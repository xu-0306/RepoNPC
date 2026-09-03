from __future__ import annotations

import hashlib
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from argon2 import PasswordHasher, Type

from reponpc.admin.auth import (
    AdminAuthError,
    AdminSession,
    AdminSessionService,
    issue_admin_setup_code,
    set_admin_recovery_password,
)
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


def _dynamic_service(tmp_path: Path, clock: Clock) -> tuple[AdminSessionService, RuntimeDatabase]:
    database = RuntimeDatabase(tmp_path, busy_timeout_ms=10_000)
    database.initialize()
    return (
        AdminSessionService(
            database=database,
            identity_hmac_key=b"k" * 32,
            idle_minutes=30,
            absolute_hours=12,
            now=clock,
        ),
        database,
    )


def test_setup_code_is_short_lived_hashed_and_reissued_atomically(tmp_path: Path) -> None:
    clock = Clock()
    service, database = _dynamic_service(tmp_path, clock)

    assert service.setup_status().setup_required is True
    assert service.setup_status().setup_code_available is False
    first = issue_admin_setup_code(database, now=clock())
    second = issue_admin_setup_code(database, now=clock())

    assert first != second
    assert service.setup_status().setup_code_available is True
    with database.connection() as connection:
        row = connection.execute("SELECT code_hash FROM admin_setup").fetchone()
    assert row is not None
    assert row["code_hash"] == hashlib.sha256(second.encode()).hexdigest()
    assert first not in str(row) and second not in str(row)
    with pytest.raises(AdminAuthError) as stale:
        service.setup_owner(
            setup_code=first,
            username="owner",
            password="correct horse battery staple",
            password_confirmation="correct horse battery staple",
        )
    assert stale.value.code == "SETUP_DENIED"


def test_setup_owner_is_durable_one_time_and_never_stores_plaintext(tmp_path: Path) -> None:
    clock = Clock()
    service, database = _dynamic_service(tmp_path, clock)
    setup_code = issue_admin_setup_code(database, now=clock())
    password = "npcx"

    session = service.setup_owner(
        setup_code=setup_code,
        username="  portfolio-owner  ",
        password=password,
        password_confirmation=password,
    )

    service.authorize(session_token=session.session_token, csrf_token=session.csrf_token)
    assert service.setup_status().setup_required is False
    with database.connection() as connection:
        owner = connection.execute("SELECT username, password_hash FROM admin_owner").fetchone()
        setup = connection.execute("SELECT * FROM admin_setup").fetchone()
        stored_session = connection.execute(
            "SELECT session_hash, csrf_hash FROM admin_sessions"
        ).fetchone()
    assert owner is not None and owner["username"] == "portfolio-owner"
    assert str(owner["password_hash"]).startswith("$argon2id$")
    assert PasswordHasher(type=Type.ID).verify(str(owner["password_hash"]), password)
    assert setup is None
    assert stored_session is not None
    persisted = repr(tuple(owner)) + repr(tuple(stored_session))
    assert all(
        secret not in persisted
        for secret in (setup_code, password, session.session_token, session.csrf_token)
    )

    restarted = AdminSessionService(
        database=database,
        identity_hmac_key=b"k" * 32,
        now=clock,
    )
    restarted.login(username="portfolio-owner", password=password, remote_identity="visitor")
    with pytest.raises(AdminAuthError) as repeated:
        restarted.setup_owner(
            setup_code=setup_code,
            username="other",
            password=password,
            password_confirmation=password,
        )
    assert repeated.value.code == "SETUP_ALREADY_COMPLETE"
    with pytest.raises(AdminAuthError) as reissue:
        issue_admin_setup_code(database, now=clock())
    assert reissue.value.code == "SETUP_ALREADY_COMPLETE"


def test_production_password_policy_blocks_short_and_common_but_accepts_unicode(
    tmp_path: Path,
) -> None:
    clock = Clock()
    database = RuntimeDatabase(tmp_path)
    database.initialize()
    service = AdminSessionService(
        database=database,
        identity_hmac_key=b"k" * 32,
        deployment_profile="production",
        now=clock,
    )
    setup_code = issue_admin_setup_code(database, now=clock())

    for password in ("short-password", "password1234567"):
        with pytest.raises(AdminAuthError) as denied:
            service.setup_owner(
                setup_code=setup_code,
                username="owner",
                password=password,
                password_confirmation=password,
            )
        assert denied.value.code == "SETUP_DENIED"

    password = "安全密碼" * 4
    service.setup_owner(
        setup_code=setup_code,
        username="owner",
        password=password,
        password_confirmation=password,
    )
    service.login(username="owner", password=password, remote_identity="local")


