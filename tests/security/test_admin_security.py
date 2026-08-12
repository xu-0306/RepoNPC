from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from argon2 import PasswordHasher, Type
from fastapi.testclient import TestClient

from reponpc.admin.auth import AdminSessionService
from reponpc.main import create_app
from reponpc.runtime.database import RuntimeDatabase

ORIGIN = "https://portfolio.example.com"
PASSWORD = "correct horse battery staple"


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
