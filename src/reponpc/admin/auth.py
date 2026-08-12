"""Argon2id credentials and durable rotating single-admin sessions."""

from __future__ import annotations

import hashlib
import hmac
import secrets
import sqlite3
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Final

from argon2 import PasswordHasher, Type
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

from reponpc.runtime.database import RuntimeDatabase, RuntimeDatabaseError

SESSION_COOKIE: Final = "__Host-reponpc_session"
SESSION_BYTES: Final = 32
CSRF_BYTES: Final = 32


class AdminAuthError(RuntimeError):
    """Stable security-boundary failure with no credential or token detail."""

    def __init__(self, code: str, *, retry_after_seconds: int | None = None) -> None:
        self.code = code
        self.retry_after_seconds = retry_after_seconds
        super().__init__("admin authentication failed")


@dataclass(frozen=True, slots=True)
class AdminSession:
    session_token: str
    csrf_token: str
    expires_at: str
    absolute_expires_at: str


@dataclass(frozen=True, slots=True)
class SessionAuthority:
    session_hash: str
    session_epoch: int


class AdminSessionService:
    """Own the complete credential/session transition boundary."""

    def __init__(
        self,
        *,
        database: RuntimeDatabase,
        username: str,
        password_hash: str,
        identity_hmac_key: bytes,
        idle_minutes: int = 30,
        absolute_hours: int = 12,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        if not username or not password_hash or len(identity_hmac_key) < 32:
            raise ValueError("admin authentication configuration is invalid")
        if idle_minutes <= 0 or absolute_hours <= 0:
            raise ValueError("admin session durations must be positive")
        self._database = database
        self._username = username
        self._password_hash = password_hash
        self._identity_hmac_key = identity_hmac_key
        self._idle = timedelta(minutes=idle_minutes)
        self._absolute = timedelta(hours=absolute_hours)
        self._now = now or (lambda: datetime.now(UTC))
        self._hasher = PasswordHasher(type=Type.ID)

    def login(self, *, username: str, password: str, remote_identity: str) -> AdminSession:
        """Verify generically, apply durable exponential backoff, and create a session."""

        now = self._utc_now()
        identity = self._backoff_identity(username, remote_identity)
        with self._database.connection() as connection:
            self._check_backoff(connection, identity, now)
        username_matches = hmac.compare_digest(username, self._username)
        password_matches = self._verify_password(password)
        valid = username_matches and password_matches
        if not valid:
            retry_after = self._record_failure(identity, now)
            raise AdminAuthError("INVALID_CREDENTIALS", retry_after_seconds=retry_after)
        with self._database.connection() as connection:
            try:
                connection.execute("BEGIN IMMEDIATE")
                connection.execute(
                    "DELETE FROM admin_login_backoff WHERE identity_hmac = ?", (identity,)
                )
                epoch = self._current_epoch(connection)
                session = self._insert_session(connection, epoch=epoch, now=now)
                connection.execute("COMMIT")
                return session
            except sqlite3.Error as exc:
                self._rollback(connection)
                raise RuntimeDatabaseError("runtime_admin_session_failed") from exc

    def authorize(self, *, session_token: str, csrf_token: str | None = None) -> SessionAuthority:
        """Validate current durable authority and optionally the CSRF token."""

        if not session_token:
            raise AdminAuthError("AUTHENTICATION_REQUIRED")
        now = self._utc_now()
        session_hash = _token_hash(session_token)
        with self._database.connection() as connection:
            try:
                connection.execute("BEGIN IMMEDIATE")
                row = connection.execute(
                    """
                    SELECT csrf_hash, idle_expires_at, absolute_expires_at,
                           session_epoch, revoked_at
                    FROM admin_sessions WHERE session_hash = ?
                    """,
                    (session_hash,),
                ).fetchone()
                epoch = self._current_epoch(connection)
                if row is None or not self._row_active(row, epoch, now):
                    self._rollback(connection)
                    raise AdminAuthError("AUTHENTICATION_REQUIRED")
                if csrf_token is not None and not hmac.compare_digest(
                    str(row["csrf_hash"]), _token_hash(csrf_token)
                ):
                    self._rollback(connection)
                    raise AdminAuthError("CSRF_FAILED")
                idle_expires_at = min(
                    now + self._idle,
                    _parse_time(str(row["absolute_expires_at"])),
                )
                connection.execute(
                    "UPDATE admin_sessions SET last_seen_at = ?, idle_expires_at = ? "
                    "WHERE session_hash = ?",
                    (_time(now), _time(idle_expires_at), session_hash),
                )
                connection.execute("COMMIT")
                return SessionAuthority(session_hash=session_hash, session_epoch=epoch)
            except AdminAuthError:
                raise
            except sqlite3.Error as exc:
                self._rollback(connection)
                raise RuntimeDatabaseError("runtime_admin_session_failed") from exc

    def refresh(self, *, session_token: str, csrf_token: str) -> AdminSession:
        """Atomically revoke an old session and return a newly rotated authority."""

        authority = self.authorize(session_token=session_token, csrf_token=csrf_token)
        now = self._utc_now()
        with self._database.connection() as connection:
            try:
                connection.execute("BEGIN IMMEDIATE")
                changed = connection.execute(
                    "UPDATE admin_sessions SET revoked_at = ? "
                    "WHERE session_hash = ? AND revoked_at IS NULL",
                    (_time(now), authority.session_hash),
                ).rowcount
                if changed != 1 or self._current_epoch(connection) != authority.session_epoch:
                    self._rollback(connection)
                    raise AdminAuthError("AUTHENTICATION_REQUIRED")
                session = self._insert_session(connection, epoch=authority.session_epoch, now=now)
                connection.execute("COMMIT")
                return session
            except AdminAuthError:
                raise
            except sqlite3.Error as exc:
                self._rollback(connection)
                raise RuntimeDatabaseError("runtime_admin_session_failed") from exc

    def logout(self, *, session_token: str, csrf_token: str) -> None:
        authority = self.authorize(session_token=session_token, csrf_token=csrf_token)
        with self._database.connection() as connection:
            connection.execute(
                "UPDATE admin_sessions SET revoked_at = ? WHERE session_hash = ?",
                (_time(self._utc_now()), authority.session_hash),
            )

    def logout_all(self, *, session_token: str, csrf_token: str, password: str) -> None:
        self.authorize(session_token=session_token, csrf_token=csrf_token)
        if not self._verify_password(password):
            raise AdminAuthError("INVALID_CREDENTIALS")
        now = self._utc_now()
        with self._database.connection() as connection:
            try:
                connection.execute("BEGIN IMMEDIATE")
                connection.execute(
                    "UPDATE admin_state SET session_epoch = session_epoch + 1 "
                    "WHERE state_key = 'current'"
                )
                connection.execute(
                    "UPDATE admin_sessions SET revoked_at = ? WHERE revoked_at IS NULL",
                    (_time(now),),
                )
                connection.execute("COMMIT")
            except sqlite3.Error as exc:
                self._rollback(connection)
                raise RuntimeDatabaseError("runtime_admin_session_failed") from exc

    def _verify_password(self, password: str) -> bool:
        try:
            return self._hasher.verify(self._password_hash, password)
        except (InvalidHashError, VerificationError, VerifyMismatchError):
            return False

    def _insert_session(
        self, connection: sqlite3.Connection, *, epoch: int, now: datetime
    ) -> AdminSession:
        absolute = now + self._absolute
        idle = min(now + self._idle, absolute)
        for _ in range(3):
            session_token = secrets.token_urlsafe(SESSION_BYTES)
            csrf_token = secrets.token_urlsafe(CSRF_BYTES)
            try:
                connection.execute(
                    """
                    INSERT INTO admin_sessions(
                        session_hash, csrf_hash, created_at, last_seen_at,
                        idle_expires_at, absolute_expires_at, session_epoch
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        _token_hash(session_token),
                        _token_hash(csrf_token),
                        _time(now),
                        _time(now),
                        _time(idle),
                        _time(absolute),
                        epoch,
                    ),
                )
                return AdminSession(
                    session_token=session_token,
                    csrf_token=csrf_token,
                    expires_at=_time(idle),
                    absolute_expires_at=_time(absolute),
                )
            except sqlite3.IntegrityError:
                continue
        raise RuntimeDatabaseError("runtime_admin_session_failed")

    def _record_failure(self, identity: str, now: datetime) -> int:
        with self._database.connection() as connection:
            try:
                connection.execute("BEGIN IMMEDIATE")
                row = connection.execute(
                    "SELECT failure_count FROM admin_login_backoff WHERE identity_hmac = ?",
                    (identity,),
                ).fetchone()
                failures = min(16, (int(row[0]) if row is not None else 0) + 1)
                delay = min(300, 2 ** (failures - 1))
                connection.execute(
                    """
                    INSERT INTO admin_login_backoff(
                        identity_hmac, failure_count, next_allowed_at, expires_at
                    ) VALUES (?, ?, ?, ?)
                    ON CONFLICT(identity_hmac) DO UPDATE SET
                        failure_count = excluded.failure_count,
                        next_allowed_at = excluded.next_allowed_at,
                        expires_at = excluded.expires_at
                    """,
                    (
                        identity,
                        failures,
                        _time(now + timedelta(seconds=delay)),
                        _time(now + timedelta(hours=24)),
                    ),
                )
                connection.execute("COMMIT")
                return delay
            except sqlite3.Error as exc:
                self._rollback(connection)
                raise RuntimeDatabaseError("runtime_admin_backoff_failed") from exc

    @staticmethod
    def _check_backoff(connection: sqlite3.Connection, identity: str, now: datetime) -> None:
        row = connection.execute(
            "SELECT next_allowed_at FROM admin_login_backoff WHERE identity_hmac = ?",
            (identity,),
        ).fetchone()
        if row is None:
            return
        remaining = int((_parse_time(str(row[0])) - now).total_seconds())
        if remaining > 0:
            raise AdminAuthError("INVALID_CREDENTIALS", retry_after_seconds=remaining)

    @staticmethod
    def _current_epoch(connection: sqlite3.Connection) -> int:
        row = connection.execute(
            "SELECT session_epoch FROM admin_state WHERE state_key = 'current'"
        ).fetchone()
        if row is None:
            raise RuntimeDatabaseError("runtime_admin_state_missing")
        return int(row[0])

    @staticmethod
    def _row_active(row: sqlite3.Row, epoch: int, now: datetime) -> bool:
        return bool(
            row["revoked_at"] is None
            and int(row["session_epoch"]) == epoch
            and now < _parse_time(str(row["idle_expires_at"]))
            and now < _parse_time(str(row["absolute_expires_at"]))
        )

    def _backoff_identity(self, username: str, remote_identity: str) -> str:
        payload = f"{username.casefold()}\x00{remote_identity}".encode()
        return hmac.new(self._identity_hmac_key, payload, hashlib.sha256).hexdigest()

    def _utc_now(self) -> datetime:
        value = self._now()
        if value.tzinfo is None:
            raise RuntimeError("admin authentication clock must be timezone-aware")
        return value.astimezone(UTC)

    @staticmethod
    def _rollback(connection: sqlite3.Connection) -> None:
        if connection.in_transaction:
            connection.execute("ROLLBACK")


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _time(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _parse_time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)
