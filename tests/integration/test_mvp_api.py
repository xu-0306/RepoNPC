from __future__ import annotations

import json
import re
import uuid
from pathlib import Path

from fastapi.testclient import TestClient
from httpx import Response

from reponpc.api.public import SetupState
from reponpc.main import app, create_app
from reponpc.runtime.database import RuntimeDatabase

UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$")


def assert_public_headers(response: Response) -> None:
    headers = response.headers
    assert UUID_RE.fullmatch(headers["X-Request-ID"])
    assert headers["Cache-Control"] == "no-store"
    assert headers["X-Content-Type-Options"] == "nosniff"
    assert headers["X-Frame-Options"] == "DENY"
    assert "frame-ancestors 'none'" in headers["Content-Security-Policy"]


def test_health_is_alive_but_readiness_fails_before_bundle_activation() -> None:
    with TestClient(app) as client:
        health = client.get("/healthz")
        readiness = client.get("/readyz")

    assert health.status_code == 200
    assert health.json() == {"status": "alive"}
    assert_public_headers(health)

    assert readiness.status_code == 503
    assert readiness.json()["error"]["code"] == "SERVICE_NOT_READY"
    assert readiness.json()["error"]["request_id"] == readiness.headers["X-Request-ID"]
    assert_public_headers(readiness)


def test_setup_status_is_public_and_contains_no_sensitive_diagnostics() -> None:
    with TestClient(app) as client:
        response = client.get("/api/public/status")

    assert response.status_code == 200
    assert response.json() == {
        "status": "setup_required",
        "index": {
            "ready": False,
            "version": None,
            "last_checked_at": None,
            "update_error": None,
        },
        "model": {"ready": False, "provider": None, "last_checked_at": None},
        "chat_available": False,
    }
    serialized = response.text.casefold()
    for forbidden in ("password", "token", "api_key", "base_url", "traceback", "d:\\"):
        assert forbidden not in serialized
    assert_public_headers(response)


def test_setup_status_sanitizes_untrusted_internal_state_strings() -> None:
    canary = "EVAL-PRIVATE-PROVIDER-URL-http://ollama.internal:11434"
    unsafe_app = create_app(
        setup_state=SetupState(
            index_ready=True,
            index_version=canary,
            index_last_checked_at=canary,
            model_ready=False,
            model_provider=canary,
            model_last_checked_at=canary,
        )
    )

    with TestClient(unsafe_app) as client:
        response = client.get("/api/public/status")

    assert response.status_code == 200
    assert canary not in response.text
    assert response.json()["index"]["version"] is None
    assert response.json()["index"]["last_checked_at"] is None
    assert response.json()["model"]["provider"] is None
    assert response.json()["model"]["last_checked_at"] is None
    assert_public_headers(response)


def test_status_distinguishes_degraded_and_ready_capabilities() -> None:
    degraded_app = create_app(
        setup_state=SetupState(
            index_ready=True,
            index_version="fixture-v1",
            model_ready=False,
        )
    )
    ready_app = create_app(
        setup_state=SetupState(
            index_ready=True,
            index_version="fixture-v1",
            index_last_checked_at="2026-08-10T15:30:00+08:00",
            model_ready=True,
            model_provider="ollama",
            model_last_checked_at="2026-08-10T15:30:01+08:00",
        )
    )

    with TestClient(degraded_app) as client:
        degraded = client.get("/api/public/status")
        degraded_readiness = client.get("/readyz")
    with TestClient(ready_app) as client:
        ready = client.get("/api/public/status")
        ready_readiness = client.get("/readyz")

    assert degraded.json()["status"] == "degraded"
    assert degraded.json()["chat_available"] is False
    assert degraded_readiness.status_code == 503
    assert ready.json()["status"] == "ready"
    assert ready.json()["chat_available"] is True
    assert ready.json()["index"]["version"] == "fixture-v1"
    assert ready.json()["index"]["last_checked_at"] == "2026-08-10T15:30:00+08:00"
    assert ready.json()["model"]["provider"] == "ollama"
    assert ready.json()["model"]["last_checked_at"] == "2026-08-10T15:30:01+08:00"
    assert ready_readiness.status_code == 200


