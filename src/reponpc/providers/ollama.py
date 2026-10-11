"""Buffered private Ollama chat adapter with no cloud fallback."""

from __future__ import annotations

import re
import time
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from typing import Any, Literal

from reponpc.providers.chat_stream import ChatStreamParser, ProviderActivity
from reponpc.providers.contracts import (
    ChatProvider,
    ProviderCapabilities,
    ProviderError,
    ProviderFailureCode,
    ProviderHealth,
    ProviderMessage,
    ProviderResult,
    ProviderUsage,
    ResponseSchema,
)
from reponpc.providers.error_messages import provider_error_message
from reponpc.providers.http_transport import (
    ProviderHttpTransport,
    ProviderOrigin,
    UrllibProviderHttpTransport,
    failure_for_status,
)
from reponpc.providers.model_catalog import ollama_model_available
from reponpc.providers.openai_compatible import (
    _checked_at,
    _json_bytes,
    _json_object,
    _validate_request,
)
from reponpc.providers.response_diagnostics import ProviderResponseError, ResponseIssue

_MODEL_LIST_UNSUPPORTED = frozenset({404, 405, 501})


@dataclass(slots=True)
class OllamaChatProvider(ChatProvider):
    """Adapt one private Ollama model; failures never invoke another adapter."""

    base_url: str = field(repr=False)
    model: str
    capabilities_config: ProviderCapabilities
    transport: ProviderHttpTransport = field(
        default_factory=UrllibProviderHttpTransport, repr=False
    )
    _origin: ProviderOrigin = field(init=False, repr=False)
    _preparation_error: ProviderFailureCode | None = field(init=False, default=None, repr=False)
    _prepared: bool = field(init=False, default=False, repr=False)

    def __post_init__(self) -> None:
        if not self.model:
            raise ValueError("chat model must be non-empty")
        self._origin = ProviderOrigin(self.base_url, allow_private_http=True)

    def capabilities(self) -> ProviderCapabilities:
        return self.capabilities_config

    def prepare(self, *, timeout: float = 5.0) -> None:
        """Discover bounded capabilities once in the existing assembly/probe path.

        Failure remains attached to this adapter; generation never retries discovery.
        No model templates, endpoint data, or thinking text are retained.
        """
        if self._prepared:
            if self._preparation_error is not None:
                raise ProviderError(self._preparation_error)
            return
        self._prepared = True
        try:
            response = self.transport.request(
                "POST",
                self._origin.endpoint("api/show"),
                headers={"Content-Type": "application/json", "Accept": "application/json"},
                body=_json_bytes({"model": self.model}),
                timeout=min(timeout, 5.0),
            )
            if response.status in _MODEL_LIST_UNSUPPORTED:
                return
            if response.status != 200:
                raise ProviderError(failure_for_status(response.status))
            payload = _json_object(response.body)
            supported, control = _reasoning_control(payload)
            context = _model_context_limit(payload)
            configured = self.capabilities_config
            effective_context = min(
                configured.max_context_tokens, context or configured.max_context_tokens
            )
            self.capabilities_config = replace(
                configured,
                max_context_tokens=effective_context,
                max_output_tokens=min(configured.max_output_tokens, effective_context),
                reasoning_supported=supported,
                reasoning_control=control,
            )
            if effective_context <= configured.max_output_tokens:
                raise ProviderError(ProviderFailureCode.CONTEXT_OVERFLOW)
        except ProviderError as exc:
            self._preparation_error = exc.code
            raise
        except (ValueError, TypeError, KeyError):
            self._preparation_error = ProviderFailureCode.INVALID_RESPONSE
            raise ProviderError(ProviderFailureCode.INVALID_RESPONSE) from None

    def health(self) -> ProviderHealth:
        if self._preparation_error is not None:
            return ProviderHealth(False, _checked_at(), self._preparation_error)
        try:
            response = self.transport.request(
                "GET",
                self._origin.endpoint("api/tags"),
                headers={"Accept": "application/json", "User-Agent": "RepoNPC-provider"},
                body=None,
                timeout=5.0,
            )
        except ProviderError as exc:
            return ProviderHealth(False, _checked_at(), exc.code)
        except Exception:
            return ProviderHealth(False, _checked_at(), ProviderFailureCode.UNAVAILABLE)
        if response.status != 200:
            if response.status in _MODEL_LIST_UNSUPPORTED:
                # Listing is optional; the profile probe remains authoritative.
                return ProviderHealth(True, _checked_at())
            return ProviderHealth(False, _checked_at(), failure_for_status(response.status))
        try:
            payload = _json_object(response.body)
            if not ollama_model_available(payload, self.model):
                return ProviderHealth(False, _checked_at(), ProviderFailureCode.UNAVAILABLE)
        except ValueError:
            return ProviderHealth(False, _checked_at(), ProviderFailureCode.INVALID_RESPONSE)
        return ProviderHealth(True, _checked_at())

    def generate(
        self,
        messages: tuple[ProviderMessage, ...],
        response_schema: ResponseSchema,
        max_output_tokens: int,
        timeout: float,
        *,
        on_progress: Callable[[ProviderActivity], None] | None = None,
        cancelled: Callable[[], bool] = lambda: False,
    ) -> ProviderResult:
        if self._preparation_error is not None:
            raise ProviderError(self._preparation_error)
        _validate_request(self.capabilities_config, messages, max_output_tokens, timeout)
        _validate_context(self.capabilities_config, messages, response_schema, max_output_tokens)
        request: dict[str, Any] = {
            "model": self.model,
            "messages": [
                {"role": message.role, "content": message.content} for message in messages
            ],
            "stream": on_progress is not None,
            "options": {
                "num_predict": max_output_tokens,
                "num_ctx": self.capabilities_config.max_context_tokens,
            },
        }
        if self.capabilities_config.reasoning_control is not None:
            request["think"] = self.capabilities_config.reasoning_control
        if self.capabilities_config.structured_output:
            request["format"] = response_schema
        started = time.monotonic()
        if on_progress is not None:
            stream_lines = getattr(self.transport, "stream_lines", None)
            if not callable(stream_lines):
                raise ProviderError(ProviderFailureCode.UNAVAILABLE)
            parser = ChatStreamParser(ollama=True, on_activity=on_progress)
            status = stream_lines(
                "POST",
                self._origin.endpoint("api/chat"),
                headers={"Accept": "application/x-ndjson", "Content-Type": "application/json"},
                body=_json_bytes(request),
                timeout=timeout,
                cancelled=cancelled,
                on_line=parser.line,
            )
            if status != 200:
                raise ProviderError(failure_for_status(status))
            parser.finish()
            return ProviderResult(
                content=parser.content or ({} if parser.finish_reason == "length" else ""),
                finish_reason=parser.finish_reason or "stop",
                usage=_ollama_usage(parser.payload)
                if self.capabilities_config.usage_reporting
                else None,
                provider_request_id=None,
                duration_ms=(time.monotonic() - started) * 1000,
            )
        response = self.transport.request(
            "POST",
            self._origin.endpoint("api/chat"),
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
                "User-Agent": "RepoNPC-provider",
            },
            body=_json_bytes(request),
            timeout=timeout,
        )
        if response.status != 200:
            raise ProviderError(
                failure_for_status(response.status),
                upstream_status=response.status,
                upstream_message=provider_error_message(
                    response.body, response.headers, private_values=(self.base_url,)
                ),
            )
        issue = ResponseIssue.JSON
        try:
            payload = _json_object(response.body)
            issue = ResponseIssue.MESSAGE
            message = payload["message"]
            if not isinstance(message, dict):
                raise ValueError
            finish_reason = payload.get("done_reason", "stop")
            issue = ResponseIssue.CONTENT
            content = message.get("content")
            if content in (None, "") and finish_reason == "length":
                raise ProviderResponseError(ResponseIssue.OUTPUT_LIMIT)
            if not isinstance(content, str) or not content:
                raise ValueError
            issue = ResponseIssue.FINISH_REASON
            if not isinstance(finish_reason, str) or not finish_reason:
                raise ValueError
            issue = ResponseIssue.USAGE
            usage = _ollama_usage(payload) if self.capabilities_config.usage_reporting else None
        except (KeyError, ValueError, TypeError) as exc:
            raise ProviderResponseError(issue) from exc
        return ProviderResult(
            content=content,
            finish_reason=finish_reason,
            usage=usage,
            provider_request_id=None,
            duration_ms=(time.monotonic() - started) * 1000,
        )

    def generate_with_progress(
        self,
        messages: tuple[ProviderMessage, ...],
        response_schema: ResponseSchema,
        max_output_tokens: int,
        timeout: float,
        *,
        on_progress: Callable[[ProviderActivity], None],
        cancelled: Callable[[], bool],
    ) -> ProviderResult:
        if not callable(getattr(self.transport, "stream_lines", None)):
            return self.generate(messages, response_schema, max_output_tokens, timeout)
        return self.generate(
            messages,
            response_schema,
            max_output_tokens,
            timeout,
            on_progress=on_progress,
            cancelled=cancelled,
        )


