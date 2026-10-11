"""Explicit interface: mature SSE, public summary privacy and unchanged final boundary."""

from __future__ import annotations

import json
from typing import Any

import pytest

from reponpc.providers import ProviderError, ProviderMessage
from reponpc.providers.http_transport import ProviderHttpResponse
from reponpc.providers.openai_responses import OpenAIResponsesChatProvider
from reponpc.providers.response_diagnostics import ProviderResponseError, ResponseIssue
from tests.unit.test_chat_stream import CAP, StreamTransport, sse
from tests.unit.test_public_summary import KEY, PROMPT, URL

ANSWER = '{"segments":[],"insufficient_evidence":true}'
SUMMARY = "Comparing evidence before preparing a supported reply."


def completed(content: str = ANSWER) -> dict:
    return {
        "status": "completed",
        "output": [
            {
                "type": "reasoning",
                "id": "r",
                "encrypted_content": KEY,
                "summary": [{"type": "summary_text", "text": KEY}],
            },
            {
                "type": "message",
                "id": "m",
                "role": "assistant",
                "status": "completed",
                "content": [{"type": "output_text", "text": content}],
            },
        ],
        "usage": {"input_tokens": 20, "output_tokens": 30},
    }


def events(text: str = SUMMARY, payload: dict | None = None) -> list[dict]:
    return [
        {
            "type": "response.output_item.added",
            "output_index": 0,
            "item": {"id": "r", "type": "reasoning"},
        },
        {
            "type": "response.reasoning_summary_text.delta",
            "item_id": "r",
            "output_index": 0,
            "summary_index": 0,
            "delta": KEY[:8],
        },
        {
            "type": "response.reasoning_summary_text.done",
            "item_id": "r",
            "output_index": 0,
            "summary_index": 0,
            "text": text,
        },
        {
            "type": "response.output_item.added",
            "output_index": 1,
            "item": {"id": "m", "type": "message"},
        },
        {"type": "response.output_text.delta", "item_id": "m", "output_index": 1, "delta": ANSWER},
        {"type": "response.completed", "response": payload or completed()},
    ]


def provider(
    frames: list[dict], status: int = 200
) -> tuple[OpenAIResponsesChatProvider, StreamTransport]:
    transport = StreamTransport([line for frame in frames for line in sse(frame)], status)
    return OpenAIResponsesChatProvider(
        URL, "owner-selected", CAP, api_key=KEY, transport=transport
    ), transport


def generate(
    adapter: OpenAIResponsesChatProvider, summaries: list[str], activity: list[str] | None = None
):
    return adapter.generate_with_public_summary(
        (ProviderMessage("system", PROMPT), ProviderMessage("user", "Question")),
        {},
        100,
        1,
        on_progress=(activity if activity is not None else []).append,
        on_summary=summaries.append,
        cancelled=lambda: False,
    )


def test_summary_is_complete_and_final_is_buffered_in_one_explicit_call() -> None:
    adapter, transport = provider(events())
    summaries: list[str] = []
    activity: list[str] = []
    result = generate(adapter, summaries, activity)
    assert summaries == [SUMMARY] and activity == ["thinking", "generating"]
    assert result.content == ANSWER and KEY not in repr(result)
    assert result.usage is not None and result.usage.input_tokens == 20
    assert len(transport.requests) == 1
    request = transport.requests[0]
    assert request["reasoning"] == {"summary": "auto"} and request["store"] is False
    assert "tools" not in request and "messages" not in request
    assert request["text"]["format"]["schema"] == {} and request["max_output_tokens"] == 100


@pytest.mark.parametrize("text", [KEY, URL, PROMPT, "x" * 4096 + KEY])
def test_unsafe_summary_suppressed_without_changing_final_answer(text: str) -> None:
    adapter, _ = provider(events(text))
    summaries: list[str] = []
    assert generate(adapter, summaries).content == ANSWER
    assert summaries == []


@pytest.mark.parametrize(
    "mutation", ["unknown_item", "duplicate", "missing_terminal", "tool", "failed", "refusal"]
)
def test_malformed_and_forbidden_streams_fail_closed(mutation: str) -> None:
    frames = events()
    if mutation == "unknown_item":
        frames[2]["item_id"] = "unknown"
    elif mutation == "duplicate":
        frames.insert(3, frames[2])
    elif mutation == "missing_terminal":
        frames.pop()
    elif mutation == "tool":
        frames[0]["item"]["type"] = "function_call"
    elif mutation == "failed":
        frames[-1]["type"] = "response.failed"
    else:
        frames.insert(5, {"type": "response.refusal.done", "refusal": KEY})
    adapter, transport = provider(frames)
    with pytest.raises(ProviderError):
        generate(adapter, [])
    assert len(transport.requests) == 1


def test_output_limit_and_cancel_never_retry() -> None:
    adapter, transport = provider(
        events(
            payload={"status": "incomplete", "incomplete_details": {"reason": "max_output_tokens"}}
        )
    )
    with pytest.raises(ProviderResponseError) as error:
        generate(adapter, [])
    assert error.value.issue == ResponseIssue.OUTPUT_LIMIT
    assert len(transport.requests) == 1
    adapter, transport = provider(events())
    with pytest.raises(InterruptedError):
        adapter.generate_with_public_summary(
            (ProviderMessage("user", "Q"),),
            {},
            100,
            1,
            on_progress=lambda _: None,
            on_summary=lambda _: None,
            cancelled=lambda: True,
        )
    assert len(transport.requests) == 1


def test_probe_verifies_summary_option_but_does_not_publish_summaries() -> None:
    class Buffered:
        request_payload: dict[str, Any]

        def request(self, _method: str, url: str, **kwargs: Any):
            assert url.endswith("/responses")
            self.request_payload = json.loads(kwargs["body"])
            return ProviderHttpResponse(200, {}, json.dumps(completed()).encode())

    transport = Buffered()
    adapter = OpenAIResponsesChatProvider(URL, "owner-selected", CAP, transport=transport)
    assert adapter.generate((ProviderMessage("user", "Question"),), {}, 100, 1).content == ANSWER
    assert (
        transport.request_payload["reasoning"] == {"summary": "auto"}
        and transport.request_payload["stream"] is False
    )
