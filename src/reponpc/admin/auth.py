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
SETUP_CODE_BYTES: Final = 32
SETUP_CODE_TTL: Final = timedelta(minutes=15)
RECENT_AUTH_TTL: Final = timedelta(minutes=5)
MIN_ADMIN_PASSWORD_LENGTH: Final = 4
PRODUCTION_MIN_ADMIN_PASSWORD_LENGTH: Final = 15
MAX_ADMIN_PASSWORD_LENGTH: Final = 128
ADMIN_DEPLOYMENT_PROFILES: Final = frozenset({"loopback_evaluation", "production"})
COMMON_ADMIN_PASSWORDS: Final = frozenset(
    {
        "123456",
        "12345678",
        "admin",
        "changeme",
        "letmein",
        "password",
        "password1",
        "password123",
        "password1234567",
        "qwerty",
    }
)


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


@dataclass(frozen=True, slots=True)
class AdminSetupStatus:
    setup_required: bool
    setup_code_available: bool
    minimum_password_length: int


@dataclass(frozen=True, slots=True)
class AdminAuthMethods:
    password_available: bool
    github_available: bool
    setup_required: bool


@dataclass(frozen=True, slots=True)
class _AdminCredentials:
    username: str
    password_hash: str


class AdminSessionService:
    """Own the complete credential/session transition boundary."""

    def __init__(
        self,
        *,
        database: RuntimeDatabase,
        username: str | None = None,
        password_hash: str | None = None,
        identity_hmac_key: bytes,
        idle_minutes: int = 30,
        absolute_hours: int = 12,
        deployment_profile: str = "loopback_evaluation",
        compromised_passwords: frozenset[str] = COMMON_ADMIN_PASSWORDS,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        if (username is None) != (password_hash is None) or len(identity_hmac_key) < 32:
            raise ValueError("admin authentication configuration is invalid")
        if username is not None and (not username or not password_hash):
            raise ValueError("admin authentication configuration is invalid")
        if idle_minutes <= 0 or absolute_hours <= 0:
            raise ValueError("admin session durations must be positive")
        if deployment_profile not in ADMIN_DEPLOYMENT_PROFILES:
            raise ValueError("admin deployment profile is invalid")
        self._database = database
        self._username = username
        self._password_hash = password_hash
        self._identity_hmac_key = identity_hmac_key
        self._idle = timedelta(minutes=idle_minutes)
        self._absolute = timedelta(hours=absolute_hours)
        self._deployment_profile = deployment_profile
        self._compromised_passwords = frozenset(
            value.strip().casefold() for value in compromised_passwords if value.strip()
        )
        self._now = now or (lambda: datetime.now(UTC))
        self._hasher = PasswordHasher(type=Type.ID)
        self._dummy_password_hash = self._hasher.hash(secrets.token_urlsafe(32))

    def setup_status(self) -> AdminSetupStatus:
        """Return only the safe public state needed by the first-owner UI."""

        if self._environment_credentials() is not None:
            return AdminSetupStatus(
                setup_required=False,
                setup_code_available=False,
                minimum_password_length=self.minimum_password_length,
            )
        now = self._utc_now()
        try:
            with self._database.connection() as connection:
                owner = connection.execute(
                    "SELECT 1 FROM admin_owner WHERE state_key = 'current'"
                ).fetchone()
                if owner is not None:
                    return AdminSetupStatus(False, False, self.minimum_password_length)
                setup = connection.execute(
                    "SELECT expires_at FROM admin_setup WHERE state_key = 'current'"
                ).fetchone()
        except sqlite3.Error as exc:
            raise RuntimeDatabaseError("runtime_admin_setup_failed") from exc
        return AdminSetupStatus(
            setup_required=True,
            setup_code_available=(
                setup is not None and now < _parse_time(str(setup["expires_at"]))
            ),
            minimum_password_length=self.minimum_password_length,
        )

    @property
    def minimum_password_length(self) -> int:
        return (
            MIN_ADMIN_PASSWORD_LENGTH
            if self._deployment_profile == "loopback_evaluation"
            else PRODUCTION_MIN_ADMIN_PASSWORD_LENGTH
        )

    def auth_methods(self, *, github_configured: bool) -> AdminAuthMethods:
        """Expose only safe method availability; never reveal linked identities."""

        setup = self.setup_status()
        with self._database.connection() as connection:
            local_method = connection.execute(
                "SELECT 1 FROM admin_auth_methods WHERE method = 'local_password'"
            ).fetchone()
        return AdminAuthMethods(
            password_available=self._environment_credentials() is not None
            or local_method is not None,
            github_available=github_configured,
            setup_required=setup.setup_required,
        )

    def setup_owner(
        self,
        *,
        setup_code: str,
        username: str,
        password: str,
        password_confirmation: str,
    ) -> AdminSession:
        """Atomically consume one host code, create the owner, and issue a session."""

        if self._environment_credentials() is not None:
            raise AdminAuthError("SETUP_ALREADY_COMPLETE")
        normalized_username = username.strip()
        if (
            not 1 <= len(normalized_username) <= 64
            or not _new_password_is_allowed(
                password,
                deployment_profile=self._deployment_profile,
                compromised_passwords=self._compromised_passwords,
            )
            or password != password_confirmation
            or not setup_code
        ):
            raise AdminAuthError("SETUP_DENIED")
        supplied_hash = _token_hash(setup_code)
        now = self._utc_now()
        try:
            with self._database.connection() as connection:
                owner = connection.execute(
                    "SELECT 1 FROM admin_owner WHERE state_key = 'current'"
                ).fetchone()
                setup = connection.execute(
                    "SELECT code_hash, expires_at FROM admin_setup WHERE state_key = 'current'"
                ).fetchone()
        except sqlite3.Error as exc:
            raise RuntimeDatabaseError("runtime_admin_setup_failed") from exc
        if owner is not None:
            raise AdminAuthError("SETUP_ALREADY_COMPLETE")
        if (
            setup is None
            or now >= _parse_time(str(setup["expires_at"]))
            or not hmac.compare_digest(str(setup["code_hash"]), supplied_hash)
        ):
            raise AdminAuthError("SETUP_DENIED")

        # Argon2 is intentionally delayed until the high-entropy host proof is
        # valid, so an uninitialized public deployment cannot be forced to hash
        # attacker-chosen passwords. The transaction below rechecks the proof.
        password_hash = self._hasher.hash(password)
        now = self._utc_now()
        with self._database.connection() as connection:
            try:
                connection.execute("BEGIN IMMEDIATE")
                owner = connection.execute(
                    "SELECT 1 FROM admin_owner WHERE state_key = 'current'"
                ).fetchone()
                if owner is not None:
                    self._rollback(connection)
                    raise AdminAuthError("SETUP_ALREADY_COMPLETE")
                setup = connection.execute(
                    "SELECT code_hash, expires_at FROM admin_setup WHERE state_key = 'current'"
                ).fetchone()
                if (
                    setup is None
                    or now >= _parse_time(str(setup["expires_at"]))
                    or not hmac.compare_digest(str(setup["code_hash"]), supplied_hash)
                ):
                    self._rollback(connection)
                    raise AdminAuthError("SETUP_DENIED")
                connection.execute(
                    "INSERT INTO admin_owner(state_key, username, password_hash, created_at) "
                    "VALUES ('current', ?, ?, ?)",
                    (normalized_username, password_hash, _time(now)),
                )
                connection.execute(
                    "INSERT INTO admin_auth_methods("
                    "method, github_user_id, github_login, created_at"
                    ") "
                    "VALUES ('local_password', NULL, NULL, ?)",
                    (_time(now),),
                )
                connection.execute("DELETE FROM admin_setup WHERE state_key = 'current'")
                session = self._insert_session(
                    connection,
                    epoch=self._current_epoch(connection),
                    now=now,
                )
                connection.execute("COMMIT")
                return session
            except AdminAuthError:
                raise
            except sqlite3.Error as exc:
                self._rollback(connection)
                raise RuntimeDatabaseError("runtime_admin_setup_failed") from exc

    def login(self, *, username: str, password: str, remote_identity: str) -> AdminSession:
        """Verify generically, apply durable exponential backoff, and create a session."""

        now = self._utc_now()
        identity = self._backoff_identity(username, remote_identity)
        with self._database.connection() as connection:
            self._check_backoff(connection, identity, now)
            credentials = self._credentials(connection)
        expected_username = credentials.username if credentials is not None else ""
        expected_hash = (
            credentials.password_hash if credentials is not None else self._dummy_password_hash
        )
        username_matches = hmac.compare_digest(username, expected_username)
        password_matches = self._verify_password_hash(expected_hash, password)
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

    def login_github(
        self,
        *,
        github_user_id: str,
        github_login: str,
        remote_identity: str,
    ) -> AdminSession:
        """Issue a normal local session only for the sole linked GitHub identity."""

        now = self._utc_now()
        identity = self._backoff_identity(f"github:{github_user_id}", remote_identity)
        with self._database.connection() as connection:
            self._check_backoff(connection, identity, now)
            linked = connection.execute(
                "SELECT github_login FROM admin_auth_methods "
                "WHERE method = 'github' AND github_user_id = ?",
                (github_user_id,),
            ).fetchone()
        if linked is None:
            retry_after = self._record_failure(identity, now)
            raise AdminAuthError("INVALID_CREDENTIALS", retry_after_seconds=retry_after)
        with self._database.connection() as connection:
            try:
                connection.execute("BEGIN IMMEDIATE")
                connection.execute(
                    "DELETE FROM admin_login_backoff WHERE identity_hmac = ?", (identity,)
                )
                connection.execute(
                    "UPDATE admin_auth_methods SET github_login = ? WHERE method = 'github'",
                    (github_login[:100],),
                )
                session = self._insert_session(
                    connection,
                    epoch=self._current_epoch(connection),
                    now=now,
                )
                connection.execute("COMMIT")
                return session
            except sqlite3.Error as exc:
                self._rollback(connection)
                raise RuntimeDatabaseError("runtime_admin_session_failed") from exc

    def link_github(
        self,
        *,
        session_token: str,
        github_user_id: str,
        github_login: str,
    ) -> None:
        """Link the stable GitHub identity after a recent local authentication."""

        self._authorize_recent(session_token)
        now = self._utc_now()
        with self._database.connection() as connection:
            try:
                connection.execute("BEGIN IMMEDIATE")
                existing = connection.execute(
                    "SELECT github_user_id FROM admin_auth_methods WHERE method = 'github'"
                ).fetchone()
                if existing is not None and str(existing["github_user_id"]) != github_user_id:
                    self._rollback(connection)
                    raise AdminAuthError("INVALID_CREDENTIALS")
                connection.execute(
                    "INSERT INTO admin_auth_methods("
                    "method, github_user_id, github_login, created_at"
                    ") "
                    "VALUES ('github', ?, ?, ?) "
                    "ON CONFLICT(method) DO UPDATE SET github_login = excluded.github_login",
                    (github_user_id, github_login[:100], _time(now)),
                )
                connection.execute("COMMIT")
            except AdminAuthError:
                raise
            except sqlite3.Error as exc:
                self._rollback(connection)
                raise RuntimeDatabaseError("runtime_admin_session_failed") from exc

    def unlink_github(self, *, session_token: str) -> None:
        """Remove GitHub only if a password method remains and auth is recent."""

        self._authorize_recent(session_token)
        with self._database.connection() as connection:
            try:
                connection.execute("BEGIN IMMEDIATE")
                password = (
                    self._environment_credentials() is not None
                    or connection.execute(
                        "SELECT 1 FROM admin_auth_methods WHERE method = 'local_password'"
                    ).fetchone()
                    is not None
                )
                if not password:
                    self._rollback(connection)
                    raise AdminAuthError("LAST_AUTH_METHOD_REQUIRED")
                connection.execute("DELETE FROM admin_auth_methods WHERE method = 'github'")
                connection.execute(
                    "DELETE FROM admin_github_credentials WHERE purpose = 'identity_public_read'"
                )
                connection.execute("COMMIT")
            except AdminAuthError:
                raise
            except sqlite3.Error as exc:
                self._rollback(connection)
                raise RuntimeDatabaseError("runtime_admin_session_failed") from exc

    def require_recent_auth(self, session_token: str) -> None:
        """Verify fresh local-session authentication for an identity mutation."""

        self._authorize_recent(session_token)

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

    def logout_all(self, *, session_token: str, csrf_token: str, password: str | None) -> None:
        self.authorize(session_token=session_token, csrf_token=csrf_token)
        if self._has_local_password():
            if not password or not self._verify_password(password):
                raise AdminAuthError("INVALID_CREDENTIALS")
        else:
            # A GitHub-only owner cannot supply a local password.  A fresh
            # GitHub login creates a local session with authenticated_at, which
            # is the server-side proof required for this sensitive action.
            self._authorize_recent(session_token)
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
            with self._database.connection() as connection:
                credentials = self._credentials(connection)
        except sqlite3.Error as exc:
            raise RuntimeDatabaseError("runtime_admin_session_failed") from exc
        password_hash = (
            credentials.password_hash if credentials is not None else self._dummy_password_hash
        )
        return credentials is not None and self._verify_password_hash(password_hash, password)

    def _has_local_password(self) -> bool:
        if self._environment_credentials() is not None:
            return True
        with self._database.connection() as connection:
            return (
                connection.execute(
                    "SELECT 1 FROM admin_auth_methods WHERE method = 'local_password'"
                ).fetchone()
                is not None
            )

    def _verify_password_hash(self, password_hash: str, password: str) -> bool:
        try:
            return self._hasher.verify(password_hash, password)
        except (InvalidHashError, VerificationError, VerifyMismatchError):
            return False

    def _environment_credentials(self) -> _AdminCredentials | None:
        if self._username is None or self._password_hash is None:
            return None
        return _AdminCredentials(self._username, self._password_hash)

    def _credentials(self, connection: sqlite3.Connection) -> _AdminCredentials | None:
        configured = self._environment_credentials()
        if configured is not None:
            return configured
        method = connection.execute(
            "SELECT 1 FROM admin_auth_methods WHERE method = 'local_password'"
        ).fetchone()
        if method is None:
            return None
        row = connection.execute(
            "SELECT username, password_hash FROM admin_owner WHERE state_key = 'current'"
        ).fetchone()
        if row is None:
            return None
        return _AdminCredentials(str(row["username"]), str(row["password_hash"]))

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
                        idle_expires_at, absolute_expires_at, session_epoch, authenticated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        _token_hash(session_token),
                        _token_hash(csrf_token),
                        _time(now),
                        _time(now),
                        _time(idle),
                        _time(absolute),
                        epoch,
                        _time(now),
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

    def _authorize_recent(self, session_token: str) -> None:
        authority = self.authorize(session_token=session_token)
        now = self._utc_now()
        with self._database.connection() as connection:
            row = connection.execute(
                "SELECT authenticated_at FROM admin_sessions WHERE session_hash = ?",
                (authority.session_hash,),
            ).fetchone()
        if row is None or row["authenticated_at"] is None:
            raise AdminAuthError("RECENT_AUTHENTICATION_REQUIRED")
        if now - _parse_time(str(row["authenticated_at"])) > RECENT_AUTH_TTL:
            raise AdminAuthError("RECENT_AUTHENTICATION_REQUIRED")

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


def issue_admin_setup_code(
    database: RuntimeDatabase,
    *,
    now: datetime | None = None,
    ttl: timedelta = SETUP_CODE_TTL,
) -> str:
    """Replace any prior setup code and return the new raw code exactly once."""

    if ttl <= timedelta(0):
        raise ValueError("admin setup code lifetime must be positive")
    issued_at = (now or datetime.now(UTC)).astimezone(UTC)
    code = secrets.token_urlsafe(SETUP_CODE_BYTES)
    with database.connection() as connection:
        try:
            connection.execute("BEGIN IMMEDIATE")
            owner = connection.execute(
                "SELECT 1 FROM admin_owner WHERE state_key = 'current'"
            ).fetchone()
            if owner is not None:
                AdminSessionService._rollback(connection)
                raise AdminAuthError("SETUP_ALREADY_COMPLETE")
            connection.execute(
                """
                INSERT INTO admin_setup(state_key, code_hash, created_at, expires_at)
                VALUES ('current', ?, ?, ?)
                ON CONFLICT(state_key) DO UPDATE SET
                    code_hash = excluded.code_hash,
                    created_at = excluded.created_at,
                    expires_at = excluded.expires_at
                """,
                (_token_hash(code), _time(issued_at), _time(issued_at + ttl)),
            )
            connection.execute("COMMIT")
        except AdminAuthError:
            raise
        except sqlite3.Error as exc:
            AdminSessionService._rollback(connection)
            raise RuntimeDatabaseError("runtime_admin_setup_failed") from exc
    return code


def _new_password_is_allowed(
    password: str,
    *,
    deployment_profile: str,
    compromised_passwords: frozenset[str],
) -> bool:
    if deployment_profile not in ADMIN_DEPLOYMENT_PROFILES:
        return False
    minimum = (
        MIN_ADMIN_PASSWORD_LENGTH
        if deployment_profile == "loopback_evaluation"
        else PRODUCTION_MIN_ADMIN_PASSWORD_LENGTH
    )
    normalized = password.strip().casefold()
    return (
        minimum <= len(password) <= MAX_ADMIN_PASSWORD_LENGTH
        and normalized not in compromised_passwords
    )


def validate_new_admin_password(
    password: str,
    *,
    deployment_profile: str,
    compromised_passwords: frozenset[str] = COMMON_ADMIN_PASSWORDS,
) -> None:
    """Apply the selected deployment policy without exposing password detail."""

    if not _new_password_is_allowed(
        password,
        deployment_profile=deployment_profile,
        compromised_passwords=compromised_passwords,
    ):
        raise AdminAuthError("SETUP_DENIED")


def set_admin_recovery_password(
    database: RuntimeDatabase,
    *,
    username: str | None,
    password: str,
    deployment_profile: str = "production",
    compromised_passwords: frozenset[str] = COMMON_ADMIN_PASSWORDS,
) -> None:
    """Host-only recovery: restore a local password method for the sole owner."""

    normalized_username = username.strip() if username is not None else None
    if (
        normalized_username is not None and not 1 <= len(normalized_username) <= 64
    ) or not _new_password_is_allowed(
        password,
        deployment_profile=deployment_profile,
        compromised_passwords=compromised_passwords,
    ):
        raise AdminAuthError("SETUP_DENIED")
    password_hash = PasswordHasher(type=Type.ID).hash(password)
    now = datetime.now(UTC)
    with database.connection() as connection:
        try:
            connection.execute("BEGIN IMMEDIATE")
            owner = connection.execute(
                "SELECT username FROM admin_owner WHERE state_key = 'current'"
            ).fetchone()
            if owner is None or (
                normalized_username is not None and normalized_username != str(owner["username"])
            ):
                AdminSessionService._rollback(connection)
                raise AdminAuthError("SETUP_DENIED")
            connection.execute(
                "UPDATE admin_owner SET password_hash = ? WHERE state_key = 'current'",
                (password_hash,),
            )
            connection.execute(
                "INSERT OR IGNORE INTO admin_auth_methods("
                "method, github_user_id, github_login, created_at"
                ") VALUES ('local_password', NULL, NULL, ?)",
                (_time(now),),
            )
            connection.execute(
                "UPDATE admin_state SET session_epoch = session_epoch + 1 "
                "WHERE state_key = 'current'"
            )
            connection.execute(
                "UPDATE admin_sessions SET revoked_at = ? WHERE revoked_at IS NULL",
                (_time(now),),
            )
            connection.execute("COMMIT")
        except AdminAuthError:
            raise
        except sqlite3.Error as exc:
            AdminSessionService._rollback(connection)
            raise RuntimeDatabaseError("runtime_admin_recovery_failed") from exc


def _time(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _parse_time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)
