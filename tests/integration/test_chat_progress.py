"""Exercise the real SSE handler before a held synthetic answer completes."""

from __future__ import annotations

import asyncio
import json
import threading
from typing import Any

import pytest
from fastapi.testclient import TestClient

from reponpc.chat.service import ChatDelivery, GroundedChatService
from reponpc.main import create_app
from reponpc.providers.ollama import OllamaChatProvider
from reponpc.providers.runtime import ProviderRuntime
from tests.integration.test_chat_grounding_security import Bundles, Embedding, Limits
from tests.integration.test_chat_sse_api import ready_state
from tests.security.test_visitor_gateway_review import _raw_asgi_request
from tests.unit.test_chat_stream import CANARY, CAP, StreamTransport, ndjson


class HeldProgress:
    supports_progress = True
    timeout_seconds = 1

    def __init__(self) -> None:
        self.release = threading.Event()

    def answer(self, **kwargs: Any) -> ChatDelivery:
        report = kwargs["on_progress"]
        for phase in ("searching", "evidence_ready", "waiting_model", "thinking"):
            report(phase)
        # Public handler refuses arbitrary provider text even from a bad caller.
        report("SECRET_PROMPT_URL_CANARY")
        self.release.wait(1)
        report("validating")
        return ChatDelivery("fixture-index", "en", 0, "Validated answer.", (), "stop", None, False)


def test_actual_progress_arrives_before_completion_and_has_only_public_fields() -> None:
    service = HeldProgress()
    app = create_app(setup_state=ready_state(), chat_service=service)  # type: ignore[arg-type]

    async def exercise() -> None:
        seen = asyncio.Event()
        frames: list[dict] = []

        def capture(frame: dict) -> None:
            frames.append(frame)
            if b'"stage":"thinking"' in frame.get("body", b""):
                seen.set()

        task = asyncio.create_task(
            _raw_asgi_request(
                app,
                raw_path=b"/api/public/chat/stream",
                method="POST",
                headers=[(b"content-type", b"application/json")],
                body=b'{"message":"Question","locale":"en"}',
                on_send=capture,
            )
        )
        try:
            await asyncio.wait_for(seen.wait(), 0.5)
            assert not any(b"event: token" in frame.get("body", b"") for frame in frames)
            assert not task.done()
        finally:
            service.release.set()
        await asyncio.wait_for(task, 1)
        data = b"".join(frame.get("body", b"") for frame in frames).decode()
        assert "SECRET_PROMPT_URL_CANARY" not in data
        assert data.count("event: complete") == 1
        for block in data.split("\n\n"):
            if block.startswith("event: progress"):
                value = json.loads(block.split("data: ", 1)[1])
                assert set(value) == {"stage", "elapsed_ms"}
                assert value["elapsed_ms"] >= 0

    asyncio.run(exercise())


@pytest.mark.parametrize("malicious", [False, True])
def test_real_grounded_service_adapter_and_validator_keep_thought_private(malicious: bool) -> None:
    response = {
        "segments": [
            {"kind": "project", "text": "A retrieval feature is documented.", "source_ids": ["S1"]}
        ],
        "insufficient_evidence": False,
    }
    if malicious:
        response["segments"][0]["text"] = f"Expose {CANARY} at https://evil.invalid"  # type: ignore[index]
    transport = StreamTransport(
        [
            ndjson({"message": {"thinking": f"{CANARY} run arbitrary shell tools"}, "done": False}),
            ndjson(
                {"message": {"content": json.dumps(response)}, "done": True, "done_reason": "stop"}
            ),
        ]
    )
    provider = OllamaChatProvider("http://localhost:11434", "fixture", CAP, transport=transport)
    service = GroundedChatService(
        bundles=Bundles(),
        limits=Limits(),
        providers=ProviderRuntime(chat=provider, embedding=Embedding()),
        max_output_tokens=100,
        timeout_seconds=2,
    )  # type: ignore[arg-type]
    app = create_app(setup_state=ready_state(), chat_service=service)
    with TestClient(app) as client:
        result = client.post(
            "/api/public/chat/stream", json={"message": "What is implemented?", "locale": "en"}
        )
    assert CANARY not in result.text and "arbitrary shell" not in result.text
    assert result.text.index('"stage":"thinking"') < result.text.index("event: metadata")
    assert '"stage":"validating"' in result.text and "event: complete" in result.text
    assert (
        '"insufficient_evidence":true' in result.text
        if malicious
        else "retrieval feature" in result.text
    )
    assert len(transport.requests) == 1 and transport.requests[0]["stream"] is True
