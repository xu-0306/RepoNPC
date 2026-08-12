"""Buffered OpenAI-compatible chat adapter with explicit capabilities."""

from __future__ import annotations

import json
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


@dataclass(slots=True)
class OpenAICompatibleChatProvider(ChatProvider):
    """Adapt one explicitly selected OpenAI-compatible model; never fall back."""

    base_url: str
    model: str
    capabilities_config: ProviderCapabilities
    api_key: str | None = field(default=None, repr=False)
    transport: ProviderHttpTransport = field(default_factory=UrllibProviderHttpTransport)
    allow_private_http: bool = False
    _origin: ProviderOrigin = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if not self.model:
            raise ValueError("chat model must be non-empty")
        self._origin = ProviderOrigin(self.base_url, self.allow_private_http)

    def capabilities(self) -> ProviderCapabilities:
        return self.capabilities_config

    def health(self) -> ProviderHealth:
        started = time.monotonic()
        del started
        response = self.transport.request(
            "GET",
            self._origin.endpoint("models"),
            headers=self._headers(),
            body=None,
            timeout=5.0,
        )
        if response.status != 200:
            return ProviderHealth(
                ready=False,
                checked_at=_checked_at(),
                failure_code=failure_for_status(response.status),
            )
        try:
            payload = _json_object(response.body)
            if not isinstance(payload.get("data"), list):
                raise ValueError
        except ValueError:
            return ProviderHealth(
                ready=False,
                checked_at=_checked_at(),
                failure_code=ProviderFailureCode.INVALID_RESPONSE,
            )
        return ProviderHealth(ready=True, checked_at=_checked_at())

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
            "max_tokens": max_output_tokens,
            "stream": False,
        }
        if self.capabilities_config.structured_output:
            request["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": "reponpc_answer",
                    "strict": True,
                    "schema": response_schema,
                },
            }
        started = time.monotonic()
        response = self.transport.request(
            "POST",
            self._origin.endpoint("chat/completions"),
            headers=self._headers({"Content-Type": "application/json"}),
            body=_json_bytes(request),
            timeout=timeout,
        )
        if response.status != 200:
            raise ProviderError(failure_for_status(response.status))
        try:
            payload = _json_object(response.body)
            choices = payload["choices"]
            if not isinstance(choices, list) or len(choices) != 1:
                raise ValueError
            choice = choices[0]
            if not isinstance(choice, dict) or not isinstance(choice.get("message"), dict):
                raise ValueError
            content = choice["message"].get("content")
            if not isinstance(content, (str, dict)) or not content:
                raise ValueError
            finish_reason = choice.get("finish_reason")
            if not isinstance(finish_reason, str) or not finish_reason:
                raise ValueError
            usage = _usage(payload.get("usage"))
            request_id = payload.get("id")
            if request_id is not None and not isinstance(request_id, str):
                raise ValueError
        except (KeyError, ValueError, TypeError) as exc:
            raise ProviderError(ProviderFailureCode.INVALID_RESPONSE) from exc
        return ProviderResult(
            content=content,
            finish_reason=finish_reason,
            usage=usage,
            provider_request_id=request_id,
            duration_ms=(time.monotonic() - started) * 1000,
        )

    def _headers(self, additional: dict[str, str] | None = None) -> dict[str, str]:
        headers = {"Accept": "application/json", "User-Agent": "RepoNPC-provider"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        if additional:
            headers.update(additional)
        return headers


def _validate_request(
    capabilities: ProviderCapabilities,
    messages: tuple[ProviderMessage, ...],
    max_output_tokens: int,
    timeout: float,
) -> None:
    if not messages or timeout <= 0:
        raise ProviderError(ProviderFailureCode.INVALID_RESPONSE)
    if (
        isinstance(max_output_tokens, bool)
        or not 0 < max_output_tokens <= capabilities.max_output_tokens
    ):
        raise ProviderError(ProviderFailureCode.CONTEXT_OVERFLOW)
    if not capabilities.system_role and any(message.role == "system" for message in messages):
        raise ProviderError(ProviderFailureCode.INVALID_RESPONSE)


def _usage(value: object) -> ProviderUsage | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        raise ValueError
    prompt = value.get("prompt_tokens")
    completion = value.get("completion_tokens")
    if not isinstance(prompt, int) or isinstance(prompt, bool):
        raise ValueError
    if not isinstance(completion, int) or isinstance(completion, bool):
        raise ValueError
    return ProviderUsage(prompt, completion)


def _json_object(body: bytes) -> dict[str, Any]:
    try:
        payload = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError from exc
    if not isinstance(payload, dict):
        raise ValueError
    return payload


def _json_bytes(value: dict[str, Any]) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _checked_at() -> str:
    from datetime import UTC, datetime

    return datetime.now(UTC).isoformat().replace("+00:00", "Z")
