"""Public chat buffers validation before emitting the stable SSE sequence."""

from __future__ import annotations

import asyncio
import json
import logging
import threading
import time
from dataclasses import dataclass

from fastapi.testclient import TestClient

from reponpc.api.public import SetupState
from reponpc.chat.answers import Citation
from reponpc.chat.limits import ChatLimitError
from reponpc.chat.service import ChatDelivery, delivery_events
from reponpc.main import create_app
from reponpc.providers import ProviderUsage


def test_no_match_complete_event_carries_bounded_profile_choices() -> None:
    delivery = ChatDelivery(
        "fixture-index",
        "en",
        0,
        "I couldn't find anything about that in this portfolio.",
        (),
        "stop",
        None,
        True,
        ("What does this project do?",),
        ("Contact", "https://example.com/contact"),
    )

    events = delivery_events(delivery, "request-id")

    assert [name for name, _payload in events] == ["metadata", "token", "complete"]
    assert events[-1][1]["suggested_questions"] == ["What does this project do?"]
    assert events[-1][1]["contact_link"] == {
        "label": "Contact",
        "url": "https://example.com/contact",
    }


@dataclass
class FixtureChatService:
    delivery: ChatDelivery | None = None
    error: Exception | None = None
    calls: int = 0

    def answer(self, **_kwargs: object) -> ChatDelivery:
        self.calls += 1
        if self.error is not None:
            raise self.error
        assert self.delivery is not None
        return self.delivery


def ready_state() -> SetupState:
    return SetupState(
        index_ready=True,
        index_version="fixture-index",
        model_ready=True,
        model_provider="ollama",
        model_last_checked_at="2026-08-12T00:00:00Z",
    )


def test_success_stream_has_exact_order_headers_and_server_owned_citation() -> None:
    citation = Citation(
        "S1",
        "E_" + "a" * 24,
        "REPOSITORY_FACT",
        "owner/repo",
        "b" * 40,
        "src/app.py",
        10,
        12,
        "Fixture",
        "excerpt",
        "https://github.com/owner/repo/blob/" + "b" * 40 + "/src/app.py#L10-L12",
    )
    service = FixtureChatService(
        ChatDelivery(
            "fixture-index",
            "en",
            1,
            "Supported answer. [S1]",
            (citation,),
            "stop",
            ProviderUsage(4, 2),
            False,
        )
    )
    application = create_app(
        setup_state=ready_state(),
        chat_service=service,  # type: ignore[arg-type]
    )

    with TestClient(application) as client:
        response = client.post(
            "/api/public/chat/stream", json={"message": "Question", "locale": "en"}
        )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert response.headers["x-accel-buffering"] == "no"
    events = [
        line.removeprefix("event: ")
        for line in response.text.splitlines()
        if line.startswith("event: ")
    ]
    assert events == ["metadata", "token", "citations", "complete"]
    assert "github.com/owner/repo/blob/" in response.text
    assert service.calls == 1


def test_worker_limit_failure_is_one_safe_terminal_sse_event() -> None:
    service = FixtureChatService(error=ChatLimitError("DAILY_BUDGET_EXHAUSTED", 3600))
    application = create_app(
        setup_state=ready_state(),
        chat_service=service,  # type: ignore[arg-type]
    )

    with TestClient(application) as client:
        response = client.post(
            "/api/public/chat/stream", json={"message": "Question", "locale": "zh-TW"}
        )

    assert response.status_code == 200
    payload = json.loads(response.text.split("event: error\ndata: ", 1)[1].split("\n", 1)[0])
    assert payload["error"]["code"] == "DAILY_BUDGET_EXHAUSTED"
    assert payload["error"]["retry_after_seconds"] == 3600
    assert response.text.count("event: error") == 1 and "event: complete" not in response.text


def test_unready_rejection_occurs_before_chat_service_call() -> None:
    service = FixtureChatService()
    application = create_app(
        setup_state=SetupState(index_ready=False, model_ready=False),
        chat_service=service,  # type: ignore[arg-type]
    )

    with TestClient(application) as client:
        response = client.post(
            "/api/public/chat/stream", json={"message": "Question", "locale": "en"}
        )

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "SERVICE_NOT_READY"
    assert service.calls == 0


def test_invalid_chat_body_uses_common_validation_error_before_service_call() -> None:
    service = FixtureChatService()
    application = create_app(
        setup_state=ready_state(),
        chat_service=service,  # type: ignore[arg-type]
    )

    with TestClient(application) as client:
        response = client.post(
            "/api/public/chat/stream",
            json={
                "message": "Question",
                "locale": "en",
                "history": [{"role": "assistant", "content": "invalid first role"}],
            },
        )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
    assert response.json()["error"]["details"]["fields"]
    assert service.calls == 0


