from __future__ import annotations

import base64
import hashlib
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest
from argon2 import PasswordHasher, Type
from fastapi.testclient import TestClient

from reponpc.admin.auth import AdminAuthError, AdminSessionService, issue_admin_setup_code
from reponpc.admin.oauth import (
    GITHUB_GRAPHQL_URL,
    GITHUB_TOKEN_URL,
    GITHUB_USER_URL,
    CredentialCipher,
    GitHubIdentityService,
    GitHubOAuthClient,
    GitHubOAuthError,
    OAuthResponse,
)
from reponpc.main import create_app
from reponpc.runtime.database import MIGRATIONS, RuntimeDatabase

ORIGIN = "https://portfolio.example.com"
OAUTH_TOKEN = "OAUTH_TOKEN_CANARY_DO_NOT_LOG"
PAT_TOKEN = "PAT_TOKEN_CANARY_DO_NOT_LOG"


class Clock:
    def __init__(self) -> None:
        self.value = datetime(2026, 8, 16, tzinfo=UTC)

    def __call__(self) -> datetime:
        return self.value

    def advance(self, **kwargs: int) -> None:
        self.value += timedelta(**kwargs)


class FakeGitHubOAuthTransport:
    def __init__(
        self,
        *,
        user_id: int = 42,
        login: str = "owner",
        scope: str = "",
        graphql_body: bytes | None = None,
    ) -> None:
        self.user_id = user_id
        self.login = login
        self.scope = scope
        self.graphql_body = graphql_body
        self.requests: list[tuple[str, str, dict[str, str], bytes | None]] = []

    def request(
        self, *, method: str, url: str, headers: dict[str, str], body: bytes | None
    ) -> OAuthResponse:
        self.requests.append((method, url, dict(headers), body))
        if url == GITHUB_TOKEN_URL:
            return OAuthResponse(
                status=200,
                body=json.dumps({"access_token": OAUTH_TOKEN, "scope": self.scope}).encode(),
                headers={},
            )
        if url == GITHUB_USER_URL:
            return OAuthResponse(
                status=200,
                body=json.dumps({"id": self.user_id, "login": self.login}).encode(),
                headers={"x-oauth-scopes": self.scope},
            )
        if url == GITHUB_GRAPHQL_URL:
            return OAuthResponse(
                status=200,
                body=self.graphql_body or b'{"data":{"viewer":{"id":"42","login":"owner"}}}',
                headers={},
            )
        raise AssertionError(f"unexpected OAuth URL: {url}")


def _service(
    tmp_path: Path,
    *,
    clock: Clock,
    local_password: bool = True,
) -> tuple[AdminSessionService, RuntimeDatabase]:
    database = RuntimeDatabase(tmp_path)
    database.initialize()
    return (
        AdminSessionService(
            database=database,
            username="owner" if local_password else None,
            password_hash=(PasswordHasher(type=Type.ID).hash("npcx") if local_password else None),
            identity_hmac_key=b"i" * 32,
            now=clock,
        ),
        database,
    )


def _identity_service(
    database: RuntimeDatabase,
    sessions: AdminSessionService,
    transport: FakeGitHubOAuthTransport,
    *,
    clock: Clock,
    recovery_available: bool = True,
    oauth_configured: bool = True,
) -> tuple[GitHubIdentityService, CredentialCipher]:
    cipher = CredentialCipher("credential-encryption-key-canary-material")
    return (
        GitHubIdentityService(
            database=database,
            sessions=sessions,
            oauth=GitHubOAuthClient(
                client_id="oauth-client-id" if oauth_configured else None,
                client_secret="oauth-client-secret-canary" if oauth_configured else None,
                callback_url=f"{ORIGIN}/api/admin/github/callback" if oauth_configured else None,
                transport=transport,
            ),
            cipher=cipher,
            recovery_available=recovery_available,
            now=clock,
        ),
        cipher,
    )


