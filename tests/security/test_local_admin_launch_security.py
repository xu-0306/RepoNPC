from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from reponpc.admin.auth import AdminSessionService, issue_admin_local_launch_grant
from reponpc.main import create_app
from reponpc.runtime.database import RuntimeDatabase

ORIGIN = "http://localhost:8000"
NOW = datetime(2026, 9, 7, 12, tzinfo=UTC)


def _local_app(tmp_path: Path, *, now: datetime = NOW):
    database = RuntimeDatabase(tmp_path)
    database.initialize()
    service = AdminSessionService(
        database=database,
        identity_hmac_key=b"i" * 32,
        deployment_profile="loopback_evaluation",
        now=lambda: now,
    )
    app = create_app(admin_session_service=service, admin_origins=(ORIGIN,))
    return app, database


def _exchange(client: TestClient, grant: str, **headers: str):
    return client.post(
        "/api/admin/session/local-launch",
        headers={"Origin": ORIGIN, **headers},
        json={"grant": grant},
    )


def test_local_launch_exchange_sets_session_cookie_without_reflecting_grant(
    tmp_path: Path,
) -> None:
    app, database = _local_app(tmp_path)
    grant = issue_admin_local_launch_grant(
        database,
        deployment_profile="loopback_evaluation",
        now=NOW,
    )

    with TestClient(
        app,
        base_url=ORIGIN,
        client=("127.0.0.1", 54321),
    ) as client:
        response = _exchange(client, grant)

    assert response.status_code == 200
    assert set(response.json()) == {"csrf_token", "expires_at", "absolute_expires_at"}
    assert grant not in response.text
    cookie = response.headers["set-cookie"]
    assert cookie.startswith("__Host-reponpc_session=")
    assert all(flag in cookie for flag in ("HttpOnly", "Path=/", "SameSite=strict", "Secure"))


def test_local_launch_replay_and_unknown_grants_have_one_generic_failure(
    tmp_path: Path,
) -> None:
    app, database = _local_app(tmp_path)
    grant = issue_admin_local_launch_grant(
        database,
        deployment_profile="loopback_evaluation",
        now=NOW,
    )

    with TestClient(app, base_url=ORIGIN, client=("::1", 54321)) as client:
        assert _exchange(client, grant).status_code == 200
        replay = _exchange(client, grant)
        unknown = _exchange(client, "not-the-current-grant")

    assert replay.status_code == unknown.status_code == 401
    replay_error = replay.json()["error"]
    unknown_error = unknown.json()["error"]
    assert {key: value for key, value in replay_error.items() if key != "request_id"} == {
        key: value for key, value in unknown_error.items() if key != "request_id"
    }
    assert replay_error["code"] == "LOCAL_LAUNCH_DENIED"
    assert grant not in replay.text


@pytest.mark.parametrize(
    "body",
    [
        b"",
        b"{",
        b"{}",
        b'{"grant":""}',
        b'{"grant":7}',
        b'{"grant":"candidate","extra":true}',
    ],
)
def test_malformed_local_launch_bodies_use_the_generic_failure(tmp_path: Path, body: bytes) -> None:
    app, _database = _local_app(tmp_path)

    with TestClient(app, base_url=ORIGIN, client=("127.0.0.1", 54321)) as client:
        response = client.post(
            "/api/admin/session/local-launch",
            headers={"Origin": ORIGIN, "Content-Type": "application/json"},
            content=body,
        )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "LOCAL_LAUNCH_DENIED"
    assert "candidate" not in response.text


def test_local_launch_failures_apply_per_peer_backoff_without_consuming_grant(
    tmp_path: Path,
) -> None:
    app, database = _local_app(tmp_path)
    grant = issue_admin_local_launch_grant(
        database,
        deployment_profile="loopback_evaluation",
        now=NOW,
    )

    with TestClient(app, base_url=ORIGIN, client=("127.0.0.1", 54321)) as client:
        denied = _exchange(client, "not-the-current-grant")
        throttled = _exchange(client, grant)
    with TestClient(app, base_url=ORIGIN, client=("::1", 54321)) as other_peer:
        accepted = _exchange(other_peer, grant)

    assert denied.status_code == throttled.status_code == 401
    assert denied.json()["error"]["code"] == "LOCAL_LAUNCH_DENIED"
    assert denied.json()["error"]["retry_after_seconds"] == 1
    assert throttled.json()["error"]["retry_after_seconds"] == 1
    assert accepted.status_code == 200


