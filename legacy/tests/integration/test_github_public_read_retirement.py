from pathlib import Path

from fastapi.testclient import TestClient

from reponpc.main import create_app
from reponpc.runtime.database import RuntimeDatabase

ORIGIN = "https://owner.example"
REMOVED = "GITHUB_PUBLIC_READ_CREDENTIALS_REMOVED"
SECRET = "OAUTH_PAT_SECRET_CANARY"


def _app(tmp_path: Path) -> tuple[object, RuntimeDatabase]:
    database = RuntimeDatabase(tmp_path / "runtime")
    database.initialize()
    with database.connection() as connection:
        connection.execute(
            "INSERT INTO admin_owner(state_key, username, password_hash, created_at) "
            "VALUES ('current', 'owner', '$argon2id$preserved', 'created')"
        )
        connection.execute(
            """
            INSERT INTO admin_github_credentials(
              purpose, token_nonce, token_ciphertext, key_version, github_user_id,
              github_login, status, created_at, updated_at
            ) VALUES ('public_read', X'01', ?, 1, NULL, NULL, 'ready', 'created', 'updated')
            """,
            (SECRET.encode(),),
        )
        connection.commit()
    return create_app(runtime_database=database, admin_origins=(ORIGIN,)), database


def _state(database: RuntimeDatabase) -> tuple[tuple[object, ...], ...]:
    with database.connection() as connection:
        owner = connection.execute(
            "SELECT username, password_hash FROM admin_owner WHERE state_key = 'current'"
        ).fetchone()
        credentials = connection.execute(
            "SELECT purpose, token_nonce, token_ciphertext FROM admin_github_credentials"
        ).fetchall()
        transactions = connection.execute(
            "SELECT state_hash FROM admin_oauth_transactions"
        ).fetchall()
    assert owner is not None
    return (
        tuple(owner),
        *(tuple(row) for row in credentials),
        *(tuple(row) for row in transactions),
    )


def test_every_retired_route_returns_uniform_410_before_validation(tmp_path: Path) -> None:
    app, database = _app(tmp_path)
    before = _state(database)
    requests = (
        ("GET", "/api/admin/github/oauth/setup-guide", None, None),
        ("POST", "/api/admin/session/github/start", b"{", "application/json"),
        ("POST", "/api/admin/setup/github/start", SECRET.encode(), "text/plain"),
        ("POST", "/api/admin/identity/github/link/start", b"{}", "application/json"),
        ("DELETE", "/api/admin/identity/github", None, None),
        ("POST", "/api/admin/github/connections/oauth/start", b"{", "application/json"),
        ("GET", "/api/admin/github/callback?state=" + "x" * 4096 + "&code=" + SECRET, None, None),
        ("GET", "/api/admin/github/connections", None, None),
        ("PUT", "/api/admin/github/connections/pat", b"{", "application/json"),
        ("PUT", "/api/admin/github/connections/pat", (SECRET * 2000).encode(), "text/plain"),
        ("POST", "/api/admin/github/connections/0/check", None, None),
        ("POST", "/api/admin/github/connections/not-an-id/check", None, None),
        ("DELETE", "/api/admin/github/connections/0", None, None),
        ("DELETE", "/api/admin/github/connections/not-an-id", None, None),
    )

    with TestClient(app, base_url=ORIGIN) as client:
        for method, path, content, content_type in requests:
            headers = {"Content-Type": content_type} if content_type else {}
            response = client.request(method, path, content=content, headers=headers)
            assert response.status_code == 410, (method, path, response.text)
            assert response.json()["error"]["code"] == REMOVED
            assert SECRET not in response.text

    assert _state(database) == before