def test_invalid_chat_body_localizes_safely_without_reflecting_input() -> None:
    service = FixtureChatService()
    application = create_app(
        setup_state=ready_state(),
        chat_service=service,  # type: ignore[arg-type]
    )
    canary = "VALIDATION_SECRET_CANARY_8d129f"

    with TestClient(application) as client:
        zh_response = client.post(
            "/api/public/chat/stream",
            json={
                "message": canary,
                "locale": "zh-TW",
                "history": [{"role": "assistant", "content": canary}],
            },
        )
        en_response = client.post(
            "/api/public/chat/stream",
            json={
                "message": canary,
                "locale": "en",
                "history": [{"role": "assistant", "content": canary}],
            },
        )

    assert zh_response.status_code == en_response.status_code == 400
    assert zh_response.json()["error"]["message"] != en_response.json()["error"]["message"]
    assert canary not in zh_response.text
    assert canary not in en_response.text
    assert service.calls == 0


def test_configured_message_and_history_limits_reject_before_service_cost() -> None:
    service = FixtureChatService()
    application = create_app(
        setup_state=ready_state(),
        chat_service=service,  # type: ignore[arg-type]
        max_message_characters=8,
        max_history_messages=1,
        max_history_characters=6,
    )

    with TestClient(application) as client:
        message_response = client.post(
            "/api/public/chat/stream",
            json={"message": "123456789", "locale": "en"},
        )
        history_response = client.post(
            "/api/public/chat/stream",
            json={
                "message": "Question",
                "locale": "en",
                "history": [{"role": "user", "content": "1234567"}],
            },
        )

    assert message_response.status_code == history_response.status_code == 413
    assert message_response.json()["error"]["code"] == "PAYLOAD_TOO_LARGE"
    assert history_response.json()["error"]["code"] == "PAYLOAD_TOO_LARGE"
    assert history_response.json()["error"]["details"] == {
        "max_message_characters": 8,
        "max_history_messages": 1,
        "max_history_characters": 6,
    }
    assert service.calls == 0


def test_abstention_stream_has_no_citations_and_completes() -> None:
    service = FixtureChatService(
        ChatDelivery(
            "fixture-index",
            "zh-TW",
            0,
            "目前可用的作品集證據不足以確認這個問題。",
            (),
            "stop",
            None,
            True,
        )
    )
    application = create_app(setup_state=ready_state(), chat_service=service)  # type: ignore[arg-type]

    with TestClient(application) as client:
        response = client.post(
            "/api/public/chat/stream", json={"message": "問題", "locale": "zh-TW"}
        )

    events = [
        line.removeprefix("event: ")
        for line in response.text.splitlines()
        if line.startswith("event: ")
    ]
    assert events == ["metadata", "token", "complete"]
    assert '"insufficient_evidence":true' in response.text


def test_midstream_internal_failure_emits_one_common_terminal_error(
    monkeypatch: object, caplog: object
) -> None:
    service = FixtureChatService(
        ChatDelivery("fixture-index", "en", 0, "Safe validated text.", (), "stop", None, False)
    )
    application = create_app(setup_state=ready_state(), chat_service=service)  # type: ignore[arg-type]

    def failing_events(*_args: object) -> object:
        yield (
            "metadata",
            {
                "request_id": "ignored-by-probe",
                "index_version": "fixture-index",
                "locale": "en",
                "evidence_count": 0,
            },
        )
        raise RuntimeError("MIDSTREAM_SECRET_CANARY_782dc2")

    monkeypatch.setattr("reponpc.api.public.delivery_events", failing_events)  # type: ignore[attr-defined]
    caplog.set_level(logging.ERROR, logger="reponpc.api.public")  # type: ignore[attr-defined]
    with TestClient(application) as client:
        response = client.post(
            "/api/public/chat/stream",
            headers={"X-Request-ID": "phase3-midstream-probe"},
            json={"message": "Question", "locale": "en"},
        )

    events = [
        line.removeprefix("event: ")
        for line in response.text.splitlines()
        if line.startswith("event: ")
    ]
    assert events == ["metadata", "error"]
    error_data = json.loads(response.text.split("event: error\ndata: ", 1)[1].split("\n", 1)[0])
    assert error_data["error"]["code"] == "REQUEST_FAILED"
    correlation_id = response.headers["x-request-id"]
    assert error_data["error"]["request_id"] == correlation_id
    assert "MIDSTREAM_SECRET_CANARY_782dc2" not in response.text
    assert "complete" not in events
    assert correlation_id in caplog.text  # type: ignore[attr-defined]
    assert "MIDSTREAM_SECRET_CANARY_782dc2" not in caplog.text  # type: ignore[attr-defined]


def test_first_event_is_constructed_within_250ms_after_validated_delivery(
    monkeypatch: object,
) -> None:
    service = FixtureChatService(
        ChatDelivery("fixture-index", "en", 0, "Safe validated text.", (), "stop", None, False)
    )
    observed_delay: list[float] = []
    delivery_ready_at = time.perf_counter()

    def timed_events(delivery: ChatDelivery, correlation_id: str) -> object:
        observed_delay.append(time.perf_counter() - delivery_ready_at)
        yield (
            "metadata",
            {
                "request_id": correlation_id,
                "index_version": delivery.index_version,
                "locale": delivery.locale,
                "evidence_count": delivery.evidence_count,
            },
        )
        yield (
            "complete",
            {
                "finish_reason": "stop",
                "usage": None,
                "insufficient_evidence": False,
            },
        )

    monkeypatch.setattr("reponpc.api.public.delivery_events", timed_events)  # type: ignore[attr-defined]
    application = create_app(setup_state=ready_state(), chat_service=service)  # type: ignore[arg-type]
    with TestClient(application) as client:
        delivery_ready_at = time.perf_counter()
        response = client.post(
            "/api/public/chat/stream", json={"message": "Question", "locale": "en"}
        )

    assert response.status_code == 200
    assert observed_delay and observed_delay[0] < 0.250