def test_host_recovery_changes_only_hash_and_accepts_optional_owner_selector(
    tmp_path: Path,
) -> None:
    clock = Clock()
    service, database = _dynamic_service(tmp_path, clock)
    setup_code = issue_admin_setup_code(database, now=clock())
    service.setup_owner(
        setup_code=setup_code,
        username="owner",
        password="npcx",
        password_confirmation="npcx",
    )

    replacement = "安全密碼" * 4
    set_admin_recovery_password(
        database,
        username=None,
        password=replacement,
        deployment_profile="production",
    )

    with database.connection() as connection:
        owner = connection.execute(
            "SELECT username, password_hash FROM admin_owner WHERE state_key = 'current'"
        ).fetchone()
    assert owner is not None and owner["username"] == "owner"
    assert PasswordHasher(type=Type.ID).verify(str(owner["password_hash"]), replacement)


@pytest.mark.parametrize(
    ("username", "password", "confirmation"),
    [
        ("", "correct horse battery staple", "correct horse battery staple"),
        ("owner", "abc", "abc"),
        ("owner", "correct horse battery staple", "different password value"),
    ],
)
def test_setup_rejects_invalid_owner_fields(
    tmp_path: Path, username: str, password: str, confirmation: str
) -> None:
    clock = Clock()
    service, database = _dynamic_service(tmp_path, clock)
    setup_code = issue_admin_setup_code(database, now=clock())

    with pytest.raises(AdminAuthError) as denied:
        service.setup_owner(
            setup_code=setup_code,
            username=username,
            password=password,
            password_confirmation=confirmation,
        )

    assert denied.value.code == "SETUP_DENIED"
    assert service.setup_status().setup_required is True


def test_setup_code_expires_after_fifteen_minutes(tmp_path: Path) -> None:
    clock = Clock()
    service, database = _dynamic_service(tmp_path, clock)
    setup_code = issue_admin_setup_code(database, now=clock())
    clock.advance(minutes=15)

    assert service.setup_status().setup_code_available is False
    with pytest.raises(AdminAuthError) as expired:
        service.setup_owner(
            setup_code=setup_code,
            username="owner",
            password="correct horse battery staple",
            password_confirmation="correct horse battery staple",
        )
    assert expired.value.code == "SETUP_DENIED"


def test_invalid_setup_code_does_not_run_argon2(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    service, database = _dynamic_service(tmp_path, Clock())
    issue_admin_setup_code(database, now=Clock()())

    class FailingHasher:
        def hash(self, _password: str) -> str:
            pytest.fail("invalid host proof must not invoke Argon2")

    monkeypatch.setattr(
        service,
        "_hasher",
        FailingHasher(),
    )

    with pytest.raises(AdminAuthError) as denied:
        service.setup_owner(
            setup_code="wrong-code",
            username="owner",
            password="correct horse battery staple",
            password_confirmation="correct horse battery staple",
        )

    assert denied.value.code == "SETUP_DENIED"


def test_concurrent_setup_allows_exactly_one_owner(tmp_path: Path) -> None:
    clock = Clock()
    service, database = _dynamic_service(tmp_path, clock)
    setup_code = issue_admin_setup_code(database, now=clock())

    def attempt(username: str) -> AdminSession | str:
        try:
            return service.setup_owner(
                setup_code=setup_code,
                username=username,
                password="correct horse battery staple",
                password_confirmation="correct horse battery staple",
            )
        except AdminAuthError as exc:
            return exc.code

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(attempt, ("owner-one", "owner-two")))

    assert sum(isinstance(result, AdminSession) for result in results) == 1
    assert results.count("SETUP_ALREADY_COMPLETE") == 1
    with database.connection() as connection:
        assert connection.execute("SELECT COUNT(*) FROM admin_owner").fetchone()[0] == 1


def test_environment_credentials_permanently_disable_first_owner_setup(tmp_path: Path) -> None:
    service, _database = _service(tmp_path, Clock())

    assert service.setup_status().setup_required is False
    with pytest.raises(AdminAuthError) as denied:
        service.setup_owner(
            setup_code="unused",
            username="owner",
            password="correct horse battery staple",
            password_confirmation="correct horse battery staple",
        )
    assert denied.value.code == "SETUP_ALREADY_COMPLETE"


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
    calls: list[tuple[str, str]] = []
    original = service._verify_password_hash

    def recording_verify(password_hash: str, password: str) -> bool:
        calls.append((password_hash, password))
        return original(password_hash, password)

    monkeypatch.setattr(service, "_verify_password_hash", recording_verify)
    with pytest.raises(AdminAuthError):
        service.login(username="unknown", password="wrong", remote_identity="visitor")

    assert len(calls) == 1
    assert calls[0][0].startswith("$argon2id$")
    assert calls[0][1] == "wrong"


def test_forged_csrf_is_rejected(tmp_path: Path) -> None:
    service, _database = _service(tmp_path, Clock())
    session = service.login(
        username="admin", password="correct horse battery staple", remote_identity="visitor"
    )
    with pytest.raises(AdminAuthError) as error:
        service.authorize(session_token=session.session_token, csrf_token="forged")
    assert error.value.code == "CSRF_FAILED"