def test_expired_local_launch_grant_has_generic_failure(tmp_path: Path) -> None:
    app, database = _local_app(tmp_path, now=NOW + timedelta(minutes=3))
    grant = issue_admin_local_launch_grant(
        database,
        deployment_profile="loopback_evaluation",
        now=NOW,
    )

    with TestClient(app, base_url=ORIGIN, client=("127.0.0.1", 54321)) as client:
        response = _exchange(client, grant)

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "LOCAL_LAUNCH_DENIED"
    assert grant not in response.text


@pytest.mark.parametrize(
    ("client_host", "headers"),
    [
        ("203.0.113.10", {}),
        ("127.0.0.1", {"Origin": "http://attacker.example"}),
        ("127.0.0.1", {"Host": "attacker.example"}),
        ("127.0.0.1", {"Forwarded": "for=127.0.0.1;host=localhost:8000"}),
        ("127.0.0.1", {"X-Forwarded-For": "127.0.0.1"}),
        ("127.0.0.1", {"X-Forwarded-Host": "localhost:8000"}),
    ],
)
def test_local_launch_rejects_nonlocal_or_forwarded_request_context(
    tmp_path: Path,
    client_host: str,
    headers: dict[str, str],
) -> None:
    app, database = _local_app(tmp_path)
    grant = issue_admin_local_launch_grant(
        database,
        deployment_profile="loopback_evaluation",
        now=NOW,
    )

    with TestClient(app, base_url=ORIGIN, client=(client_host, 54321)) as client:
        response = _exchange(client, grant, **headers)

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "LOCAL_LAUNCH_DENIED"
    assert grant not in response.text


def test_local_auth_methods_contract_excludes_github_login(tmp_path: Path) -> None:
    app, _database = _local_app(tmp_path)

    with TestClient(app, base_url=ORIGIN, client=("127.0.0.1", 54321)) as client:
        response = client.get("/api/admin/auth/methods")

    assert response.status_code == 200
    assert response.json() == {
        "mode": "local_launch",
        "password": {"available": False},
        "setup_required": False,
    }


def test_loopback_logout_all_http_contract_consumes_a_fresh_named_grant(
    tmp_path: Path,
) -> None:
    app, database = _local_app(tmp_path)
    initial_grant = issue_admin_local_launch_grant(
        database,
        deployment_profile="loopback_evaluation",
        now=NOW,
    )

    with TestClient(app, base_url=ORIGIN, client=("127.0.0.1", 54321)) as client:
        session = _exchange(client, initial_grant)
        assert session.status_code == 200
        csrf_token = session.json()["csrf_token"]
        session_cookie = session.headers["set-cookie"].split(";", 1)[0]
        proof = issue_admin_local_launch_grant(
            database,
            deployment_profile="loopback_evaluation",
            now=NOW,
        )
        missing = client.request(
            "DELETE",
            "/api/admin/sessions",
            headers={
                "Cookie": session_cookie,
                "Origin": ORIGIN,
                "X-CSRF-Token": csrf_token,
            },
            json={},
        )
        revoked = client.request(
            "DELETE",
            "/api/admin/sessions",
            headers={
                "Cookie": session_cookie,
                "Origin": ORIGIN,
                "X-CSRF-Token": csrf_token,
            },
            json={"local_launch_grant": proof},
        )
        replay = _exchange(client, proof)

    assert missing.status_code == 401
    assert missing.json()["error"]["code"] == "LOCAL_LAUNCH_DENIED"
    assert revoked.status_code == 204
    assert proof not in revoked.text
    assert replay.status_code == 401
    assert replay.json()["error"]["code"] == "LOCAL_LAUNCH_DENIED"
