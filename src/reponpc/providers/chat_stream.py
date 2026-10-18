"""Bounded chat parsers exposing fixed activity labels, never reasoning text."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Literal

from reponpc.providers.contracts import ProviderError, ProviderFailureCode

ProviderActivity = Literal["thinking", "generating"]


class ChatStreamParser:
    """Parse Ollama NDJSON or Chat Completions SSE without interpreting prose."""

    def __init__(self, *, ollama: bool, on_activity: Callable[[ProviderActivity], None]) -> None:
        self._ollama = ollama
        self._on_activity = on_activity
        self._sse_data: list[str] = []
        self.content = ""
        self.finish_reason: str | None = None
        self.terminal = False
        self.payload: dict = {}

    def line(self, line: bytes) -> None:
        try:
            value = line.decode("utf-8").rstrip("\r\n")
            if self._ollama:
                if value.strip():
                    self._chunk(json.loads(value))
            elif value.startswith("data:"):
                self._sse_data.append(value[5:].lstrip(" "))
            elif not value:
                self._flush_sse()
        except UnicodeError, ValueError, KeyError, TypeError:
            raise ProviderError(ProviderFailureCode.INVALID_RESPONSE) from None

    def finish(self) -> None:
        try:
            self._flush_sse()
        except ValueError, KeyError, TypeError:
            raise ProviderError(ProviderFailureCode.INVALID_RESPONSE) from None
        if not self.terminal or not isinstance(self.finish_reason, str) or not self.finish_reason:
            raise ProviderError(ProviderFailureCode.INVALID_RESPONSE)

    def _flush_sse(self) -> None:
        if not self._sse_data:
            return
        data = "\n".join(self._sse_data)
        self._sse_data.clear()
        if data == "[DONE]":
            if self.finish_reason is None or self.terminal:
                raise ProviderError(ProviderFailureCode.INVALID_RESPONSE)
            self.terminal = True
        else:
            self._chunk(json.loads(data))

    def _chunk(self, chunk: object) -> None:
        if not isinstance(chunk, dict) or self.terminal or "error" in chunk:
            raise ProviderError(ProviderFailureCode.INVALID_RESPONSE)
        if self._ollama:
            message = chunk.get("message", {})
            if not isinstance(message, dict) or type(chunk.get("done")) is not bool:
                raise ProviderError(ProviderFailureCode.INVALID_RESPONSE)
            thinking = message.get("thinking", "")
            if not isinstance(thinking, str):
                raise ProviderError(ProviderFailureCode.INVALID_RESPONSE)
            if thinking:
                self._on_activity("thinking")
            self._content(message.get("content", ""))
            if chunk["done"]:
                self.terminal = True
                self.finish_reason = chunk.get("done_reason", "stop")
                self.payload = {
                    key: chunk[key] for key in ("prompt_eval_count", "eval_count") if key in chunk
                }
        else:
            choices = chunk.get("choices")
            if not isinstance(choices, list) or len(choices) > 1:
                raise ProviderError(ProviderFailureCode.INVALID_RESPONSE)
            if choices:
                choice = choices[0]
                if not isinstance(choice, dict) or choice.get("index", 0) != 0:
                    raise ProviderError(ProviderFailureCode.INVALID_RESPONSE)
                delta = choice.get("delta")
                if not isinstance(delta, dict) or delta.get("tool_calls"):
                    raise ProviderError(ProviderFailureCode.INVALID_RESPONSE)
                self._content(delta.get("content") or "")
                # Generic Chat Completions has no standard public reasoning
                # summary. Ignore all unknown reasoning/provider fields.
                reason = choice.get("finish_reason")
                if reason is not None:
                    if self.finish_reason is not None:
                        raise ProviderError(ProviderFailureCode.INVALID_RESPONSE)
                    self.finish_reason = reason
            if chunk.get("usage") is not None:
                self.payload["usage"] = chunk["usage"]

    def _content(self, delta: object) -> None:
        if not isinstance(delta, str) or (self.finish_reason is not None and delta):
            raise ProviderError(ProviderFailureCode.INVALID_RESPONSE)
        self.content += delta
        if delta:
            self._on_activity("generating")