def test_oauth_pkce_state_is_server_bound_one_use_and_secret_free(tmp_path: Path) -> None:
    clock = Clock()
    sessions, database = _service(tmp_path, clock=clock, local_password=False)
    transport = FakeGitHubOAuthTransport()
    identity, cipher = _identity_service(database, sessions, transport, clock=clock)

    setup_code = issue_admin_setup_code(database, now=clock())
    started = identity.start(intent="setup", setup_code=setup_code)
    query = parse_qs(urlsplit(started.authorization_url).query)
    assert query["state"] == [started.state]
    assert query["code_challenge_method"] == ["S256"]
    assert "scope" not in query and "client_secret" not in query
    with database.connection() as connection:
        transaction = connection.execute(
            "SELECT state_hash, verifier_nonce, verifier_ciphertext FROM admin_oauth_transactions"
        ).fetchone()
    assert transaction is not None
    verifier = cipher.decrypt(
        bytes(transaction["verifier_nonce"]),
        bytes(transaction["verifier_ciphertext"]),
        purpose="oauth-pkce",
    )
    expected_challenge = (
        base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    )
    assert query["code_challenge"] == [expected_challenge]
    assert started.state not in repr(tuple(transaction))
    assert verifier not in repr(tuple(transaction))

    completed = identity.complete(
        state=started.state, cookie_state=started.state, code="oauth-code"
    )
    assert completed.session is not None and completed.handoff is not None
    with pytest.raises(GitHubOAuthError) as replay:
        identity.complete(state=started.state, cookie_state=started.state, code="oauth-code")
    assert replay.value.code == "OAUTH_TRANSACTION_EXPIRED"


def test_oauth_rejects_cross_transaction_and_expired_state_before_exchange(tmp_path: Path) -> None:
    clock = Clock()
    sessions, database = _service(tmp_path, clock=clock)
    transport = FakeGitHubOAuthTransport()
    identity, _ = _identity_service(database, sessions, transport, clock=clock)
    first = identity.start(intent="login")
    second = identity.start(intent="login")

    with pytest.raises(GitHubOAuthError) as cross_transaction:
        identity.complete(state=first.state, cookie_state=second.state, code="oauth-code")
    assert cross_transaction.value.code == "OAUTH_TRANSACTION_INVALID"
    assert transport.requests == []

    clock.advance(minutes=10)
    with pytest.raises(GitHubOAuthError) as expired:
        identity.complete(state=first.state, cookie_state=first.state, code="oauth-code")
    assert expired.value.code == "OAUTH_TRANSACTION_EXPIRED"
    assert transport.requests == []


def test_setup_requires_host_proof_and_recovery_before_github_only_owner(tmp_path: Path) -> None:
    clock = Clock()
    sessions, database = _service(tmp_path, clock=clock, local_password=False)
    setup_code = issue_admin_setup_code(database, now=clock())
    transport = FakeGitHubOAuthTransport()
    unavailable, _ = _identity_service(
        database, sessions, transport, clock=clock, recovery_available=False
    )
    with pytest.raises(GitHubOAuthError) as rejected:
        unavailable.start(intent="setup", setup_code=setup_code)
    assert rejected.value.code == "GITHUB_LOGIN_UNAVAILABLE"

    identity, _ = _identity_service(database, sessions, transport, clock=clock)
    started = identity.start(intent="setup", setup_code=setup_code)
    completed = identity.complete(
        state=started.state, cookie_state=started.state, code="oauth-code"
    )
    assert completed.session is not None
    assert sessions.setup_status().setup_required is False
    with database.connection() as connection:
        methods = connection.execute(
            "SELECT method, github_user_id FROM admin_auth_methods"
        ).fetchall()
    assert [(row["method"], row["github_user_id"]) for row in methods] == [("github", "42")]
    with pytest.raises(AdminAuthError) as final_method:
        sessions.unlink_github(session_token=completed.session.session_token)
    assert final_method.value.code == "LAST_AUTH_METHOD_REQUIRED"


