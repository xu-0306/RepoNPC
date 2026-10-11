"""Real adapter parsers never project thinking or provider bodies publicly."""

from __future__ import annotations

import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

import pytest

from reponpc.providers import (
    ProviderCapabilities,
    ProviderError,
    ProviderFailureCode,
    ProviderMessage,
)
from reponpc.providers.chat_stream import ChatStreamParser
from reponpc.providers.http_transport import UrllibProviderHttpTransport
from reponpc.providers.ollama import OllamaChatProvider
from reponpc.providers.openai_compatible import OpenAICompatibleChatProvider

CANARY = "PRIVATE_THINKING_PROMPT_KEY_CANARY_92f7"
CAP = ProviderCapabilities(False, True, True, True, True, 8192, 100)


class StreamTransport:
    def __init__(self, lines: list[bytes], status: int = 200) -> None:
        self.lines = lines
        self.status = status
        self.requests: list[dict[str, Any]] = []

    def request(self, *_args: object, **_kwargs: object):
        raise AssertionError("stream must not retry a buffered call")

    def stream_lines(self, _method: str, _url: str, **kwargs: Any) -> int:
        self.requests.append(json.loads(kwargs["body"]))
        if self.status == 200:
            for line in self.lines:
                if kwargs["cancelled"]():
                    raise InterruptedError
                kwargs["on_line"](line)
        return self.status


def ndjson(value: dict) -> bytes:
    return (json.dumps(value, ensure_ascii=False) + "\n").encode()


def sse(value: dict | str) -> list[bytes]:
    return [
        ("data: " + (value if isinstance(value, str) else json.dumps(value)) + "\n").encode(),
        b"\n",
    ]


@pytest.mark.parametrize("locale", ["en", "zh-TW"])
def test_native_thinking_is_activity_only_and_final_content_is_buffered(locale: str) -> None:
    content = '{"segments":[],"insufficient_evidence":true}'
    transport = StreamTransport(
        [
            ndjson({"message": {"thinking": CANARY}, "done": False}),
            ndjson({"message": {"content": content[:12]}, "done": False}),
            ndjson(
                {
                    "message": {"content": content[12:]},
                    "done": True,
                    "done_reason": "stop",
                    "prompt_eval_count": 2,
                    "eval_count": 3,
                }
            ),
        ]
    )
    activity: list[str] = []
    provider = OllamaChatProvider("http://localhost:11434", "arbitrary", CAP, transport=transport)
    result = provider.generate_with_progress(
        (ProviderMessage("user", locale),),
        {},
        100,
        1,
        on_progress=activity.append,
        cancelled=lambda: False,
    )
    assert activity == ["thinking", "generating", "generating"]
    assert result.content == content and CANARY not in repr(result)
    assert transport.requests[0]["stream"] is True and len(transport.requests) == 1


def test_generic_api_ignores_all_reasoning_extensions_and_tool_narratives() -> None:
    chunks = sse(
        {
            "choices": [
                {
                    "index": 0,
                    "delta": {
                        "reasoning": CANARY,
                        "reasoning_content": CANARY,
                        "content": '{"ok":',
                    },
                    "finish_reason": None,
                }
            ]
        }
    )
    chunks += sse(
        {"choices": [{"index": 0, "delta": {"content": "true}"}, "finish_reason": "stop"}]}
    )
    chunks += sse("[DONE]")
    transport = StreamTransport(chunks)
    activity: list[str] = []
    provider = OpenAICompatibleChatProvider(
        "https://api.example.test/v1", "arbitrary", CAP, transport=transport, api_key=CANARY
    )
    result = provider.generate_with_progress(
        (ProviderMessage("user", "question"),),
        {},
        100,
        1,
        on_progress=activity.append,
        cancelled=lambda: False,
    )
    assert result.content == '{"ok":true}'
    assert activity == ["generating", "generating"]
    assert CANARY not in repr(result)
    assert len(transport.requests) == 1


