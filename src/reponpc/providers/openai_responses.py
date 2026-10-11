"""Explicit Responses interface; final answers buffered, public summaries checked."""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from typing import Any

from reponpc.providers.chat_stream import ProviderActivity
from reponpc.providers.contracts import (
    ProviderError,
    ProviderFailureCode,
    ProviderMessage,
    ProviderResult,
    ResponseSchema,
)
from reponpc.providers.http_transport import failure_for_status
from reponpc.providers.openai_compatible import (
    OpenAICompatibleChatProvider,
    _failure_for_response,
    _json_bytes,
    _json_object,
    _usage,
    _validate_request,
)
from reponpc.providers.public_summary import PublicSummaryFilter
from reponpc.providers.response_diagnostics import ProviderResponseError, ResponseIssue


def _result(payload: dict[str, Any], duration_ms: float) -> ProviderResult:
    details = payload.get("incomplete_details")
    if (
        payload.get("status") == "incomplete"
        and isinstance(details, dict)
        and details.get("reason") == "max_output_tokens"
    ):
        raise ProviderResponseError(ResponseIssue.OUTPUT_LIMIT)
    if payload.get("status") != "completed":
        raise ProviderError(ProviderFailureCode.INVALID_RESPONSE)
    output = payload.get("output")
    if not isinstance(output, list):
        raise ProviderError(ProviderFailureCode.INVALID_RESPONSE)
    text = ""
    for item in output:
        if not isinstance(item, dict):
            raise ProviderError(ProviderFailureCode.INVALID_RESPONSE)
        if item.get("type") == "reasoning":
            continue  # Never consume encrypted/private traces as answers.
        if (
            item.get("type") != "message"
            or item.get("role") != "assistant"
            or item.get("status") != "completed"
        ):
            raise ProviderError(ProviderFailureCode.INVALID_RESPONSE)
        parts = item.get("content")
        if not isinstance(parts, list):
            raise ProviderError(ProviderFailureCode.INVALID_RESPONSE)
        for part in parts:
            if (
                not isinstance(part, dict)
                or part.get("type") != "output_text"
                or not isinstance(part.get("text"), str)
            ):
                raise ProviderError(ProviderFailureCode.INVALID_RESPONSE)
            text += part["text"]
    if not text:
        raise ProviderError(ProviderFailureCode.INVALID_RESPONSE)
    usage = payload.get("usage")
    try:
        parsed_usage = (
            _usage(
                {
                    "prompt_tokens": usage["input_tokens"],
                    "completion_tokens": usage["output_tokens"],
                }
            )
            if usage is not None
            else None
        )
    except (KeyError, TypeError, ValueError):
        raise ProviderError(ProviderFailureCode.INVALID_RESPONSE) from None
    return ProviderResult(text, "stop", parsed_usage, None, duration_ms)


class ResponsesStreamParser:
    """Only provider-defined complete summaries from known reasoning items."""

    def __init__(
        self,
        on_activity: Callable[[ProviderActivity], None],
        on_summary: Callable[[str], None],
        privacy: PublicSummaryFilter,
    ) -> None:
        self._on_activity = on_activity
        self._on_summary = on_summary
        self._privacy = privacy
        self._data: list[str] = []
        self._items: dict[tuple[object, object], str] = {}
        self._summaries: set[tuple[object, object, object]] = set()
        self.payload: dict[str, Any] | None = None

    def line(self, line: bytes) -> None:
        try:
            value = line.decode("utf-8").rstrip("\r\n")
            if value.startswith("data:"):
                self._data.append(value[5:].lstrip(" "))
            elif not value:
                self._flush()
        except (UnicodeError, ValueError, KeyError, TypeError):
            raise ProviderError(ProviderFailureCode.INVALID_RESPONSE) from None

    def _flush(self) -> None:
        if not self._data:
            return
        data = "\n".join(self._data)
        self._data.clear()
        chunk = json.loads(data)
        if not isinstance(chunk, dict) or self.payload is not None:
            raise ValueError
        kind = chunk.get("type")
        key = (chunk.get("item_id"), chunk.get("output_index"))
        if kind == "response.output_item.added":
            item = chunk["item"]
            item_type = item.get("type")
            if item_type not in {"reasoning", "message"} or not isinstance(item.get("id"), str):
                raise ValueError
            self._items[(item["id"], chunk.get("output_index"))] = item_type
            if item_type == "reasoning":
                self._on_activity("thinking")
        elif kind == "response.reasoning_summary_text.done":
            index = chunk.get("summary_index")
            if self._items.get(key) != "reasoning" or type(index) is not int or index < 0:
                raise ValueError
            identity = (*key, index)
            if identity in self._summaries:
                raise ValueError
            self._summaries.add(identity)
            text = self._privacy.project(chunk.get("text"))
            if text is not None:
                self._on_summary(text)
        elif kind == "response.output_text.delta":
            if self._items.get(key) != "message" or not isinstance(chunk.get("delta"), str):
                raise ValueError
            if chunk["delta"]:
                self._on_activity("generating")
        elif kind in {"response.completed", "response.incomplete"}:
            if not isinstance(chunk.get("response"), dict):
                raise ValueError
            self.payload = chunk["response"]
        elif kind in {
            "error",
            "response.failed",
            "response.refusal.delta",
            "response.refusal.done",
        }:
            raise ValueError
        # Unknown extensions, partial summaries and raw thinking are discarded.

    def finish(self, duration_ms: float) -> ProviderResult:
        try:
            self._flush()
            if self.payload is None:
                raise ValueError
            return _result(self.payload, duration_ms)
        except (ValueError, KeyError, TypeError):
            raise ProviderError(ProviderFailureCode.INVALID_RESPONSE) from None