def test_broad_scope_rejects_before_token_persistence(tmp_path: Path) -> None:
    clock = Clock()
    sessions, database = _service(tmp_path, clock=clock)
    transport = FakeGitHubOAuthTransport(scope="public_repo")
    identity, _ = _identity_service(database, sessions, transport, clock=clock)
    started = identity.start(intent="login")

    with pytest.raises(GitHubOAuthError) as rejected:
        identity.complete(state=started.state, cookie_state=started.state, code="oauth-code")
    assert rejected.value.code == "GITHUB_SCOPE_UNSAFE"
    with database.connection() as connection:
        stored_credentials = connection.execute(
            "SELECT COUNT(*) FROM admin_github_credentials"
        ).fetchone()[0]
    assert stored_credentials == 0


@pytest.mark.parametrize(
    "graphql_body",
    [
        b'{"errors":[{"message":"forbidden"}],"data":null}',
        b'{"data":{"viewer":null}}',
        b'{"data":{"viewer":{"id":"","login":"owner"}}}',
    ],
)
def test_public_read_probe_rejects_graphql_body_errors_or_invalid_viewer(
    tmp_path: Path,
    graphql_body: bytes,
) -> None:
    clock = Clock()
    sessions, database = _service(tmp_path, clock=clock)
    transport = FakeGitHubOAuthTransport(graphql_body=graphql_body)
    identity, _ = _identity_service(
        database,
        sessions,
        transport,
        clock=clock,
    )

    with pytest.raises(GitHubOAuthError) as rejected:
        identity.save_pat(PAT_TOKEN)

    assert rejected.value.code == "GITHUB_CREDENTIAL_INVALID"
    with database.connection() as connection:
        assert (
            connection.execute(
                "SELECT COUNT(*) FROM admin_github_credentials WHERE purpose = 'public_read'"
            ).fetchone()[0]
            == 0
        )


def test_migration_preserves_existing_password_owner(tmp_path: Path) -> None:
    clock = Clock()
    database = RuntimeDatabase(tmp_path)
    database.initialize(migrations=MIGRATIONS[:3])
    with database.connection() as connection:
        connection.execute(
            "INSERT INTO admin_owner(state_key, username, password_hash, created_at) "
            "VALUES ('current', 'owner', ?, ?)",
            (PasswordHasher(type=Type.ID).hash("npcx"), clock().isoformat()),
        )

    database.initialize()
    migrated = AdminSessionService(database=database, identity_hmac_key=b"i" * 32, now=clock)
    session = migrated.login(username="owner", password="npcx", remote_identity="test")
    migrated.authorize(session_token=session.session_token, csrf_token=session.csrf_token)
    assert migrated.auth_methods(github_configured=True).password_available is True


def test_batch_public_read_decryption_is_server_only_and_401_state_is_explicit(
    tmp_path: Path,
) -> None:
    clock = Clock()
    sessions, database = _service(tmp_path, clock=clock)
    transport = FakeGitHubOAuthTransport()
    identity, _ = _identity_service(database, sessions, transport, clock=clock)

    identity.save_pat(PAT_TOKEN)
    credentials = identity.public_read_credentials()

    assert len(credentials) == 1
    assert credentials[0].purpose.value == "public_read"
    assert credentials[0].status == "ready"
    assert PAT_TOKEN not in repr(credentials[0])
    identity.mark_connection_required(credentials[0].credential_id)
    assert identity.public_read_credentials()[0].status == "connection_required"
    assert PAT_TOKEN.encode() not in database.database_path.read_bytes()