def test_runtime_migration_failure_degrades_readiness_without_breaking_health(tmp_path) -> None:
    data_dir = tmp_path / "runtime"
    data_dir.mkdir()
    (data_dir / "runtime.sqlite").write_bytes(b"not a sqlite database")
    runtime_failure_app = create_app(
        setup_state=SetupState(
            index_ready=True,
            index_version="fixture-v1",
            model_ready=True,
            model_provider="ollama",
        ),
        runtime_database=RuntimeDatabase(data_dir),
    )

    with TestClient(runtime_failure_app) as client:
        health = client.get("/healthz")
        status = client.get("/api/public/status")
        readiness = client.get("/readyz")

    assert health.status_code == 200
    assert status.json()["status"] == "degraded"
    assert status.json()["chat_available"] is False
    assert readiness.status_code == 503


def test_profile_reports_localized_index_unavailable_errors() -> None:
    with TestClient(app) as client:
        zh_tw = client.get("/api/public/profile", params={"locale": "zh-TW"})
        en = client.get("/api/public/profile", params={"locale": "en"})

    assert zh_tw.status_code == en.status_code == 503
    assert zh_tw.json()["error"]["code"] == "INDEX_UNAVAILABLE"
    assert en.json()["error"]["code"] == "INDEX_UNAVAILABLE"
    assert zh_tw.json()["error"]["message"] == "索引目前無法使用。"
    assert en.json()["error"]["message"] == "The index is currently unavailable."
    for response in (zh_tw, en):
        error = response.json()["error"]
        assert error["request_id"] == response.headers["X-Request-ID"]
        assert error["details"] == {}
        assert error["retry_after_seconds"] is None
        assert_public_headers(response)


def test_request_id_preserves_valid_uuid_and_replaces_invalid_value() -> None:
    supplied = str(uuid.uuid4())
    with TestClient(app) as client:
        preserved = client.get("/healthz", headers={"X-Request-ID": supplied})
        replaced = client.get("/healthz", headers={"X-Request-ID": "not-a-uuid"})

    assert preserved.headers["X-Request-ID"] == supplied
    assert replaced.headers["X-Request-ID"] != "not-a-uuid"
    assert UUID_RE.fullmatch(replaced.headers["X-Request-ID"])


def test_unsupported_locale_uses_safe_field_error_without_echoing_value() -> None:
    canary = "CANARY-LOCALE-DO-NOT-ECHO"
    with TestClient(app) as client:
        response = client.get("/api/public/profile", params={"locale": canary})

    assert response.status_code == 400
    error = response.json()["error"]
    assert error["code"] == "VALIDATION_ERROR"
    assert error["details"] == {"fields": [{"path": "locale", "code": "unsupported_locale"}]}
    assert canary not in response.text
    assert_public_headers(response)


def _active_public_directory(tmp_path: Path) -> tuple[Path, dict[str, dict[str, object]]]:
    directory = tmp_path / "public"
    directory.mkdir()
    locales = {
        locale: {
            "profile": {
                "display_name": "Fixture Developer",
                "headline": "Traditional headline" if locale == "zh-TW" else "English headline",
                "bio": "Traditional bio" if locale == "zh-TW" else "English bio",
                "greeting": "Traditional greeting" if locale == "zh-TW" else "English greeting",
                "location": None,
                "avatar_url": None,
                "links": [],
            },
            "repositories": [
                {
                    "slug": "fixture-owner/reponpc-demo",
                    "summary": "Traditional summary" if locale == "zh-TW" else "English summary",
                    "role": "Traditional role" if locale == "zh-TW" else "English role",
                    "tags": ["Python"],
                    "demo_url": None,
                }
            ],
            "suggested_questions": [
                "Traditional question?" if locale == "zh-TW" else "English question?"
            ],
        }
        for locale in ("zh-TW", "en")
    }
    character = {
        "mode": "builtin",
        "asset_url": "/api/public/character.png",
        "revision": 1,
        "frame_duration_ms": 160,
        "movement": "subtle",
    }
    index = {
        "version": "bundle-one",
        "built_at": "2026-08-10T12:00:00Z",
        "repository_count": 1,
    }
    internal = {"schema_version": 1, "locales": locales, "character": character, "index": index}
    (directory / "profile.json").write_text(
        json.dumps(internal, ensure_ascii=False), encoding="utf-8"
    )
    (directory / "character.png").write_bytes(b"same-payload")
    for theme in ("light", "dark"):
        for locale in ("zh-TW", "en"):
            for extension in ("svg", "gif", "png"):
                (directory / f"card-{theme}-{locale}.{extension}").write_bytes(b"same-payload")
    responses = {
        locale: {
            "schema_version": 1,
            "locale": locale,
            **payload,
            "character": character,
            "index": index,
        }
        for locale, payload in locales.items()
    }
    return directory, responses


