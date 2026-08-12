from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from argon2 import PasswordHasher, Type

from reponpc.admin.auth import AdminAuthError, AdminSessionService
from reponpc.runtime.database import RuntimeDatabase


class Clock:
    def __init__(self) -> None:
        self.value = datetime(2026, 8, 13, tzinfo=UTC)

    def __call__(self) -> datetime:
        return self.value

    def advance(self, **kwargs: int) -> None:
        self.value += timedelta(**kwargs)


def _service(tmp_path: Path, clock: Clock) -> tuple[AdminSessionService, RuntimeDatabase]:
    database = RuntimeDatabase(tmp_path)
    database.initialize()
    password_hash = PasswordHasher(type=Type.ID).hash("correct horse battery staple")
    return (
        AdminSessionService(
            database=database,
            username="admin",
            password_hash=password_hash,
            identity_hmac_key=b"k" * 32,
            idle_minutes=30,
            absolute_hours=12,
            now=clock,
        ),
        database,
    )


def test_login_rotation_logout_and_logout_all_are_durable(tmp_path: Path) -> None:
    clock = Clock()
    service, database = _service(tmp_path, clock)
    first = service.login(
        username="admin", password="correct horse battery staple", remote_identity="visitor-1"
    )
    service.authorize(session_token=first.session_token, csrf_token=first.csrf_token)

    rotated = service.refresh(session_token=first.session_token, csrf_token=first.csrf_token)
    with pytest.raises(AdminAuthError) as old:
        service.authorize(session_token=first.session_token)
    assert old.value.code == "AUTHENTICATION_REQUIRED"
    service.authorize(session_token=rotated.session_token, csrf_token=rotated.csrf_token)

    service.logout(session_token=rotated.session_token, csrf_token=rotated.csrf_token)
    with pytest.raises(AdminAuthError):
        service.authorize(session_token=rotated.session_token)

    one = service.login(
        username="admin", password="correct horse battery staple", remote_identity="visitor-1"
    )
    two = service.login(
        username="admin", password="correct horse battery staple", remote_identity="visitor-2"
    )
    service.logout_all(
        session_token=one.session_token,
        csrf_token=one.csrf_token,
        password="correct horse battery staple",
    )
    with pytest.raises(AdminAuthError):
        service.authorize(session_token=two.session_token)

    with database.connection() as connection:
        rows = connection.execute("SELECT session_hash, csrf_hash FROM admin_sessions").fetchall()
    forbidden = {first.session_token, first.csrf_token, rotated.session_token, rotated.csrf_token}
    assert all(value not in {cell for row in rows for cell in row} for value in forbidden)
    assert all(len(row[0]) == len(hashlib.sha256().hexdigest()) for row in rows)


def test_invalid_credentials_backoff_and_expiry(tmp_path: Path) -> None:
    clock = Clock()
    service, _database = _service(tmp_path, clock)
    with pytest.raises(AdminAuthError) as failure:
        service.login(username="unknown", password="wrong", remote_identity="visitor")
    assert failure.value.code == "INVALID_CREDENTIALS"
    assert failure.value.retry_after_seconds == 1
    with pytest.raises(AdminAuthError) as backed_off:
        service.login(username="unknown", password="wrong", remote_identity="visitor")
    assert backed_off.value.code == "INVALID_CREDENTIALS"

    clock.advance(seconds=2)
    session = service.login(
        username="admin", password="correct horse battery staple", remote_identity="visitor"
    )
    clock.advance(minutes=31)
    with pytest.raises(AdminAuthError) as expired:
        service.authorize(session_token=session.session_token)
    assert expired.value.code == "AUTHENTICATION_REQUIRED"


def test_login_always_runs_argon2_verification_for_unknown_username(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    service, _database = _service(tmp_path, Clock())
    calls: list[str] = []
    original = service._verify_password

    def recording_verify(password: str) -> bool:
        calls.append(password)
        return original(password)

    monkeypatch.setattr(service, "_verify_password", recording_verify)
    with pytest.raises(AdminAuthError):
        service.login(username="unknown", password="wrong", remote_identity="visitor")

    assert calls == ["wrong"]


def test_forged_csrf_is_rejected(tmp_path: Path) -> None:
    service, _database = _service(tmp_path, Clock())
    session = service.login(
        username="admin", password="correct horse battery staple", remote_identity="visitor"
    )
    with pytest.raises(AdminAuthError) as error:
        service.authorize(session_token=session.session_token, csrf_token="forged")
    assert error.value.code == "CSRF_FAILED"