def test_api_callback_handoff_connection_check_and_token_canaries(tmp_path: Path) -> None:
    clock = Clock()
    sessions, database = _service(tmp_path, clock=clock)
    transport = FakeGitHubOAuthTransport()
    identity, _ = _identity_service(database, sessions, transport, clock=clock)
    bootstrap = sessions.login(username="owner", password="npcx", remote_identity="bootstrap")
    sessions.link_github(
        session_token=bootstrap.session_token,
        github_user_id="42",
        github_login="owner",
    )
    app = create_app(
        runtime_database=database,
        admin_session_service=sessions,
        admin_origins=(ORIGIN,),
        github_identity_service=identity,
    )

    with TestClient(app, base_url=ORIGIN) as client:
        started = client.post(
            "/api/admin/session/github/start", headers={"Origin": ORIGIN}, follow_redirects=False
        )
        assert started.status_code == 303
        query = parse_qs(urlsplit(started.headers["location"]).query)
        oauth_cookie = started.headers["set-cookie"].split(";", 1)[0]
        client.cookies.clear()
        callback = client.get(
            "/api/admin/github/callback",
            params={"state": query["state"][0], "code": "oauth-code"},
            headers={"Cookie": oauth_cookie},
            follow_redirects=False,
        )
        assert callback.status_code == 303
        assert "github_oauth=success" in callback.headers["location"]
        assert "OAUTH_TOKEN_CANARY" not in callback.text
        callback_cookies = "; ".join(
            cookie.split(";", 1)[0]
            for cookie in callback.headers.get_list("set-cookie")
            if cookie.startswith(("__Host-reponpc_session=", "__Secure-reponpc_oauth_handoff="))
        )
        session_cookie = next(
            cookie
            for cookie in callback_cookies.split("; ")
            if cookie.startswith("__Host-reponpc_session=")
        )
        assert callback_cookies, callback.headers.get_list("set-cookie")
        handoff = client.get(
            "/api/admin/session/github/result", headers={"Cookie": callback_cookies}
        )
        assert handoff.status_code == 200, (callback_cookies, handoff.text)
        csrf_token = handoff.json()["csrf_token"]
        assert client.get("/api/admin/session/github/result").status_code == 401
        connections = client.get(
            "/api/admin/github/connections", headers={"Cookie": session_cookie}
        )
        assert connections.status_code == 200
        connection = connections.json()["connections"][0]
        checked = client.post(
            f"/api/admin/github/connections/{connection['id']}/check",
            headers={
                "Cookie": session_cookie,
                "Origin": ORIGIN,
                "X-CSRF-Token": csrf_token,
            },
        )
        assert checked.status_code == 200
        assert checked.json() == {
            "id": connection["id"],
            "purpose": "identity_public_read",
            "github_login": "owner",
            "status": "ready",
        }
        saved_pat = client.put(
            "/api/admin/github/connections/pat",
            headers={
                "Cookie": session_cookie,
                "Origin": ORIGIN,
                "X-CSRF-Token": csrf_token,
            },
            json={"token": PAT_TOKEN},
        )
        assert saved_pat.status_code == 201
        assert PAT_TOKEN not in saved_pat.text
        assert saved_pat.json() == {
            "purpose": "public_read",
            "github_login": "owner",
            "status": "ready",
        }

    persisted = database.database_path.read_bytes()
    assert OAUTH_TOKEN.encode() not in persisted
    assert PAT_TOKEN.encode() not in persisted
    assert b"oauth-client-secret-canary" not in persisted
    assert csrf_token.encode() not in persisted


def test_local_password_owner_can_manage_pat_without_oauth_configuration(tmp_path: Path) -> None:
    clock = Clock()
    sessions, database = _service(tmp_path, clock=clock)
    transport = FakeGitHubOAuthTransport()
    identity, _ = _identity_service(
        database,
        sessions,
        transport,
        clock=clock,
        oauth_configured=False,
    )
    app = create_app(
        runtime_database=database,
        admin_session_service=sessions,
        admin_origins=(ORIGIN,),
        github_identity_service=identity,
    )

    with TestClient(app, base_url=ORIGIN) as client:
        methods = client.get("/api/admin/auth/methods")
        assert methods.status_code == 200
        assert methods.json()["github"]["available"] is False

        unavailable_login = client.post(
            "/api/admin/session/github/start",
            headers={"Origin": ORIGIN},
            follow_redirects=False,
        )
        assert unavailable_login.status_code == 503
        assert unavailable_login.json()["error"]["code"] == "GITHUB_LOGIN_UNAVAILABLE"

        login = client.post(
            "/api/admin/session",
            headers={"Origin": ORIGIN},
            json={"username": "owner", "password": "npcx"},
        )
        assert login.status_code == 200
        csrf_token = login.json()["csrf_token"]
        saved = client.put(
            "/api/admin/github/connections/pat",
            headers={
                "Origin": ORIGIN,
                "X-CSRF-Token": csrf_token,
            },
            json={"token": PAT_TOKEN},
        )

    assert saved.status_code == 201
    assert saved.json() == {
        "purpose": "public_read",
        "github_login": "owner",
        "status": "ready",
    }


