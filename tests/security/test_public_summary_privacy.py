"""Actual service/adapter/SSE reject copied prompt or credentials without logging."""

import json
import logging

import pytest
from fastapi.testclient import TestClient

from reponpc.chat.service import GroundedChatService
from reponpc.main import create_app
from reponpc.providers.openai_responses import OpenAIResponsesChatProvider
from reponpc.providers.runtime import ProviderRuntime
from tests.integration.test_chat_grounding_security import Bundles, Embedding, Limits
from tests.integration.test_chat_sse_api import ready_state
from tests.unit.test_chat_stream import CAP, StreamTransport, sse
from tests.unit.test_openai_responses import ANSWER, completed, events
from tests.unit.test_public_summary import KEY, URL


@pytest.mark.parametrize(
    "attack", ["key", "endpoint", "actual_prompt", "raw_extension", "invalid_final"]
)
def test_public_projection_does_not_leak_private_request_or_unvalidated_answer(
    attack: str, caplog: pytest.LogCaptureFixture
) -> None:
    class Adversarial(StreamTransport):
        def stream_lines(self, method: str, url: str, **kwargs) -> int:
            request = json.loads(kwargs["body"])
            summary = "Comparing sources before preparing a supported reply."
            if attack == "key":
                summary = KEY
            elif attack == "endpoint":
                summary = URL
            elif attack == "actual_prompt":
                summary = request["input"][0]["content"][:200]
            frames = events(
                summary,
                completed(
                    "FORBIDDEN_UNVALIDATED_FINAL_CANARY" if attack == "invalid_final" else ANSWER
                ),
            )
            frames.insert(1, {"type": "response.raw_thinking.delta", "thinking": KEY + URL})
            if attack == "raw_extension":
                frames.pop(3)  # No public-summary event; unknown raw field only.
            self.lines = [line for frame in frames for line in sse(frame)]
            return super().stream_lines(method, url, **kwargs)

    transport = Adversarial([])
    service = GroundedChatService(
        bundles=Bundles(),
        limits=Limits(),
        providers=ProviderRuntime(
            chat=OpenAIResponsesChatProvider(
                URL, "selected", CAP, api_key=KEY, transport=transport
            ),
            embedding=Embedding(),
        ),
        max_output_tokens=100,
        timeout_seconds=2,
    )
    with (
        caplog.at_level(logging.DEBUG),
        TestClient(create_app(setup_state=ready_state(), chat_service=service)) as client,
    ):
        response = client.post(
            "/api/public/chat/stream", json={"message": "What is implemented?", "locale": "en"}
        )
    assert response.status_code == 200
    assert KEY not in response.text and URL not in response.text
    assert "FORBIDDEN_UNVALIDATED_FINAL_CANARY" not in response.text
    assert KEY not in caplog.text and URL not in caplog.text
    assert "Comparing sources before preparing a supported reply." not in caplog.text
    if attack in {"key", "endpoint", "actual_prompt", "raw_extension"}:
        assert "event: reasoning_summary" not in response.text
    assert len(transport.requests) == 1
