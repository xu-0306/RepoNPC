"""Translation shares contribution authorization and keeps private text out of diagnostics."""

from __future__ import annotations

import traceback

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from reponpc.admin.onboarding import GuidedOnboardingError, ProfileTranslateRequest
from reponpc.i18n.languages import LANGUAGES
from reponpc.providers.contracts import ProviderError, ProviderFailureCode
from tests.integration.test_admin_onboarding import ORIGIN, _login
from tests.integration.test_admin_profile_translate import (
    OWNER_CANARY,
    ROUTE,
)
from tests.integration.test_admin_profile_translate import (
    translation_app as translation_app,
)
from tests.unit.test_profile_translate import _item


@pytest.mark.parametrize(
    ("access", "status", "code"),
    [
        ("unauthenticated", 401, "AUTHENTICATION_REQUIRED"),
        ("missing_csrf", 403, "CSRF_FAILED"),
        ("forged_csrf", 403, "CSRF_FAILED"),
        ("cross_origin", 403, "CSRF_FAILED"),
        ("missing_origin", 403, "CSRF_FAILED"),
        ("wrong_host", 403, "CSRF_FAILED"),
    ],
)
@pytest.mark.parametrize("target", [None, *(language for language in LANGUAGES if language.derive)])
def test_profile_translate_authorization_matches_contribution_suggest(
    translation_app, access: str, status: int, code: str, target
) -> None:
    app, _, _, state = translation_app
    with TestClient(app, base_url=ORIGIN) as client:
        headers = {"Origin": ORIGIN}
        if access != "unauthenticated":
            headers["X-CSRF-Token"] = _login(client)
        if access == "missing_csrf":
            headers.pop("X-CSRF-Token")
        elif access == "forged_csrf":
            headers["X-CSRF-Token"] = "forged"
        elif access == "cross_origin":
            headers["Origin"] = "https://attacker.example"
        elif access == "missing_origin":
            headers.pop("Origin")
        elif access == "wrong_host":
            headers["Host"] = "attacker.example"
        item = _item(text=OWNER_CANARY)
        if target is not None:
            assert target.derive is not None
            item.update(source_locale=target.derive.source, target_locale=target.tag)
        responses = [
            client.post(ROUTE, headers=headers, json={"items": [item]}),
            client.post(
                "/api/admin/onboarding/contributions/suggest",
                headers=headers,
                json={"slug": "octocat/demo", "owner_statement": OWNER_CANARY},
            ),
        ]
    assert [response.status_code for response in responses] == [status, status]
    assert [response.json()["error"]["code"] for response in responses] == [code, code]
    assert all(OWNER_CANARY not in response.text for response in responses)
    assert state["calls"] == []


@pytest.mark.parametrize("invalid", ["length", "duplicate", "extra", "locale"])
def test_profile_translate_strict_models_hide_owner_text_in_errors_and_repr(invalid: str) -> None:
    item = _item(text=OWNER_CANARY)
    valid = ProfileTranslateRequest.model_validate({"items": [item]})
    assert OWNER_CANARY not in repr(valid)
    if invalid == "length":
        item["text"] += "x" * 2000
    elif invalid == "extra":
        item["extra"] = OWNER_CANARY
    elif invalid == "locale":
        item["source_locale"] = "unknown"
    items = [item, dict(item)] if invalid == "duplicate" else [item]
    with pytest.raises(ValidationError) as error:
        ProfileTranslateRequest.model_validate({"items": items})
    assert OWNER_CANARY not in str(error.value)
    assert OWNER_CANARY not in repr(error.value)
    assert OWNER_CANARY not in "".join(traceback.format_exception(error.value))


@pytest.mark.parametrize("failure", ["request", "provider", "json", "schema"])
def test_profile_translate_safe_exception_has_no_private_cause_or_context(
    translation_app, failure: str
) -> None:
    _, _, onboarding, state = translation_app
    item = _item(text=OWNER_CANARY)
    if failure == "request":
        item["text"] += "x" * 2000
    elif failure == "provider":
        state["failure"] = ProviderError(
            ProviderFailureCode.INVALID_RESPONSE, upstream_message=OWNER_CANARY
        )
    elif failure == "json":
        state["content"] = OWNER_CANARY
    else:
        state["content"] = {"items": [OWNER_CANARY, "extra"]}
    with pytest.raises(GuidedOnboardingError) as error:
        onboarding.translate_profile(session_hash="session-a", items=[item])
    assert error.value.__cause__ is None
    assert error.value.__context__ is None
    assert OWNER_CANARY not in str(error.value)
    assert OWNER_CANARY not in repr(error.value)
    assert OWNER_CANARY not in "".join(traceback.format_exception(error.value))
    assert len(state["calls"]) == (0 if failure == "request" else 1)


def test_profile_translate_failure_releases_permit_and_session_without_retry(
    translation_app,
) -> None:
    _, _, onboarding, state = translation_app
    state["failure"] = ProviderError(ProviderFailureCode.TIMEOUT)
    with pytest.raises(GuidedOnboardingError) as error:
        onboarding.translate_profile(session_hash="session-a", items=[_item()])
    assert error.value.code == "PROVIDER_TIMEOUT"
    assert len(state["calls"]) == 1
    state["failure"] = None
    result = onboarding.translate_profile(session_hash="session-a", items=[_item()])
    assert result["items"][0]["method"] == "model"
    assert len(state["calls"]) == 2