class OpenAIResponsesChatProvider(OpenAICompatibleChatProvider):
    """Share origin/health/auth primitives; never switch or retry protocols."""

    def generate(
        self,
        messages: tuple[ProviderMessage, ...],
        response_schema: ResponseSchema,
        max_output_tokens: int,
        timeout: float,
        *,
        on_progress: Callable[[ProviderActivity], None] | None = None,
        cancelled: Callable[[], bool] = lambda: False,
        on_summary: Callable[[str], None] | None = None,
    ) -> ProviderResult:
        _validate_request(self.capabilities_config, messages, max_output_tokens, timeout)
        request: dict[str, Any] = {
            "model": self.model,
            "input": [{"role": message.role, "content": message.content} for message in messages],
            "max_output_tokens": max_output_tokens,
            "store": False,
            "reasoning": {"summary": "auto"},
            "stream": on_progress is not None,
        }
        if self.capabilities_config.structured_output:
            request["text"] = {
                "format": {
                    "type": "json_schema",
                    "name": "reponpc_answer",
                    "strict": True,
                    "schema": response_schema,
                }
            }
        started = time.monotonic()
        if on_progress is not None:
            privacy = PublicSummaryFilter(
                (item.content for item in messages), (self.base_url, self.api_key)
            )
            parser = ResponsesStreamParser(on_progress, on_summary or (lambda _: None), privacy)
            stream_lines = getattr(self.transport, "stream_lines", None)
            if not callable(stream_lines):
                raise ProviderError(ProviderFailureCode.UNAVAILABLE)
            status = stream_lines(
                "POST",
                self._origin.endpoint("responses"),
                headers=self._headers(
                    {"Content-Type": "application/json", "Accept": "text/event-stream"}
                ),
                body=_json_bytes(request),
                timeout=timeout,
                cancelled=cancelled,
                on_line=parser.line,
            )
            if status != 200:
                raise ProviderError(failure_for_status(status))
            result = parser.finish((time.monotonic() - started) * 1000)
        else:
            response = self.transport.request(
                "POST",
                self._origin.endpoint("responses"),
                headers=self._headers({"Content-Type": "application/json"}),
                body=_json_bytes(request),
                timeout=timeout,
            )
            if response.status != 200:
                raise ProviderError(_failure_for_response(response.status, response.body))
            try:
                result = _result(_json_object(response.body), (time.monotonic() - started) * 1000)
            except (ValueError, TypeError, KeyError):
                raise ProviderError(ProviderFailureCode.INVALID_RESPONSE) from None
        if not self.capabilities_config.usage_reporting:
            result = ProviderResult(
                result.content, result.finish_reason, None, None, result.duration_ms
            )
        return result

    def generate_with_public_summary(
        self,
        messages: tuple[ProviderMessage, ...],
        response_schema: ResponseSchema,
        max_output_tokens: int,
        timeout: float,
        *,
        on_progress: Callable[[ProviderActivity], None],
        cancelled: Callable[[], bool],
        on_summary: Callable[[str], None],
    ) -> ProviderResult:
        return self.generate(
            messages,
            response_schema,
            max_output_tokens,
            timeout,
            on_progress=on_progress,
            cancelled=cancelled,
            on_summary=on_summary,
        )
