"""Buffered private Ollama chat adapter with no cloud fallback."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

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


@dataclass(slots=True)
class OllamaChatProvider(ChatProvider):
    """Adapt one private Ollama model; failures never invoke another adapter."""

    base_url: str = field(repr=False)
    model: str
    capabilities_config: ProviderCapabilities
    transport: ProviderHttpTransport = field(default_factory=UrllibProviderHttpTransport)
    _origin: ProviderOrigin = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if not self.model:
            raise ValueError("chat model must be non-empty")
        self._origin = ProviderOrigin(self.base_url, allow_private_http=True)

    def capabilities(self) -> ProviderCapabilities:
        return self.capabilities_config

    def health(self) -> ProviderHealth:
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
    ) -> ProviderResult:
        _validate_request(self.capabilities_config, messages, max_output_tokens, timeout)
        request: dict[str, Any] = {
            "model": self.model,
            "messages": [
                {"role": message.role, "content": message.content} for message in messages
            ],
            "stream": False,
            "options": {"num_predict": max_output_tokens},
        }
        if self.capabilities_config.structured_output:
            request["format"] = response_schema
        started = time.monotonic()
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
            raise ProviderError(failure_for_status(response.status))
        try:
            payload = _json_object(response.body)
            message = payload["message"]
            if not isinstance(message, dict):
                raise ValueError
            content = message.get("content")
            if not isinstance(content, str) or not content:
                raise ValueError
            finish_reason = payload.get("done_reason", "stop")
            if not isinstance(finish_reason, str) or not finish_reason:
                raise ValueError
            usage = _ollama_usage(payload) if self.capabilities_config.usage_reporting else None
        except (KeyError, ValueError, TypeError) as exc:
            raise ProviderError(ProviderFailureCode.INVALID_RESPONSE) from exc
        return ProviderResult(
            content=content,
            finish_reason=finish_reason,
            usage=usage,
            provider_request_id=None,
            duration_ms=(time.monotonic() - started) * 1000,
        )


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
