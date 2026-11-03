"""HTTP translation reaches real onboarding/runtime services and the existing fake provider."""

from __future__ import annotations

import json
import logging
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from argon2 import PasswordHasher, Type
from fastapi.testclient import TestClient

from reponpc.admin.auth import AdminSessionService
from reponpc.admin.onboarding import GuidedOnboardingService
from reponpc.admin.operations import AdminOperations
from reponpc.chat.limits import ChatLimits
from reponpc.i18n.languages import LANGUAGES
from reponpc.main import create_app
from reponpc.providers.contracts import (
    ProviderError,
    ProviderFailureCode,
    ProviderHealth,
    ProviderResult,
)
from reponpc.providers.runtime import ProviderRuntime
from reponpc.runtime.database import RuntimeDatabase
from tests.integration.test_admin_onboarding import ORIGIN, PASSWORD, _login
from tests.integration.test_provider_lifecycle import LifecycleChat, LifecycleEmbedding
from tests.unit.test_guided_onboarding import FakeResolver
from tests.unit.test_profile_translate import INVALID_ITEMS, _item

ROUTE = "/api/admin/onboarding/profile/translate"
OWNER_CANARY = "SYNTHETIC_OWNER_PROFILE_TRANSLATE_CANARY"
OUTPUT_CANARY = "SYNTHETIC_PROVIDER_TRANSLATION_CANARY"


