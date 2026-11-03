"""Admin locale boundaries use prepared content first, then the saved owner configuration."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest
from fastapi.testclient import TestClient

from reponpc.admin.faq import ReviewedFaq
from reponpc.admin.local_portfolio import LocalPortfolioStore
from reponpc.admin.scene import AdminSceneService
from reponpc.api.admin import OnboardingDraftRequest, create_admin_router
from reponpc.i18n.languages import language_tags
from reponpc.i18n.plan import ANALYSIS_LOCALES, LocaleNotEnabledError
from tests.integration.test_admin_onboarding import ORIGIN, _application, _login
from tests.integration.test_admin_profile_translate import translation_app as translation_app
from tests.unit.test_guided_onboarding import _service
from tests.unit.test_onboarding_languages import SITE_SETS, LanguageChat, draft_payload


class RecordingFaq:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []
        self.fail = False

    def view(self, locale):
        return self._result("view", locale)

    def public_payload(self, locale):
        return self._result("export", locale)

    def initialize_queue(self, locale):
        return self._result("queue", locale)

    def _result(self, operation, locale):
        if self.fail:
            raise LocaleNotEnabledError("disabled by service")
        self.calls.append((operation, locale))
        return {"locale": locale, "entries": []}


class PreparedScene:
    def __init__(self, locales: tuple[str, ...] = ANALYSIS_LOCALES, schema_version: int = 1):
        self.locales = locales
        self.schema_version = schema_version

    @contextmanager
    def published_profile(self):
        yield SimpleNamespace(
            document=SimpleNamespace(
                locales=dict.fromkeys(self.locales), schema_version=self.schema_version
            )
        )


def _locale_application(tmp_path: Path, site, monkeypatch: pytest.MonkeyPatch):
    application, _ = _application(tmp_path / "auth")
    # Keep create_app's real validation/error handlers; supply only the admin dependencies.
    auth = application.state.admin_session_service
    operations = application.state.admin_operations
    service, _, _, _ = _service(tmp_path / "onboarding")
    body = OnboardingDraftRequest.model_validate(draft_payload(site))
    draft = service.create_draft(
        profile=body.profile,
        repositories=body.repositories,
        locales=body.locales,
        base_config=None,
        confirmed_assertions=True,
    )
    store = LocalPortfolioStore(tmp_path / "portfolio")
    store.save(content=draft["content"], sprite_base64=None, expected_revision=None)
    operations = replace(operations, local_portfolio=store)
    application.state.admin_operations = operations
    faq = RecordingFaq()
    scene = PreparedScene()
    prepared = SimpleNamespace(active_bundle_id=None)
    application.state.bundle_manager = SimpleNamespace(status=lambda: prepared)
    calls: list[str] = []

    class Sharing:
        def __init__(self, **kwargs: Any):
            pass

        def readme(self, *, web_dist, locale):
            calls.append(locale)
            return "README " + locale

    def snippet(**kwargs: Any) -> str:
        return f"[![RepoNPC]({ORIGIN}/api/public/card.svg?locale={kwargs['locale']})]({ORIGIN}/)"

    monkeypatch.setattr("reponpc.api.admin.PagesSharingService", Sharing)
    monkeypatch.setattr("reponpc.api.admin._mounted_web_directory", lambda request: tmp_path)
    # Card rendering belongs to W1; isolate this worker's locale validation and dispatch.
    monkeypatch.setattr("reponpc.admin.operations.render_readme_snippet", snippet)
    application.router.routes = []
    application.include_router(
        create_admin_router(
            service_supplier=lambda: auth,
            origins_supplier=lambda: (ORIGIN,),
            operations_supplier=lambda: operations,
            faq_supplier=lambda: cast(ReviewedFaq, faq),
            scene_supplier=lambda: cast(AdminSceneService, scene),
            gateway_supplier=lambda: cast(Any, object()),
        )
    )
    return application, faq, calls, scene, prepared


def _requests(client, csrf, locale: str | None):
    headers = {"Origin": ORIGIN, "X-CSRF-Token": csrf}
    params = {} if locale is None else {"locale": locale}
    return [
        client.get("/api/admin/portfolio/faq", params=params, headers=headers),
        client.get("/api/admin/portfolio/faq/export", params=params, headers=headers),
        client.post("/api/admin/portfolio/faq/check", json=params, headers=headers),
        client.get("/api/admin/sharing/readme", params=params, headers=headers),
        client.get(
            "/api/admin/readme-snippet",
            params={**params, "theme": "light", "extension": "svg", "revision": 1},
            headers=headers,
        ),
    ]


@pytest.mark.parametrize("site", SITE_SETS, ids=lambda site: ",".join(site))
def test_admin_locales_follow_saved_set_and_default(tmp_path: Path, site, monkeypatch) -> None:
    app, faq, calls, _, _ = _locale_application(tmp_path, site, monkeypatch)
    with TestClient(app, base_url=ORIGIN) as client:
        csrf = _login(client)
        for locale in (None, *site):
            resolved = site[-1] if locale is None else locale
            responses = _requests(client, csrf, locale)
            assert [response.status_code for response in responses] == [200] * 5
            assert all(response.headers["cache-control"] == "no-store" for response in responses)
            assert [response.json()["locale"] for response in responses[:3]] == [resolved] * 3
            assert f"faq-{resolved}.json" in responses[1].headers["content-disposition"]
            assert responses[3].text == "README " + resolved
            assert "locale=" + resolved in responses[4].json()["asset_url"]
            assert faq.calls[-3:] == [
                (operation, resolved) for operation in ("view", "export", "queue")
            ]
            assert calls[-1] == resolved
        prior = list(faq.calls), list(calls)
        for locale in ("unknown", *(tag for tag in language_tags() if tag not in site)):
            responses = _requests(client, csrf, locale)
            assert [response.status_code for response in responses] == [400] * 5
            assert all(
                response.json()["error"]["code"] == "VALIDATION_ERROR" for response in responses
            )
            assert [response.json()["error"]["details"] for response in responses] == [
                {
                    "fields": [
                        {
                            "path": ("body.locale" if index == 2 else "query.locale"),
                            "code": "invalid",
                        }
                    ]
                }
                for index in range(5)
            ]
        assert (faq.calls, calls) == prior


@pytest.mark.parametrize("site", SITE_SETS)
def test_explicit_admin_locale_uses_prepared_set_even_when_saved_set_differs(
    tmp_path: Path, site, monkeypatch
) -> None:
    saved = (next(tag for tag in language_tags() if tag != site[0]),)
    app, faq, calls, scene, prepared = _locale_application(tmp_path, saved, monkeypatch)
    scene.locales = site
    scene.schema_version = 2
    prepared.active_bundle_id = "prepared-bundle"
    with TestClient(app, base_url=ORIGIN) as client:
        csrf = _login(client)
        for locale in site:
            responses = _requests(client, csrf, locale)
            assert [response.status_code for response in responses] == [200] * 5
            assert [response.json()["locale"] for response in responses[:3]] == [locale] * 3
            assert calls[-1] == locale
        prior = list(faq.calls), list(calls)
        for locale in ("unknown", *(tag for tag in language_tags() if tag not in site)):
            assert [response.status_code for response in _requests(client, csrf, locale)] == [
                400
            ] * 5
        assert (faq.calls, calls) == prior


def test_legacy_prepared_default_and_service_locale_error_mapping(
    tmp_path: Path, monkeypatch
) -> None:
    app, faq, calls, _, prepared = _locale_application(
        tmp_path, tuple(reversed(ANALYSIS_LOCALES)), monkeypatch
    )
    prepared.active_bundle_id = "legacy-bundle"
    with TestClient(app, base_url=ORIGIN) as client:
        csrf = _login(client)
        responses = _requests(client, csrf, None)
        assert [response.status_code for response in responses] == [200] * 5
        assert [response.json()["locale"] for response in responses[:3]] == [
            ANALYSIS_LOCALES[0]
        ] * 3
        assert calls[-1] == ANALYSIS_LOCALES[0]
        faq.fail = True
        for response in _requests(client, csrf, ANALYSIS_LOCALES[0])[:3]:
            assert response.status_code == 400
            assert response.json()["error"]["code"] == "VALIDATION_ERROR"
            assert response.json()["error"]["details"]["fields"][0]["path"].endswith(".locale")
            assert response.json()["error"]["details"]["fields"][0]["code"] == "invalid"


@pytest.mark.parametrize("site", SITE_SETS)
def test_new_suggest_and_draft_fields_reach_real_onboarding_services(
    translation_app, tmp_path, site
) -> None:
    app, _, onboarding, _ = translation_app
    chat = LanguageChat()
    service, _, _, _ = _service(tmp_path / "suggest", chat=chat)
    app.state.admin_operations = replace(app.state.admin_operations, onboarding=service)
    with TestClient(app, base_url=ORIGIN) as client:
        csrf = _login(client)
        headers = {"Origin": ORIGIN, "X-CSRF-Token": csrf}
        suggestion = client.post(
            "/api/admin/onboarding/contributions/suggest",
            headers=headers,
            json={"slug": "octocat/demo", "owner_statement": "Owner tools", "locales": site},
        )
        assert suggestion.status_code == 200
        assert tuple(suggestion.json()["proposal"]["role"]) == site
        draft = client.post(
            "/api/admin/onboarding/draft", headers=headers, json=draft_payload(site)
        )
        assert draft.status_code == 200
        parsed = draft.json()["validation"]["parsed"]
        assert parsed["locales"] == {"default": site[-1], "supported": list(site)}
        assert tuple(parsed["profile"]["headline"]) == site
        assert tuple(parsed["card"]["call_to_action"]) == site
    assert chat.calls == 1
    assert onboarding._active_sessions == set()