def test_degraded_active_public_assets_validate_variants_and_cache_identity(tmp_path: Path) -> None:
    directory, profiles = _active_public_directory(tmp_path)
    active = SetupState(
        index_ready=True, index_version="bundle-one", model_ready=False, public_directory=directory
    )
    app_one = create_app(setup_state=active)
    with TestClient(app_one) as client:
        first_profile = client.get("/api/public/profile?locale=en")
        repeated_profile = client.get("/api/public/profile?locale=en")
        assert first_profile.status_code == repeated_profile.status_code == 200
        assert first_profile.json() == profiles["en"]
        assert first_profile.json()["profile"]["greeting"] == "English greeting"
        assert first_profile.json()["character"]["frame_duration_ms"] == 160
        assert first_profile.json()["character"]["movement"] == "subtle"
        assert first_profile.headers["content-type"] == "application/json"
        assert first_profile.headers["ETag"] == repeated_profile.headers["ETag"]
        assert (
            first_profile.headers["ETag"]
            != client.get("/api/public/profile?locale=zh-TW").headers["ETag"]
        )
        character = client.get("/api/public/character.png?rev=1")
        assert character.status_code == 200 and character.headers["content-type"] == "image/png"
        assert (
            character.headers["ETag"]
            != client.get("/api/public/character.png?rev=2").headers["ETag"]
        )
        svg = None
        for theme in ("light", "dark"):
            for locale in ("zh-TW", "en"):
                for extension, content_type in (
                    ("svg", "image/svg+xml"),
                    ("gif", "image/gif"),
                    ("png", "image/png"),
                ):
                    response = client.get(
                        f"/api/public/card.{extension}?theme={theme}&locale={locale}&rev=1"
                    )
                    assert response.status_code == 200
                    assert response.headers["content-type"] == content_type
                    if extension == "svg":
                        svg = response
        assert svg is not None
        assert (
            svg.headers["Content-Security-Policy"]
            == "default-src 'none'; style-src 'unsafe-inline'; img-src data:"
        )
        assert svg.headers["X-Content-Type-Options"] == "nosniff"
        assert "frame-ancestors" not in svg.headers["Content-Security-Policy"]
        assert "frame-ancestors 'none'" in character.headers["Content-Security-Policy"]
        for query in (
            "locale=en&locale=zh-TW",
            "locale=en&theme=bad",
            "locale=en&rev=0",
            "locale=en&rev=01",
            "locale=en&rev=1234567890",
            "locale=en&rev=x",
            "locale=en&extra=x",
            "locale=CANARY",
        ):
            response = client.get(f"/api/public/card.svg?{query}")
            assert response.status_code == 400 and "CANARY" not in response.text
        assert client.get("/api/public/card.bad?locale=en").status_code == 400
    app_two = create_app(
        setup_state=SetupState(
            index_ready=True,
            index_version="bundle-two",
            model_ready=False,
            public_directory=directory,
        )
    )
    with TestClient(app_two) as client:
        mismatched_profile = client.get("/api/public/profile?locale=en")
        assert mismatched_profile.status_code == 503
        assert mismatched_profile.json()["error"]["code"] == "INDEX_UNAVAILABLE"
    (directory / "character.png").write_bytes(b"")
    with TestClient(app_one) as client:
        assert client.get("/api/public/character.png").status_code == 503


def test_profile_missing_required_locale_fails_closed_without_cross_fallback(
    tmp_path: Path,
) -> None:
    directory, _ = _active_public_directory(tmp_path)
    profile_path = directory / "profile.json"
    internal = json.loads(profile_path.read_text(encoding="utf-8"))
    del internal["locales"]["en"]
    profile_path.write_text(json.dumps(internal), encoding="utf-8")
    active = SetupState(
        index_ready=True,
        index_version="bundle-one",
        public_directory=directory,
    )

    with TestClient(create_app(setup_state=active)) as client:
        assert client.get("/api/public/profile?locale=en").status_code == 503
        assert client.get("/api/public/profile?locale=zh-TW").status_code == 503
