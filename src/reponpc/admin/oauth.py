"""GitHub OAuth Web Flow with PKCE and encrypted runtime credentials."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import sqlite3
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Final, Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from reponpc.admin.auth import AdminAuthError, AdminSession, AdminSessionService
from reponpc.admin.batch_resolver import CredentialPurpose, PublicReadCredential
from reponpc.runtime.database import RuntimeDatabase, RuntimeDatabaseError

OAUTH_TRANSACTION_TTL: Final = timedelta(minutes=10)
OAUTH_STATE_BYTES: Final = 32
PKCE_VERIFIER_BYTES: Final = 48
AES_GCM_NONCE_BYTES: Final = 12
MAX_OAUTH_RESPONSE_BYTES: Final = 64 * 1024
GITHUB_AUTHORIZE_URL: Final = "https://github.com/login/oauth/authorize"
GITHUB_TOKEN_URL: Final = "https://github.com/login/oauth/access_token"
GITHUB_USER_URL: Final = "https://api.github.com/user"
GITHUB_GRAPHQL_URL: Final = "https://api.github.com/graphql"


class GitHubOAuthError(RuntimeError):
    """Stable, secret-free OAuth failure."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__("GitHub OAuth operation failed")


@dataclass(frozen=True, slots=True)
class OAuthResponse:
    status: int
    body: bytes
    headers: Mapping[str, str]


class OAuthTransport(Protocol):
    def request(
        self, *, method: str, url: str, headers: Mapping[str, str], body: bytes | None
    ) -> OAuthResponse: ...


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args: object, **kwargs: object) -> Request | None:
        del args, kwargs
        return None


class UrllibOAuthTransport:
    """Bounded transport for the two fixed GitHub OAuth API origins."""

    def __init__(self, *, timeout_seconds: float = 20.0) -> None:
        self._timeout_seconds = timeout_seconds

    def request(
        self, *, method: str, url: str, headers: Mapping[str, str], body: bytes | None
    ) -> OAuthResponse:
        _validate_oauth_url(url)
        request = Request(url, data=body, headers=dict(headers), method=method)
        try:
            with build_opener(_NoRedirect()).open(
                request, timeout=self._timeout_seconds
            ) as response:
                _validate_oauth_url(response.geturl())
                payload = response.read(MAX_OAUTH_RESPONSE_BYTES + 1)
                if len(payload) > MAX_OAUTH_RESPONSE_BYTES:
                    raise GitHubOAuthError("GITHUB_CREDENTIAL_INVALID")
                return OAuthResponse(
                    status=int(response.status),
                    body=payload,
                    headers={key.casefold(): value for key, value in response.headers.items()},
                )
        except GitHubOAuthError:
            raise
        except HTTPError as exc:
            payload = exc.read(MAX_OAUTH_RESPONSE_BYTES + 1)
            return OAuthResponse(
                status=int(exc.code),
                body=payload[:MAX_OAUTH_RESPONSE_BYTES],
                headers={key.casefold(): value for key, value in exc.headers.items()},
            )
        except (URLError, OSError, TimeoutError) as exc:
            raise GitHubOAuthError("GITHUB_LOGIN_UNAVAILABLE") from exc


@dataclass(frozen=True, slots=True)
class GitHubIdentity:
    user_id: str
    login: str


@dataclass(frozen=True, slots=True)
class OAuthStart:
    authorization_url: str
    state: str


@dataclass(frozen=True, slots=True)
class OAuthCompletion:
    session: AdminSession | None
    handoff: str | None