def test_public_boundary_enforces_overall_timeout_for_noncooperative_service() -> None:
    class SlowService(FixtureChatService):
        timeout_seconds = 0.01

        def answer(self, **kwargs: object) -> ChatDelivery:
            time.sleep(0.05)
            return super().answer(**kwargs)

    service = SlowService(
        ChatDelivery("fixture-index", "en", 0, "Too late.", (), "stop", None, False)
    )
    application = create_app(setup_state=ready_state(), chat_service=service)  # type: ignore[arg-type]

    with TestClient(application) as client:
        response = client.post(
            "/api/public/chat/stream", json={"message": "Question", "locale": "en"}
        )

    assert response.status_code == 200
    assert '"code":"REQUEST_TIMEOUT"' in response.text
    assert response.text.count("event: error") == 1 and "event: complete" not in response.text


def test_client_disconnect_cancels_worker_without_answer_events() -> None:
    started = threading.Event()
    release = threading.Event()
    cancellations: list[threading.Event] = []

    class BlockingService(FixtureChatService):
        timeout_seconds = 2.0

        def answer(self, **kwargs: object) -> ChatDelivery:
            cancellations.append(kwargs["cancel_requested"])  # type: ignore[arg-type]
            started.set()
            release.wait(1.0)
            return ChatDelivery("fixture-index", "en", 0, "Late answer.", (), "stop", None, False)

    service = BlockingService()
    application = create_app(setup_state=ready_state(), chat_service=service)  # type: ignore[arg-type]
    sent: list[dict[str, object]] = []
    receives = iter(
        [
            {
                "type": "http.request",
                "body": json.dumps({"message": "Question", "locale": "en"}).encode(),
                "more_body": False,
            },
            {"type": "http.disconnect"},
        ]
    )

    async def receive() -> dict[str, object]:
        try:
            return next(receives)
        except StopIteration:
            await asyncio.sleep(0.01)
            return {"type": "http.disconnect"}

    async def send(message: dict[str, object]) -> None:
        sent.append(message)

    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "POST",
        "scheme": "http",
        "path": "/api/public/chat/stream",
        "raw_path": b"/api/public/chat/stream",
        "query_string": b"",
        "root_path": "",
        "headers": [(b"content-type", b"application/json"), (b"host", b"test")],
        "client": ("203.0.113.9", 1234),
        "server": ("test", 80),
        "state": {},
    }

    async def exercise() -> None:
        task = asyncio.create_task(application(scope, receive, send))  # type: ignore[arg-type]
        assert await asyncio.to_thread(started.wait, 0.5)
        await asyncio.wait_for(task, timeout=0.5)
        release.set()
        await asyncio.sleep(0.05)

    asyncio.run(exercise())
    assert cancellations and cancellations[0].is_set()
    assert not any(b"event: token" in frame.get("body", b"") for frame in sent)


def test_local_chat_asgi_heartbeat_identity_and_usage_before_validated_answer() -> None:
    from tests.security.test_visitor_gateway_review import _HeldVisitorAnswer, _raw_asgi_request

    service = _HeldVisitorAnswer()
    application = create_app(setup_state=ready_state(), chat_service=service)  # type: ignore[arg-type]
    application.state.sse_keepalive_seconds = 0.01

    async def exercise() -> None:
        observed = asyncio.Event()
        captured: list[dict] = []

        def inspect(frame: dict) -> None:
            captured.append(frame)
            if frame.get("body", b"").startswith(b": keepalive"):
                observed.set()

        task = asyncio.create_task(
            _raw_asgi_request(
                application,
                raw_path=b"/api/public/chat/stream",
                method="POST",
                peer="203.0.113.9",
                headers=[(b"content-type", b"application/json")],
                body=b'{"message":"Question","locale":"en"}',
                on_send=inspect,
            )
        )
        try:
            await asyncio.wait_for(observed.wait(), 1)
            assert captured[0]["status"] == 200 and not service.finished.is_set()
            assert not any(b"event: token" in frame.get("body", b"") for frame in captured)
        finally:
            service.release.set()
        frames = await asyncio.wait_for(task, 1)
        payload = b"".join(frame.get("body", b"") for frame in frames)
        assert payload.count(b"event: complete") == 1 and b'"input_tokens":41' in payload
        assert service.calls[0]["client_ip"] == "203.0.113.9"
        assert service.calls[0]["allow_retry"] is True

    asyncio.run(exercise())