def test_oauth_setup_guide_is_non_sensitive_and_uses_canonical_callback(
    tmp_path: Path,
) -> None:
    clock = Clock()
    sessions, database = _service(tmp_path, clock=clock)
    transport = FakeGitHubOAuthTransport()
    identity, _ = _identity_service(
        database,
        sessions,
        transport,
        clock=clock,
        oauth_configured=False,
    )
    app = create_app(
        runtime_database=database,
        admin_session_service=sessions,
        admin_origins=(ORIGIN,),
        github_identity_service=identity,
    )

    with TestClient(app, base_url=ORIGIN) as client:
        response = client.get("/api/admin/github/oauth/setup-guide")

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.json() == {
        "configured": False,
        "callback_url": f"{ORIGIN}/api/admin/github/callback",
        "documentation_url": (
            "https://docs.github.com/en/apps/oauth-apps/building-oauth-apps/creating-an-oauth-app"
        ),
        "next_step": "configure_host_secrets_restart_then_recheck",
    }
    assert "oauth-client-secret-canary" not in response.text
    assert "credential-encryption-key-canary" not in response.text
    assert "OAUTH_TOKEN_CANARY" not in response.text
    assert "owner" not in response.text


def test_oauth_setup_guide_reports_configured_without_identity_disclosure(
    tmp_path: Path,
) -> None:
    clock = Clock()
    sessions, database = _service(tmp_path, clock=clock)
    identity, _ = _identity_service(
        database,
        sessions,
        FakeGitHubOAuthTransport(),
        clock=clock,
    )
    app = create_app(
        runtime_database=database,
        admin_session_service=sessions,
        admin_origins=(ORIGIN,),
        github_identity_service=identity,
        github_oauth_callback_url=f"{ORIGIN}/api/admin/github/callback",
    )

    with TestClient(app, base_url=ORIGIN) as client:
        response = client.get("/api/admin/github/oauth/setup-guide")

    assert response.status_code == 200
    assert response.json()["configured"] is True
    assert response.json()["next_step"] == "continue_with_github"
    assert set(response.json()) == {
        "configured",
        "callback_url",
        "documentation_url",
        "next_step",
    }


def test_unlinked_github_callback_uses_generic_invalid_credentials(tmp_path: Path) -> None:
    clock = Clock()
    sessions, database = _service(tmp_path, clock=clock)
    transport = FakeGitHubOAuthTransport(user_id=999, login="unlinked-account")
    identity, _ = _identity_service(database, sessions, transport, clock=clock)
    app = create_app(
        runtime_database=database,
        admin_session_service=sessions,
        admin_origins=(ORIGIN,),
        github_identity_service=identity,
    )

    with TestClient(app, base_url=ORIGIN) as client:
        started = client.post(
            "/api/admin/session/github/start", headers={"Origin": ORIGIN}, follow_redirects=False
        )
        state = parse_qs(urlsplit(started.headers["location"]).query)["state"][0]
        oauth_cookie = started.headers["set-cookie"].split(";", 1)[0]
        client.cookies.clear()
        callback = client.get(
            "/api/admin/github/callback",
            params={"state": state, "code": "oauth-code"},
            headers={"Cookie": oauth_cookie},
            follow_redirects=False,
        )

    assert callback.status_code == 303
    assert callback.headers["location"] == "/admin?github_oauth=invalid_credentials"
    assert "owner" not in callback.headers["location"]
    assert "unlinked-account" not in callback.headers["location"]


