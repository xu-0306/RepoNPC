from __future__ import annotations

import json
import logging

from reponpc.observability.logging import SafeLogger


class CapturingHandler(logging.Handler):
    def __init__(self) -> None:
        super().__init__()
        self.messages: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.messages.append(record.getMessage())


class FailingHandler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        raise RuntimeError("LOG_HANDLER_SECRET_CANARY")


def configured_logger(handler: logging.Handler) -> logging.Logger:
    logger = logging.getLogger(f"reponpc.test.safe_logging.{id(handler)}")
    logger.handlers[:] = [handler]
    logger.setLevel(logging.INFO)
    logger.propagate = False
    return logger


def test_safe_logger_preserves_allowlisted_diagnostics_and_omits_nested_canaries() -> None:
    handler = CapturingHandler()
    safe_logger = SafeLogger(configured_logger(handler))
    canaries = (
        "TOKEN_CANARY",
        "PASSWORD_CANARY",
        "COOKIE_CANARY",
        "CSRF_CANARY",
        "PROMPT_CANARY",
        "ANSWER_CANARY",
        "203.0.113.9",
        "https://private.example.invalid/v1",
        "C:\\private\\secrets.txt",
        "/srv/private/secrets.txt",
    )

    safe_logger.emit(
        logging.INFO,
        "provider.request.completed",
        request_id="request-123",
        route_template="/api/public/status",
        status=200,
        latency_ms=12.5,
        index_version="20260810-abcdef",
        provider_adapter="ollama",
        provider_model="qwen3:8b",
        retrieval_count=8,
        retrieval_ranks=[1, 2, 3],
        input_tokens=11,
        output_tokens=7,
        rate_outcome="accepted",
        error_category="unavailable",
        token="TOKEN_CANARY",
        private_url="https://private.example.invalid/v1",
        request={"answer": "ANSWER_CANARY", "nested": list(canaries)},
        exception=RuntimeError("PASSWORD_CANARY"),
    )

    assert len(handler.messages) == 1
    rendered = handler.messages[0]
    payload = json.loads(rendered)
    assert payload["event"] == "provider.request.completed"
    assert payload["request_id"] == "request-123"
    assert payload["retrieval_ranks"] == [1, 2, 3]
    assert "token" not in payload
    assert "request" not in payload
    assert "exception" not in payload
    assert all(canary not in rendered for canary in canaries)


def test_safe_logger_redacts_private_values_in_allowlisted_text_fields() -> None:
    handler = CapturingHandler()
    safe_logger = SafeLogger(configured_logger(handler))

    safe_logger.emit(
        logging.ERROR,
        "provider.failed",
        request_id="198.51.100.44",
        provider_model="https://private.example.invalid/model",
        retrieval_ranks=[1] * 100,
        error_category="internal",
    )

    payload = json.loads(handler.messages[0])
    assert payload["request_id"] == "<redacted>"
    assert payload["provider_model"] == "<redacted>"
    assert payload["retrieval_ranks"] == [1] * 20


def test_safe_logger_redacts_posix_paths_in_allowlisted_text_fields() -> None:
    handler = CapturingHandler()
    safe_logger = SafeLogger(configured_logger(handler))
    canary = "/tmp"

    safe_logger.emit(logging.INFO, "provider.started", provider_model=canary)

    payload = json.loads(handler.messages[0])
    assert payload["provider_model"] == "<redacted>"
    assert canary not in handler.messages[0]


def test_safe_logger_ignores_invalid_event_and_does_not_raise_when_logging_fails() -> None:
    safe_logger = SafeLogger(configured_logger(FailingHandler()))

    safe_logger.emit(logging.INFO, "PROMPT_CANARY")