@pytest.mark.parametrize(
    "lines",
    [
        [b"data: {broken\n", b"\n"],
        [b"data: {broken\n"],
        sse({"choices": [{"delta": {"content": "unfinished"}, "finish_reason": None}]}),
        sse("[DONE]"),
        sse(
            {"choices": [{"delta": {"tool_calls": [{"function": CANARY}]}, "finish_reason": None}]}
        ),
    ],
)
def test_malformed_incomplete_and_tool_call_streams_fail_closed(lines: list[bytes]) -> None:
    parser = ChatStreamParser(ollama=False, on_activity=lambda _stage: None)
    with pytest.raises(ProviderError):
        for line in lines:
            parser.line(line)
        parser.finish()


@pytest.mark.parametrize("ollama", [True, False])
def test_upstream_failure_does_not_reflect_body_or_retry(ollama: bool) -> None:
    transport = StreamTransport([CANARY.encode()], 429)
    cls = OllamaChatProvider if ollama else OpenAICompatibleChatProvider
    provider = cls("https://api.example.test", "arbitrary", CAP, transport=transport)
    with pytest.raises(ProviderError) as raised:
        provider.generate_with_progress(
            (ProviderMessage("user", "q"),),
            {},
            100,
            1,
            on_progress=lambda _stage: None,
            cancelled=lambda: False,
        )
    assert raised.value.code is ProviderFailureCode.RATE_LIMIT
    assert CANARY not in str(raised.value) and len(transport.requests) == 1


@pytest.mark.parametrize("cancel", [True, False])
def test_real_socket_blocked_read_stops_on_cancel_or_total_deadline(cancel: bool) -> None:
    release = threading.Event()
    connected = threading.Event()
    cancelled = threading.Event()

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            self.rfile.read(int(self.headers.get("Content-Length", "0")))
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"first\n")
            self.wfile.flush()
            connected.set()
            release.wait(2)

        def log_message(self, *_args: Any) -> None:
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    timer = threading.Timer(0.15, cancelled.set) if cancel else None
    if timer:
        timer.start()
    started = time.monotonic()
    try:
        with pytest.raises((InterruptedError, ProviderError)) as raised:
            UrllibProviderHttpTransport().stream_lines(
                "POST",
                f"http://127.0.0.1:{server.server_port}/chat",
                headers={},
                body=b"{}",
                timeout=1 if cancel else 0.2,
                cancelled=cancelled.is_set,
                on_line=lambda _line: None,
            )
        assert connected.is_set() and time.monotonic() - started < 0.7
        if cancel:
            assert isinstance(raised.value, InterruptedError)
        else:
            assert (
                isinstance(raised.value, ProviderError)
                and raised.value.code is ProviderFailureCode.TIMEOUT
            )
    finally:
        release.set()
        if timer:
            timer.cancel()
        server.shutdown()
        server.server_close()
        thread.join(1)


def test_usage_and_empty_chunks_do_not_claim_new_generation_activity() -> None:
    activity: list[str] = []
    parser = ChatStreamParser(ollama=False, on_activity=activity.append)
    for line in (
        sse({"choices": [{"delta": {"content": "answer"}, "finish_reason": None}]})
        + sse({"choices": [{"delta": {}, "finish_reason": "stop"}]})
        + sse({"choices": [], "usage": {"completion_tokens": 1}})
        + sse("[DONE]")
    ):
        parser.line(line)
    parser.finish()
    assert activity == ["generating"]


def test_real_socket_continuous_activity_cannot_restart_total_deadline() -> None:
    release = threading.Event()
    lines: list[bytes] = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            self.rfile.read(int(self.headers.get("Content-Length", "0")))
            self.send_response(200)
            self.end_headers()
            try:
                while not release.is_set():
                    self.wfile.write(b"activity\n")
                    self.wfile.flush()
                    release.wait(0.02)
            except OSError:
                pass

        def log_message(self, *_args: Any) -> None:
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    started = time.monotonic()
    try:
        with pytest.raises(ProviderError) as raised:
            UrllibProviderHttpTransport().stream_lines(
                "POST",
                f"http://127.0.0.1:{server.server_port}/chat",
                headers={},
                body=b"{}",
                timeout=0.2,
                cancelled=lambda: False,
                on_line=lines.append,
            )
        assert raised.value.code is ProviderFailureCode.TIMEOUT
        assert len(lines) >= 2 and time.monotonic() - started < 0.7
    finally:
        release.set()
        server.shutdown()
        server.server_close()
        thread.join(1)