def test_authenticated_link_uses_csrf_json_start_and_keeps_identity_stable(tmp_path: Path) -> None:
    clock = Clock()
    sessions, database = _service(tmp_path, clock=clock)
    transport = FakeGitHubOAuthTransport(user_id=42, login="owner-old-login")
    identity, _ = _identity_service(database, sessions, transport, clock=clock)
    app = create_app(
        runtime_database=database,
        admin_session_service=sessions,
        admin_origins=(ORIGIN,),
        github_identity_service=identity,
    )

    with TestClient(app, base_url=ORIGIN) as client:
        login = client.post(
            "/api/admin/session",
            headers={"Origin": ORIGIN},
            json={"username": "owner", "password": "npcx"},
        )
        csrf_token = login.json()["csrf_token"]
        started = client.post(
            "/api/admin/identity/github/link/start",
            headers={"Origin": ORIGIN, "X-CSRF-Token": csrf_token, "Accept": "application/json"},
        )
        assert started.status_code == 200
        assert set(started.json()) == {"authorization_url"}
        query = parse_qs(urlsplit(started.json()["authorization_url"]).query)
        oauth_cookie = started.headers["set-cookie"].split(";", 1)[0]
        client.cookies.clear()
        callback = client.get(
            "/api/admin/github/callback",
            params={"state": query["state"][0], "code": "oauth-code"},
            headers={"Cookie": oauth_cookie},
            follow_redirects=False,
        )
        assert callback.status_code == 303
        assert "github_oauth=success" in callback.headers["location"]
        transport.login = "owner-renamed"
        fresh_login = client.post(
            "/api/admin/session/github/start", headers={"Origin": ORIGIN}, follow_redirects=False
        )
        fresh_state = parse_qs(urlsplit(fresh_login.headers["location"]).query)["state"][0]
        fresh_oauth_cookie = fresh_login.headers["set-cookie"].split(";", 1)[0]
        renamed_callback = client.get(
            "/api/admin/github/callback",
            params={"state": fresh_state, "code": "oauth-code"},
            headers={"Cookie": fresh_oauth_cookie},
            follow_redirects=False,
        )
        assert renamed_callback.status_code == 303
    with database.connection() as connection:
        method = connection.execute(
            "SELECT github_user_id, github_login FROM admin_auth_methods WHERE method = 'github'"
        ).fetchone()
    assert method is not None
    assert (method["github_user_id"], method["github_login"]) == ("42", "owner-renamed")


def test_link_completion_accepts_the_current_recent_session(tmp_path: Path) -> None:
    clock = Clock()
    sessions, database = _service(tmp_path, clock=clock)
    transport = FakeGitHubOAuthTransport()
    identity, _ = _identity_service(database, sessions, transport, clock=clock)
    session = sessions.login(username="owner", password="npcx", remote_identity="test")
    started = identity.start(intent="link", session_token=session.session_token)

    assert (
        identity.complete(
            state=started.state, cookie_state=started.state, code="oauth-code"
        ).session
        is None
    )


def test_github_only_logout_all_requires_fresh_github_session(tmp_path: Path) -> None:
    clock = Clock()
    sessions, database = _service(tmp_path, clock=clock, local_password=False)
    setup_code = issue_admin_setup_code(database, now=clock())
    transport = FakeGitHubOAuthTransport()
    identity, _ = _identity_service(database, sessions, transport, clock=clock)
    started = identity.start(intent="setup", setup_code=setup_code)
    session = identity.complete(
        state=started.state, cookie_state=started.state, code="oauth-code"
    ).session
    assert session is not None
    clock.advance(minutes=6)
    with pytest.raises(AdminAuthError) as stale:
        sessions.logout_all(
            session_token=session.session_token, csrf_token=session.csrf_token, password=None
        )
    assert stale.value.code == "RECENT_AUTHENTICATION_REQUIRED"
    # A fresh GitHub login is the required reauthentication for a GitHub-only owner.
    login_started = identity.start(intent="login")
    fresh = identity.complete(
        state=login_started.state, cookie_state=login_started.state, code="oauth-code"
    ).session
    assert fresh is not None
    sessions.logout_all(
        session_token=fresh.session_token, csrf_token=fresh.csrf_token, password=None
    )
    with pytest.raises(AdminAuthError):
        sessions.authorize(session_token=fresh.session_token)