class CredentialCipher:
    """AES-256-GCM envelope used only for OAuth/PAT runtime values."""

    def __init__(self, key_material: str, *, key_version: int = 1) -> None:
        if len(key_material.encode("utf-8")) < 32 or key_version < 1:
            raise ValueError("credential cipher configuration is invalid")
        self._key = hashlib.sha256(key_material.encode("utf-8")).digest()
        self.key_version = key_version

    def encrypt(self, value: str, *, purpose: str) -> tuple[bytes, bytes]:
        nonce = secrets.token_bytes(AES_GCM_NONCE_BYTES)
        ciphertext = AESGCM(self._key).encrypt(nonce, value.encode("utf-8"), purpose.encode())
        return nonce, ciphertext

    def decrypt(self, nonce: bytes, ciphertext: bytes, *, purpose: str) -> str:
        try:
            return AESGCM(self._key).decrypt(nonce, ciphertext, purpose.encode()).decode("utf-8")
        except Exception as exc:
            raise GitHubOAuthError("OAUTH_TRANSACTION_INVALID") from exc


class GitHubOAuthClient:
    """Perform only the fixed token/user OAuth calls; never browser token flow."""

    def __init__(
        self,
        *,
        client_id: str | None,
        client_secret: str | None,
        callback_url: str | None,
        transport: OAuthTransport,
    ) -> None:
        if callback_url:
            _validate_callback_url(callback_url)
        self._client_id = client_id
        self._client_secret = client_secret
        self._callback_url = callback_url
        self._transport = transport

    @property
    def oauth_available(self) -> bool:
        """Whether the Web Flow credentials are complete and usable."""

        return bool(self._client_id and self._client_secret and self._callback_url)

    def authorization_url(self, *, state: str, code_challenge: str) -> str:
        if not self.oauth_available:
            raise GitHubOAuthError("GITHUB_LOGIN_UNAVAILABLE")
        assert self._client_id is not None
        assert self._callback_url is not None
        return f"{GITHUB_AUTHORIZE_URL}?{
            urlencode(
                {
                    'client_id': self._client_id,
                    'redirect_uri': self._callback_url,
                    'state': state,
                    'code_challenge': code_challenge,
                    'code_challenge_method': 'S256',
                }
            )
        }"

    def exchange_code(self, *, code: str, verifier: str) -> str:
        if not code or not verifier:
            raise GitHubOAuthError("OAUTH_TRANSACTION_INVALID")
        if not self.oauth_available:
            raise GitHubOAuthError("GITHUB_LOGIN_UNAVAILABLE")
        assert self._client_id is not None
        assert self._client_secret is not None
        assert self._callback_url is not None
        body = urlencode(
            {
                "client_id": self._client_id,
                "client_secret": self._client_secret,
                "code": code,
                "redirect_uri": self._callback_url,
                "code_verifier": verifier,
            }
        ).encode()
        response = self._transport.request(
            method="POST",
            url=GITHUB_TOKEN_URL,
            headers={
                "Accept": "application/json",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            body=body,
        )
        if response.status != 200:
            raise GitHubOAuthError("OAUTH_AUTHORIZATION_DENIED")
        payload = _json_object(response.body, "OAUTH_AUTHORIZATION_DENIED")
        scope = str(payload.get("scope", "")).strip()
        if scope:
            raise GitHubOAuthError("GITHUB_SCOPE_UNSAFE")
        token = payload.get("access_token")
        if not isinstance(token, str) or not token:
            raise GitHubOAuthError("OAUTH_AUTHORIZATION_DENIED")
        return token

    def identity(self, token: str) -> GitHubIdentity:
        response = self._transport.request(
            method="GET",
            url=GITHUB_USER_URL,
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {token}",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            body=None,
        )
        if response.status == 401:
            raise GitHubOAuthError("GITHUB_CREDENTIAL_INVALID")
        if response.status != 200:
            raise GitHubOAuthError("GITHUB_LOGIN_UNAVAILABLE")
        scopes = response.headers.get("x-oauth-scopes", "").strip()
        if scopes:
            raise GitHubOAuthError("GITHUB_SCOPE_UNSAFE")
        payload = _json_object(response.body, "GITHUB_CREDENTIAL_INVALID")
        user_id = payload.get("id")
        login = payload.get("login")
        if isinstance(user_id, bool) or not isinstance(user_id, int) or user_id <= 0:
            raise GitHubOAuthError("GITHUB_CREDENTIAL_INVALID")
        if not isinstance(login, str) or not login or len(login) > 100:
            raise GitHubOAuthError("GITHUB_CREDENTIAL_INVALID")
        return GitHubIdentity(user_id=str(user_id), login=login)

    def validate_public_read(self, token: str) -> GitHubIdentity:
        """Validate an OAuth/PAT credential without turning it into identity auth."""

        identity = self.identity(token)
        response = self._transport.request(
            method="POST",
            url=GITHUB_GRAPHQL_URL,
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            body=b'{"query":"query { viewer { id login } }"}',
        )
        if response.status == 401:
            raise GitHubOAuthError("GITHUB_CREDENTIAL_INVALID")
        if response.status != 200:
            raise GitHubOAuthError("GITHUB_LOGIN_UNAVAILABLE")
        payload = _json_object(response.body, "GITHUB_CREDENTIAL_INVALID")
        errors = payload.get("errors")
        if errors is not None and (not isinstance(errors, list) or errors):
            raise GitHubOAuthError("GITHUB_CREDENTIAL_INVALID")
        data = payload.get("data")
        if not isinstance(data, dict):
            raise GitHubOAuthError("GITHUB_CREDENTIAL_INVALID")
        viewer = data.get("viewer")
        if not isinstance(viewer, dict):
            raise GitHubOAuthError("GITHUB_CREDENTIAL_INVALID")
        viewer_id = viewer.get("id")
        viewer_login = viewer.get("login")
        if (
            not isinstance(viewer_id, str)
            or not viewer_id
            or len(viewer_id) > 256
            or not isinstance(viewer_login, str)
            or not viewer_login
            or len(viewer_login) > 100
        ):
            raise GitHubOAuthError("GITHUB_CREDENTIAL_INVALID")
        return identity

    def validate_pat(self, token: str) -> GitHubIdentity:
        """Backward-compatible name for public-read PAT validation."""

        return self.validate_public_read(token)


class GitHubIdentityService:
    """Persist bounded OAuth transactions and safe credential envelopes."""

    def __init__(
        self,
        *,
        database: RuntimeDatabase,
        sessions: AdminSessionService,
        oauth: GitHubOAuthClient,
        cipher: CredentialCipher,
        recovery_available: bool,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self._database = database
        self._sessions = sessions
        self._oauth = oauth
        self._cipher = cipher
        self._recovery_available = recovery_available
        self._now = now or (lambda: datetime.now(UTC))

    @property
    def oauth_available(self) -> bool:
        """Expose OAuth login availability separately from PAT management."""

        return self._oauth.oauth_available

    def start(
        self,
        *,
        intent: str,
        setup_code: str | None = None,
        session_token: str | None = None,
    ) -> OAuthStart:
        if intent not in {"login", "setup", "link"}:
            raise GitHubOAuthError("OAUTH_TRANSACTION_INVALID")
        if not self._oauth.oauth_available:
            raise GitHubOAuthError("GITHUB_LOGIN_UNAVAILABLE")
        setup_hash: str | None = None
        session_hash: str | None = None
        if intent == "setup":
            if not self._recovery_available:
                raise GitHubOAuthError("GITHUB_LOGIN_UNAVAILABLE")
            setup_hash = self._sessions.verify_setup_proof(setup_code or "")
        elif intent == "link":
            if not session_token:
                raise AdminAuthError("AUTHENTICATION_REQUIRED")
            self._sessions.require_recent_auth(session_token)
            session_hash = _token_hash(session_token)
        state = secrets.token_urlsafe(OAUTH_STATE_BYTES)
        verifier = secrets.token_urlsafe(PKCE_VERIFIER_BYTES)
        challenge = _pkce_challenge(verifier)
        now = _utc(self._now())
        nonce, ciphertext = self._cipher.encrypt(verifier, purpose="oauth-pkce")
        with self._database.connection() as connection:
            try:
                connection.execute("BEGIN IMMEDIATE")
                connection.execute(
                    "DELETE FROM admin_oauth_transactions "
                    "WHERE expires_at <= ? OR consumed_at IS NOT NULL",
                    (_time(now),),
                )
                connection.execute(
                    """
                    INSERT INTO admin_oauth_transactions(
                        state_hash, intent, verifier_nonce, verifier_ciphertext,
                        setup_code_hash, session_hash, created_at, expires_at, return_path
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, '/admin')
                    """,
                    (
                        _token_hash(state),
                        intent,
                        nonce,
                        ciphertext,
                        setup_hash,
                        session_hash,
                        _time(now),
                        _time(now + OAUTH_TRANSACTION_TTL),
                    ),
                )
                connection.execute("COMMIT")
            except sqlite3.Error as exc:
                _rollback(connection)
                raise RuntimeDatabaseError("runtime_oauth_transaction_failed") from exc
        return OAuthStart(
            authorization_url=self._oauth.authorization_url(state=state, code_challenge=challenge),
            state=state,
        )

    def complete(self, *, state: str, cookie_state: str, code: str) -> OAuthCompletion:
        if not state or not cookie_state or not hmac.compare_digest(state, cookie_state):
            raise GitHubOAuthError("OAUTH_TRANSACTION_INVALID")
        state_hash = _token_hash(state)
        now = _utc(self._now())
        with self._database.connection() as connection:
            try:
                connection.execute("BEGIN IMMEDIATE")
                row = connection.execute(
                    "SELECT * FROM admin_oauth_transactions WHERE state_hash = ?", (state_hash,)
                ).fetchone()
                if (
                    row is None
                    or row["consumed_at"] is not None
                    or now >= _parse_time(str(row["expires_at"]))
                ):
                    _rollback(connection)
                    raise GitHubOAuthError("OAUTH_TRANSACTION_EXPIRED")
                connection.execute(
                    "UPDATE admin_oauth_transactions SET consumed_at = ? WHERE state_hash = ?",
                    (_time(now), state_hash),
                )
                connection.execute("COMMIT")
            except GitHubOAuthError:
                raise
            except sqlite3.Error as exc:
                _rollback(connection)
                raise RuntimeDatabaseError("runtime_oauth_transaction_failed") from exc
        verifier = self._cipher.decrypt(
            bytes(row["verifier_nonce"]), bytes(row["verifier_ciphertext"]), purpose="oauth-pkce"
        )
        token = self._oauth.exchange_code(code=code, verifier=verifier)
        identity = self._oauth.identity(token)
        intent = str(row["intent"])
        session: AdminSession | None
        if intent == "login":
            session = self._sessions.login_github(
                github_user_id=identity.user_id,
                github_login=identity.login,
                remote_identity="github-oauth",
            )
        elif intent == "setup":
            setup_hash = row["setup_code_hash"]
            if not isinstance(setup_hash, str):
                raise GitHubOAuthError("OAUTH_TRANSACTION_INVALID")
            session = self._sessions.setup_github_owner(
                setup_code_hash=setup_hash,
                github_user_id=identity.user_id,
                github_login=identity.login,
                recovery_available=self._recovery_available,
            )
        else:
            session_hash = row["session_hash"]
            if not isinstance(session_hash, str):
                raise GitHubOAuthError("OAUTH_TRANSACTION_INVALID")
            # Session hashes never leave runtime state; recover the active raw
            # cookie is unnecessary because start already enforced recent auth.
            self._link_from_transaction(
                session_hash=session_hash,
                github_user_id=identity.user_id,
                github_login=identity.login,
            )
            session = None
        self._store_credential(
            purpose="identity_public_read",
            token=token,
            identity=identity,
            now=now,
        )
        return OAuthCompletion(
            session=session,
            handoff=self._create_handoff(session, now=now) if session is not None else None,
        )

    def consume_handoff(self, *, handoff: str, session_token: str) -> str:
        """Return CSRF once to the same new session without putting it in a URL."""

        if not handoff or not session_token:
            raise GitHubOAuthError("OAUTH_TRANSACTION_INVALID")
        now = _utc(self._now())
        handoff_hash = _token_hash(handoff)
        session_hash = _token_hash(session_token)
        with self._database.connection() as connection:
            try:
                connection.execute("BEGIN IMMEDIATE")
                row = connection.execute(
                    "SELECT csrf_nonce, csrf_ciphertext, expires_at, consumed_at, session_hash "
                    "FROM admin_oauth_handoffs WHERE handoff_hash = ?",
                    (handoff_hash,),
                ).fetchone()
                if (
                    row is None
                    or row["consumed_at"] is not None
                    or now >= _parse_time(str(row["expires_at"]))
                    or not hmac.compare_digest(str(row["session_hash"]), session_hash)
                ):
                    _rollback(connection)
                    raise GitHubOAuthError("OAUTH_TRANSACTION_INVALID")
                connection.execute(
                    "UPDATE admin_oauth_handoffs SET consumed_at = ? WHERE handoff_hash = ?",
                    (_time(now), handoff_hash),
                )
                connection.execute("COMMIT")
            except GitHubOAuthError:
                raise
            except sqlite3.Error as exc:
                _rollback(connection)
                raise RuntimeDatabaseError("runtime_oauth_transaction_failed") from exc
        return self._cipher.decrypt(
            bytes(row["csrf_nonce"]), bytes(row["csrf_ciphertext"]), purpose="oauth-csrf"
        )

    def connections(self) -> list[dict[str, object]]:
        with self._database.connection() as connection:
            rows = connection.execute(
                """
                SELECT credential_id, purpose, github_login, expires_at, last_validated_at, status
                FROM admin_github_credentials ORDER BY credential_id
                """
            ).fetchall()
        return [
            {
                "id": int(row["credential_id"]),
                "purpose": str(row["purpose"]),
                "github_login": str(row["github_login"]) if row["github_login"] else None,
                "expires_at": str(row["expires_at"]) if row["expires_at"] else None,
                "last_validated_at": (
                    str(row["last_validated_at"]) if row["last_validated_at"] else None
                ),
                "status": str(row["status"]),
            }
            for row in rows
        ]

    def public_read_credentials(self) -> tuple[PublicReadCredential, ...]:
        """Return server-only decryptions eligible for batch analysis.

        The return value is deliberately a resolver-only value object whose
        token field is excluded from ``repr``.  It must never cross an HTTP,
        event, log, or durable-preflight boundary.  A ciphertext that can no
        longer be authenticated is made unavailable rather than retried under
        a different credential purpose.
        """

        with self._database.connection() as connection:
            rows = connection.execute(
                """
                SELECT credential_id, purpose, token_nonce, token_ciphertext,
                       github_login, status
                FROM admin_github_credentials
                WHERE purpose IN ('identity_public_read', 'public_read')
                ORDER BY credential_id
                """
            ).fetchall()
        credentials: list[PublicReadCredential] = []
        for row in rows:
            credential_id = int(row["credential_id"])
            purpose = str(row["purpose"])
            try:
                token = self._cipher.decrypt(
                    bytes(row["token_nonce"]),
                    bytes(row["token_ciphertext"]),
                    purpose=purpose,
                )
                credentials.append(
                    PublicReadCredential(
                        credential_id=credential_id,
                        purpose=CredentialPurpose(purpose),
                        status=str(row["status"]),
                        token=token,
                        github_login=(
                            str(row["github_login"]) if row["github_login"] is not None else None
                        ),
                    )
                )
            except (GitHubOAuthError, ValueError):
                self._set_credential_status(credential_id, status="invalid")
        return tuple(credentials)

    def mark_connection_required(self, credential_id: int) -> None:
        """Persist a selected public-read credential's `401` fail-closed state."""

        self._set_credential_status(credential_id, status="connection_required")

    def save_pat(self, token: str) -> dict[str, object]:
        if not token or len(token) > 1024:
            raise GitHubOAuthError("GITHUB_CREDENTIAL_INVALID")
        identity = self._oauth.validate_pat(token)
        self._store_credential(
            purpose="public_read", token=token, identity=identity, now=_utc(self._now())
        )
        return {"purpose": "public_read", "github_login": identity.login, "status": "ready"}

    def check_credential(self, credential_id: int) -> dict[str, object]:
        """Revalidate a persisted public-read credential without exposing it."""

        with self._database.connection() as connection:
            row = connection.execute(
                """
                SELECT purpose, token_nonce, token_ciphertext
                FROM admin_github_credentials WHERE credential_id = ?
                """,
                (credential_id,),
            ).fetchone()
        if row is None:
            raise GitHubOAuthError("GITHUB_CREDENTIAL_INVALID")

        purpose = str(row["purpose"])
        try:
            token = self._cipher.decrypt(
                bytes(row["token_nonce"]), bytes(row["token_ciphertext"]), purpose=purpose
            )
            identity = self._oauth.validate_public_read(token)
        except GitHubOAuthError as exc:
            status = "connection_required" if exc.code == "GITHUB_CREDENTIAL_INVALID" else "invalid"
            self._set_credential_status(credential_id, status=status)
            if exc.code == "GITHUB_CREDENTIAL_INVALID":
                raise GitHubOAuthError("GITHUB_CONNECTION_REQUIRED") from exc
            raise

        now = _utc(self._now())
        with self._database.connection() as connection:
            connection.execute(
                """
                UPDATE admin_github_credentials
                SET github_login = ?, last_validated_at = ?, status = 'ready', updated_at = ?
                WHERE credential_id = ?
                """,
                (identity.login[:100], _time(now), _time(now), credential_id),
            )
        return {
            "id": credential_id,
            "purpose": purpose,
            "github_login": identity.login,
            "status": "ready",
        }

    def delete_credential(self, credential_id: int) -> None:
        with self._database.connection() as connection:
            connection.execute(
                "DELETE FROM admin_github_credentials WHERE credential_id = ?", (credential_id,)
            )

    def _set_credential_status(self, credential_id: int, *, status: str) -> None:
        if status not in {"connection_required", "invalid"}:
            raise ValueError("credential status is invalid")
        now = _utc(self._now())
        with self._database.connection() as connection:
            connection.execute(
                """
                UPDATE admin_github_credentials SET status = ?, updated_at = ?
                WHERE credential_id = ?
                """,
                (status, _time(now), credential_id),
            )

    def _link_from_transaction(
        self, *, session_hash: str, github_user_id: str, github_login: str
    ) -> None:
        now = _utc(self._now())
        with self._database.connection() as connection:
            try:
                connection.execute("BEGIN IMMEDIATE")
                row = connection.execute(
                    """
                    SELECT session.authenticated_at, session.revoked_at, session.idle_expires_at,
                           session.absolute_expires_at, session.session_epoch,
                           state.session_epoch AS current_epoch
                    FROM admin_sessions AS session
                    JOIN admin_state AS state ON state.state_key = 'current'
                    WHERE session.session_hash = ?
                    """,
                    (session_hash,),
                ).fetchone()
                if (
                    row is None
                    or row["revoked_at"] is not None
                    or row["authenticated_at"] is None
                    or now >= _parse_time(str(row["idle_expires_at"]))
                    or now >= _parse_time(str(row["absolute_expires_at"]))
                    or int(row["session_epoch"]) != int(row["current_epoch"])
                    or now - _parse_time(str(row["authenticated_at"])) > timedelta(minutes=5)
                ):
                    _rollback(connection)
                    raise AdminAuthError("RECENT_AUTHENTICATION_REQUIRED")
                existing = connection.execute(
                    "SELECT github_user_id FROM admin_auth_methods WHERE method = 'github'"
                ).fetchone()
                if existing is not None and str(existing["github_user_id"]) != github_user_id:
                    _rollback(connection)
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
            except (AdminAuthError, GitHubOAuthError):
                raise
            except sqlite3.Error as exc:
                _rollback(connection)
                raise RuntimeDatabaseError("runtime_admin_session_failed") from exc

    def _store_credential(
        self, *, purpose: str, token: str, identity: GitHubIdentity, now: datetime
    ) -> None:
        nonce, ciphertext = self._cipher.encrypt(token, purpose=purpose)
        with self._database.connection() as connection:
            try:
                connection.execute("BEGIN IMMEDIATE")
                connection.execute(
                    """
                    INSERT INTO admin_github_credentials(
                        purpose, token_nonce, token_ciphertext, key_version, github_user_id,
                        github_login, expires_at, last_validated_at, status, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, NULL, ?, 'ready', ?, ?)
                    ON CONFLICT(purpose, github_user_id) DO UPDATE SET
                        token_nonce = excluded.token_nonce,
                        token_ciphertext = excluded.token_ciphertext,
                        key_version = excluded.key_version,
                        github_login = excluded.github_login,
                        last_validated_at = excluded.last_validated_at,
                        status = excluded.status,
                        updated_at = excluded.updated_at
                    """,
                    (
                        purpose,
                        nonce,
                        ciphertext,
                        self._cipher.key_version,
                        identity.user_id,
                        identity.login[:100],
                        _time(now),
                        _time(now),
                        _time(now),
                    ),
                )
                connection.execute("COMMIT")
            except sqlite3.Error as exc:
                _rollback(connection)
                raise RuntimeDatabaseError("runtime_github_credential_failed") from exc

    def _create_handoff(self, session: AdminSession, *, now: datetime) -> str:
        handoff = secrets.token_urlsafe(32)
        nonce, ciphertext = self._cipher.encrypt(session.csrf_token, purpose="oauth-csrf")
        with self._database.connection() as connection:
            try:
                connection.execute("BEGIN IMMEDIATE")
                connection.execute(
                    "DELETE FROM admin_oauth_handoffs "
                    "WHERE expires_at <= ? OR consumed_at IS NOT NULL",
                    (_time(now),),
                )
                connection.execute(
                    """
                    INSERT INTO admin_oauth_handoffs(
                        handoff_hash, session_hash, csrf_nonce, csrf_ciphertext, expires_at
                    ) VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        _token_hash(handoff),
                        _token_hash(session.session_token),
                        nonce,
                        ciphertext,
                        _time(now + timedelta(minutes=2)),
                    ),
                )
                connection.execute("COMMIT")
            except sqlite3.Error as exc:
                _rollback(connection)
                raise RuntimeDatabaseError("runtime_oauth_transaction_failed") from exc
        return handoff


def _pkce_challenge(verifier: str) -> str:
    return (
        base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    )


def _token_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _json_object(payload: bytes, code: str) -> dict[str, object]:
    try:
        decoded = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise GitHubOAuthError(code) from exc
    if not isinstance(decoded, dict):
        raise GitHubOAuthError(code)
    return decoded


def _validate_oauth_url(value: str) -> None:
    parsed = urlsplit(value)
    allowed = {
        ("https", "github.com", "/login/oauth/authorize"),
        ("https", "github.com", "/login/oauth/access_token"),
        ("https", "api.github.com", "/user"),
        ("https", "api.github.com", "/graphql"),
    }
    if (
        (parsed.scheme, parsed.hostname, parsed.path) not in allowed
        or parsed.username
        or parsed.password
        or parsed.port not in {None, 443}
    ):
        raise GitHubOAuthError("GITHUB_LOGIN_UNAVAILABLE")


def _validate_callback_url(value: str) -> None:
    parsed = urlsplit(value)
    allowed_scheme = parsed.scheme == "https" or (
        parsed.scheme == "http" and parsed.hostname in {"localhost", "127.0.0.1"}
    )
    if (
        not allowed_scheme
        or not parsed.netloc
        or parsed.path != "/api/admin/github/callback"
        or parsed.query
        or parsed.fragment
        or parsed.username
        or parsed.password
    ):
        raise ValueError("GitHub OAuth callback is invalid")


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise RuntimeError("OAuth clock must be timezone-aware")
    return value.astimezone(UTC)


def _time(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _parse_time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)


def _rollback(connection: sqlite3.Connection) -> None:
    if connection.in_transaction:
        connection.execute("ROLLBACK")