@pytest.fixture
def translation_app(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    database = RuntimeDatabase(tmp_path / "runtime")
    database.initialize()
    ready = ProviderHealth(True, "2026-11-03T00:00:00Z")
    chat = LifecycleChat(ready)
    state: dict[str, Any] = {
        "content": {"items": ["Translated profile."]},
        "failure": None,
        "finish_reason": "stop",
        "calls": [],
    }

    def generate(messages, response_schema, max_output_tokens, timeout):
        state["calls"].append((messages, response_schema, max_output_tokens, timeout))
        if state["failure"] is not None:
            raise state["failure"]
        return ProviderResult(state["content"], state["finish_reason"], None, None, 1.0)

    monkeypatch.setattr(chat, "generate", generate)
    runtime = ProviderRuntime(chat=chat, embedding=LifecycleEmbedding(ready))
    limits = ChatLimits(
        database,
        ip_hash_key=b"translation-fixture",
        requests_per_minute=1,
        daily_budget=1,
        global_concurrency=1,
    )
    onboarding = GuidedOnboardingService(
        source_resolver=FakeResolver(),
        providers_supplier=lambda: None,
        contribution_providers_supplier=lambda: runtime,
        limits_supplier=lambda: limits,
        staging_root=tmp_path / "staging",
        provider_timeout_seconds=45,
    )
    auth = AdminSessionService(
        database=database,
        username="admin",
        password_hash=PasswordHasher(type=Type.ID).hash(PASSWORD),
        identity_hmac_key=b"t" * 32,
        now=lambda: datetime(2026, 11, 3, tzinfo=UTC),
    )
    app = create_app(
        admin_session_service=auth,
        admin_origins=(ORIGIN,),
        admin_operations=AdminOperations(database, ORIGIN, onboarding=onboarding),
    )
    return app, database, onboarding, state


@pytest.mark.parametrize(
    ("source", "target"),
    [(source, target) for source in LANGUAGES for target in LANGUAGES if source != target],
    ids=lambda language: language.tag,
)
def test_profile_translate_http_end_to_end_uses_selected_model_and_exact_response(
    translation_app, source, target
) -> None:
    app, _, onboarding, state = translation_app
    translated = "我協助維護工具。" if "CJK" in target.scripts else "I help maintain tools."
    state["content"] = json.dumps({"items": [translated]}, ensure_ascii=False)
    item = _item(source_locale=source.tag, target_locale=target.tag, text="I help maintain tools.")
    with TestClient(app, base_url=ORIGIN) as client:
        csrf = _login(client)
        response = client.post(
            ROUTE, headers={"Origin": ORIGIN, "X-CSRF-Token": csrf}, json={"items": [item]}
        )
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.json() == {
        "items": [
            {
                "field": item["field"],
                "target_locale": target.tag,
                "text": translated,
                "method": "model",
                "confirmed": False,
            }
        ]
    }
    [(messages, schema, budget, timeout)] = state["calls"]
    assert item["text"] in messages[-1].content
    assert source.tag in messages[-1].content and target.tag in messages[-1].content
    assert (
        schema["properties"]["items"]["minItems"] == schema["properties"]["items"]["maxItems"] == 1
    )
    assert budget == 16384 and timeout == 45
    assert onboarding._active_sessions == set()


def test_profile_translate_http_validation_matrix_never_calls_provider(translation_app) -> None:
    app, _, _, state = translation_app
    payloads = [
        *[{"items": items} for items in INVALID_ITEMS],
        {},
        {"items": None},
        {"items": {}},
        {"items": "profile"},
        {"items": [_item()], "confirmed": True},
    ]
    with TestClient(app, base_url=ORIGIN) as client:
        csrf = _login(client)
        for payload in payloads:
            response = client.post(
                ROUTE, headers={"Origin": ORIGIN, "X-CSRF-Token": csrf}, json=payload
            )
            assert response.status_code == 400
            assert response.json()["error"]["code"] == "VALIDATION_ERROR"
            assert "items" not in response.json()
    assert state["calls"] == []


@pytest.mark.parametrize(
    ("failure", "status", "code"),
    [
        (ProviderFailureCode.TIMEOUT, 504, "PROVIDER_TIMEOUT"),
        (ProviderFailureCode.UNAVAILABLE, 503, "MODEL_UNAVAILABLE"),
        *[
            (failure, 502, "PROVIDER_ERROR")
            for failure in ProviderFailureCode
            if failure not in {ProviderFailureCode.TIMEOUT, ProviderFailureCode.UNAVAILABLE}
        ],
    ],
)
def test_profile_translate_http_preserves_provider_error_mapping(
    translation_app, failure: ProviderFailureCode, status: int, code: str
) -> None:
    app, _, _, state = translation_app
    state["failure"] = ProviderError(failure)
    with TestClient(app, base_url=ORIGIN) as client:
        csrf = _login(client)
        response = client.post(
            ROUTE, headers={"Origin": ORIGIN, "X-CSRF-Token": csrf}, json={"items": [_item()]}
        )
    assert response.status_code == status
    assert response.json()["error"]["code"] == code
    assert "items" not in response.json()
    assert len(state["calls"]) == 1


@pytest.mark.parametrize(
    ("content", "finish_reason", "reason"),
    [
        ({"items": ["Valid JSON"]}, "length", "PROVIDER_OUTPUT_LIMIT_REACHED"),
        (
            {"items": ["First valid", "Second invalid", "extra"]},
            "stop",
            "PROVIDER_OUTPUT_SCHEMA_INVALID",
        ),
        ({"items": ["First valid", " "]}, "stop", "PROVIDER_OUTPUT_SCHEMA_INVALID"),
        ({"items": ["First valid", "x" * 2001]}, "stop", "PROVIDER_OUTPUT_SCHEMA_INVALID"),
        ({"items": ["First valid", "Missing reference"]}, "stop", "PROVIDER_OUTPUT_SCHEMA_INVALID"),
    ],
)
def test_profile_translate_http_never_returns_partial_items(
    translation_app, content: Any, finish_reason: str, reason: str
) -> None:
    app, _, _, state = translation_app
    state.update(content=content, finish_reason=finish_reason)
    items = [_item(), _item(field="headline", text="I work on acme/another-project")]
    with TestClient(app, base_url=ORIGIN) as client:
        csrf = _login(client)
        response = client.post(
            ROUTE, headers={"Origin": ORIGIN, "X-CSRF-Token": csrf}, json={"items": items}
        )
    assert response.status_code == 502
    assert response.json()["error"]["code"] == "PROVIDER_ERROR"
    assert response.json()["error"]["details"] == {"reason": reason}
    assert "items" not in response.json()
    assert len(state["calls"]) == 1


@pytest.mark.parametrize(
    "outcome", ["success", "invalid_output", "provider_error", "invalid_request"]
)
def test_profile_translate_never_logs_or_stores_owner_text(
    translation_app, tmp_path: Path, caplog: pytest.LogCaptureFixture, outcome: str
) -> None:
    app, database, onboarding, state = translation_app
    text = OWNER_CANARY
    if outcome == "invalid_output":
        state["content"] = {"items": [OUTPUT_CANARY, "extra"]}
    elif outcome == "provider_error":
        state["failure"] = ProviderError(
            ProviderFailureCode.INVALID_RESPONSE, upstream_message=OWNER_CANARY + OUTPUT_CANARY
        )
    elif outcome == "invalid_request":
        text += "x" * 2000
    else:
        state["content"] = {"items": [OUTPUT_CANARY]}
    with TestClient(app, base_url=ORIGIN) as client, caplog.at_level(logging.DEBUG):
        csrf = _login(client)
        response = client.post(
            ROUTE,
            headers={"Origin": ORIGIN, "X-CSRF-Token": csrf},
            json={"items": [_item(text=text)]},
        )
        assert response.status_code == (
            200 if outcome == "success" else 400 if outcome == "invalid_request" else 502
        )
    with database.connection() as connection:
        stored_state = "\n".join(connection.iterdump())
    for canary in (OWNER_CANARY, OUTPUT_CANARY):
        assert canary not in caplog.text
        assert canary not in stored_state
        assert canary not in repr(onboarding.__dict__)
        for path in tmp_path.rglob("*"):
            if path.is_file():
                assert canary.encode() not in path.read_bytes()
        if outcome != "success":
            assert canary not in response.text
    assert len(state["calls"]) == (0 if outcome == "invalid_request" else 1)
    assert onboarding._active_sessions == set()


def test_profile_translate_http_unconfigured_onboarding_uses_existing_error(
    translation_app,
) -> None:
    app, _, _, state = translation_app
    app.state.admin_operations = replace(app.state.admin_operations, onboarding=None)
    with TestClient(app, base_url=ORIGIN) as client:
        csrf = _login(client)
        response = client.post(
            ROUTE, headers={"Origin": ORIGIN, "X-CSRF-Token": csrf}, json={"items": [_item()]}
        )
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "SERVICE_NOT_READY"
    assert state["calls"] == []