def _model_context_limit(payload: dict[str, Any]) -> int | None:
    info = payload.get("model_info", {})
    if not isinstance(info, dict):
        raise ValueError
    architecture = info.get("general.architecture")
    if architecture is None:
        return None
    if not isinstance(architecture, str) or not re.fullmatch(r"[A-Za-z0-9_]{1,64}", architecture):
        raise ValueError
    limit = info.get(f"{architecture}.context_length")
    if limit is None:
        return None
    if type(limit) is not int or not 1 <= limit <= 16 * 1024 * 1024:
        raise ValueError
    return limit


def _reasoning_control(payload: dict[str, Any]) -> tuple[bool | None, Literal[True] | str | None]:
    metadata = payload.get("thinking")
    if metadata is None:
        capabilities = payload.get("capabilities", [])
        if (
            not isinstance(capabilities, list)
            or len(capabilities) > 32
            or any(not isinstance(value, str) or len(value) > 64 for value in capabilities)
        ):
            raise ValueError
        return (True, True) if "thinking" in capabilities else (None, None)
    if not isinstance(metadata, dict):
        raise ValueError
    values = metadata.get("values")
    default = metadata.get("default")
    if (
        not isinstance(values, list)
        or not 1 <= len(values) <= 16
        or any(
            type(value) is not bool
            and not (isinstance(value, str) and re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{0,31}", value))
            for value in values
        )
    ):
        raise ValueError
    if not any(type(default) is type(value) and default == value for value in values):
        raise ValueError
    if any(value is True for value in values):
        return True, True
    named = [value for value in values if isinstance(value, str)]
    if named:
        if not isinstance(default, str) or default not in named:
            raise ValueError
        return True, default
    return False, None


def _validate_context(
    capabilities: ProviderCapabilities,
    messages: tuple[ProviderMessage, ...],
    schema: ResponseSchema,
    output: int,
) -> None:
    # UTF-8 byte accounting is intentionally conservative without a tokenizer.
    # Include the schema and message roles/framing, never just visible content.
    serialized = _json_bytes(
        {
            "messages": [{"role": item.role, "content": item.content} for item in messages],
            "format": schema if capabilities.structured_output else None,
        }
    )
    if len(serialized) + 256 + output > capabilities.max_context_tokens:
        raise ProviderError(ProviderFailureCode.CONTEXT_OVERFLOW)


def _ollama_usage(payload: dict[str, Any]) -> ProviderUsage | None:
    prompt = payload.get("prompt_eval_count")
    completion = payload.get("eval_count")
    if prompt is None and completion is None:
        return None
    if (
        not isinstance(prompt, int)
        or isinstance(prompt, bool)
        or not isinstance(completion, int)
        or isinstance(completion, bool)
    ):
        raise ValueError
    return ProviderUsage(prompt, completion)
