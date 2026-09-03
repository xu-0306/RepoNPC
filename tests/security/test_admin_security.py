from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from argon2 import PasswordHasher, Type
from fastapi.testclient import TestClient

from reponpc.admin.auth import AdminSessionService, issue_admin_setup_code
from reponpc.main import create_app
from reponpc.runtime.database import RuntimeDatabase

ORIGIN = "https://portfolio.example.com"
PASSWORD = "npcx"


def _app(tmp_path: Path):
    database = RuntimeDatabase(tmp_path)
    database.initialize()
    service = AdminSessionService(
        database=database,
        username="admin",
        password_hash=PasswordHasher(type=Type.ID).hash(PASSWORD),
        identity_hmac_key=b"i" * 32,
        now=lambda: datetime(2026, 8, 13, tzinfo=UTC),
    )
    return create_app(admin_session_service=service, admin_origins=(ORIGIN,)), database


def _setup_app(tmp_path: Path):
    database = RuntimeDatabase(tmp_path)
    database.initialize()
    service = AdminSessionService(
        database=database,
        identity_hmac_key=b"i" * 32,
        now=lambda: datetime(2026, 8, 13, tzinfo=UTC),
    )
    return create_app(admin_session_service=service, admin_origins=(ORIGIN,)), database, service


def _login(client: TestClient):
    return client.post(
        "/api/admin/session",
        headers={"Origin": ORIGIN},
        json={"username": "admin", "password": PASSWORD},
    )


def test_login_sets_host_cookie_and_never_returns_session_token(tmp_path: Path) -> None:
    app, database = _app(tmp_path)
    with TestClient(app, base_url=ORIGIN) as client:
        response = _login(client)

    assert response.status_code == 200
    cookie = response.headers["set-cookie"]
    assert cookie.startswith("__Host-reponpc_session=")
    assert all(flag in cookie for flag in ("HttpOnly", "Path=/", "SameSite=strict", "Secure"))
    assert set(response.json()) == {"csrf_token", "expires_at", "absolute_expires_at"}
    assert response.json()["csrf_token"] not in cookie
    with database.connection() as connection:
        stored = connection.execute("SELECT session_hash, csrf_hash FROM admin_sessions").fetchone()
    assert stored is not None
    assert all(response.json()["csrf_token"] != value for value in stored)


def test_setup_status_exposes_only_safe_booleans(tmp_path: Path) -> None:
    app, database, _service = _setup_app(tmp_path)
    setup_code = issue_admin_setup_code(database, now=datetime(2026, 8, 13, tzinfo=UTC))

    with TestClient(app, base_url=ORIGIN) as client:
        response = client.get("/api/admin/setup")

    assert response.status_code == 200
    assert response.json() == {
        "setup_required": True,
        "setup_code_available": True,
    }
    assert setup_code not in response.text
    assert "code_hash" not in response.text
    assert "expires_at" not in response.text


def test_legacy_github_setup_route_cannot_consume_code_or_create_owner(
    tmp_path: Path,
) -> None:
    app, database, service = _setup_app(tmp_path)
    setup_code = issue_admin_setup_code(database, now=datetime(2026, 8, 13, tzinfo=UTC))

    with TestClient(app, base_url=ORIGIN) as client:
        rejected = client.post(
            "/api/admin/setup/github/start",
            headers={"Origin": ORIGIN},
            json={"setup_code": setup_code},
        )

    assert rejected.status_code == 403
    assert rejected.json()["error"]["code"] == "SETUP_DENIED"
    assert setup_code not in rejected.text
    assert service.setup_status().setup_required is True
    assert service.setup_status().setup_code_available is True


def test_github_oauth_setup_guide_has_no_secret_or_identity_material(tmp_path: Path) -> None:
    app, _database = _app(tmp_path)
    app.state.github_oauth_callback_url = f"{ORIGIN}/api/admin/github/callback"

    with TestClient(app, base_url=ORIGIN) as client:
        response = client.get("/api/admin/github/oauth/setup-guide")

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert set(response.json()) == {
        "configured",
        "callback_url",
        "documentation_url",
        "next_step",
    }
    assert "REPONPC_GITHUB_OAUTH_CLIENT_SECRET_FILE" not in response.text
    assert "REPONPC_CREDENTIAL_ENCRYPTION_KEY_FILE" not in response.text
    assert "token" not in response.text.casefold()
    assert "owner" not in response.text.casefold()


def test_github_oauth_setup_guide_rejects_cross_origin_callback_configuration(
    tmp_path: Path,
) -> None:
    app, _database = _app(tmp_path)
    app.state.github_oauth_callback_url = "https://evil.example/api/admin/github/callback"

    with TestClient(app, base_url=ORIGIN) as client:
        response = client.get("/api/admin/github/oauth/setup-guide")

    assert response.status_code == 200
    assert response.json()["callback_url"] == f"{ORIGIN}/api/admin/github/callback"
    assert "evil.example" not in response.text


