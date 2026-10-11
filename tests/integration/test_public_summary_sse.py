"""Real Responses adapter, grounded service and public SSE projection."""

import asyncio
import json
import threading
from typing import Any

from reponpc.chat.service import GroundedChatService
from reponpc.main import create_app
from reponpc.providers.openai_responses import OpenAIResponsesChatProvider
from reponpc.providers.runtime import ProviderRuntime
from tests.integration.test_chat_grounding_security import Bundles, Embedding, Limits
from tests.integration.test_chat_sse_api import ready_state
from tests.security.test_visitor_gateway_review import _raw_asgi_request
from tests.unit.test_chat_stream import CAP, sse
from tests.unit.test_openai_responses import SUMMARY, completed, events
from tests.unit.test_public_summary import KEY, URL


def test_actual_summary_arrives_early_without_final_answer_or_secret() -> None:
    release = threading.Event()
    raw_answer = json.dumps(
        {
            "segments": [
                {
                    "kind": "project",
                    "text": "A retrieval feature is documented.",
                    "source_ids": ["S1"],
                }
            ],
            "insufficient_evidence": False,
        }
    )

    class Held:
        calls = 0

        def stream_lines(self, _method: str, _url: str, **kwargs: Any) -> int:
            self.calls += 1
            frames = events(payload=completed(raw_answer))
            for index, frame in enumerate(frames):
                for line in sse(frame):
                    kwargs["on_line"](line)
                if index == 2:
                    release.wait(1)
                if kwargs["cancelled"]():
                    raise InterruptedError
            return 200

    transport = Held()
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
    app = create_app(setup_state=ready_state(), chat_service=service)

    async def exercise() -> None:
        seen = asyncio.Event()
        frames: list[dict] = []

        def capture(frame: dict) -> None:
            frames.append(frame)
            if b"event: reasoning_summary" in frame.get("body", b""):
                seen.set()

        task = asyncio.create_task(
            _raw_asgi_request(
                app,
                raw_path=b"/api/public/chat/stream",
                method="POST",
                headers=[(b"content-type", b"application/json")],
                body=b'{"message":"What is implemented?","locale":"en"}',
                on_send=capture,
            )
        )
        try:
            await asyncio.wait_for(seen.wait(), 0.7)
            assert not task.done()
            assert not any(b"event: token" in frame.get("body", b"") for frame in frames)
        finally:
            release.set()
        await asyncio.wait_for(task, 1)
        text = b"".join(frame.get("body", b"") for frame in frames).decode()
        assert SUMMARY in text and KEY not in text and URL not in text
        assert text.index("event: reasoning_summary") < text.index("event: metadata")
        assert text.count("event: complete") == 1 and "retrieval feature" in text
        for block in text.split("\n\n"):
            if block.startswith("event: reasoning_summary"):
                assert set(json.loads(block.split("data: ", 1)[1])) == {"text", "elapsed_ms"}

    asyncio.run(exercise())
    assert transport.calls == 1