def test_setup_requires_same_origin_and_returns_generic_denial(tmp_path: Path) -> None:
    app, database, _service = _setup_app(tmp_path)
    setup_code = issue_admin_setup_code(database, now=datetime(2026, 8, 13, tzinfo=UTC))
    body = {
        "setup_code": setup_code,
        "username": "owner",
        "password": PASSWORD,
        "password_confirmation": PASSWORD,
    }

    with TestClient(app, base_url=ORIGIN) as client:
        cross_origin = client.post(
            "/api/admin/setup", headers={"Origin": "https://evil.example"}, json=body
        )
        missing_origin = client.post("/api/admin/setup", json=body)
        denied = client.post(
            "/api/admin/setup",
            headers={"Origin": ORIGIN},
            json={**body, "setup_code": "wrong-code"},
        )

    assert cross_origin.status_code == 403
    assert missing_origin.status_code == 403
    assert denied.status_code == 401
    assert denied.json()["error"]["code"] == "SETUP_DENIED"
    assert setup_code not in denied.text
    assert PASSWORD not in denied.text


def test_setup_validation_and_one_time_owner_session_contract(tmp_path: Path) -> None:
    app, database, _service = _setup_app(tmp_path)
    setup_code = issue_admin_setup_code(database, now=datetime(2026, 8, 13, tzinfo=UTC))

    with TestClient(app, base_url=ORIGIN) as client:
        malformed = client.post(
            "/api/admin/setup",
            headers={"Origin": ORIGIN},
            json={
                "setup_code": setup_code,
                "username": "owner",
                "password": "abc",
                "password_confirmation": "abc",
            },
        )
        created = client.post(
            "/api/admin/setup",
            headers={"Origin": ORIGIN},
            json={
                "setup_code": setup_code,
                "username": "owner",
                "password": PASSWORD,
                "password_confirmation": PASSWORD,
            },
        )
        completed_status = client.get("/api/admin/setup")
        repeated = client.post(
            "/api/admin/setup",
            headers={"Origin": ORIGIN},
            json={
                "setup_code": setup_code,
                "username": "other",
                "password": PASSWORD,
                "password_confirmation": PASSWORD,
            },
        )
        client.cookies.clear()
        login = client.post(
            "/api/admin/session",
            headers={"Origin": ORIGIN},
            json={"username": "owner", "password": PASSWORD},
        )

    assert malformed.status_code == 400
    assert malformed.json()["error"]["code"] == "VALIDATION_ERROR"
    assert created.status_code == 200
    assert set(created.json()) == {"csrf_token", "expires_at", "absolute_expires_at"}
    assert created.headers["set-cookie"].startswith("__Host-reponpc_session=")
    assert setup_code not in created.text and PASSWORD not in created.text
    assert completed_status.json() == {
        "setup_required": False,
        "setup_code_available": False,
    }
    assert repeated.status_code == 409
    assert repeated.json()["error"]["code"] == "SETUP_ALREADY_COMPLETE"
    assert login.status_code == 200


def test_cross_origin_missing_origin_and_forged_csrf_fail_closed(tmp_path: Path) -> None:
    app, _database = _app(tmp_path)
    with TestClient(app, base_url=ORIGIN) as client:
        assert (
            client.post(
                "/api/admin/session",
                headers={"Origin": "https://evil.example"},
                json={"username": "admin", "password": PASSWORD},
            ).status_code
            == 403
        )
        assert (
            client.post(
                "/api/admin/session", json={"username": "admin", "password": PASSWORD}
            ).status_code
            == 403
        )
        login = _login(client)
        assert (
            client.post(
                "/api/admin/session/refresh",
                headers={"Origin": ORIGIN, "X-CSRF-Token": "forged"},
            ).status_code
            == 403
        )
        assert (
            client.post(
                "/api/admin/session/refresh",
                headers={
                    "Origin": "https://evil.example",
                    "X-CSRF-Token": login.json()["csrf_token"],
                },
            ).status_code
            == 403
        )


def test_refresh_rotates_cookie_and_logout_revokes_authority(tmp_path: Path) -> None:
    app, _database = _app(tmp_path)
    with TestClient(app, base_url=ORIGIN) as client:
        login = _login(client)
        first_cookie = login.headers["set-cookie"]
        refresh = client.post(
            "/api/admin/session/refresh",
            headers={"Origin": ORIGIN, "X-CSRF-Token": login.json()["csrf_token"]},
        )
        assert refresh.status_code == 200
        assert refresh.headers["set-cookie"] != first_cookie
        logout = client.delete(
            "/api/admin/session",
            headers={"Origin": ORIGIN, "X-CSRF-Token": refresh.json()["csrf_token"]},
        )
        assert logout.status_code == 204
        assert "Max-Age=0" in logout.headers["set-cookie"]
        denied = client.post(
            "/api/admin/session/refresh",
            headers={"Origin": ORIGIN, "X-CSRF-Token": refresh.json()["csrf_token"]},
        )
        assert denied.status_code == 401
        assert denied.json()["error"]["code"] == "AUTHENTICATION_REQUIRED"


def test_referer_is_accepted_only_when_its_origin_matches(tmp_path: Path) -> None:
    app, _database = _app(tmp_path)
    with TestClient(app, base_url=ORIGIN) as client:
        accepted = client.post(
            "/api/admin/session",
            headers={"Referer": f"{ORIGIN}/admin/login"},
            json={"username": "admin", "password": PASSWORD},
        )
        rejected = client.post(
            "/api/admin/session",
            headers={"Referer": "https://evil.example/admin"},
            json={"username": "admin", "password": PASSWORD},
        )
    assert accepted.status_code == 200
    assert rejected.status_code == 403
