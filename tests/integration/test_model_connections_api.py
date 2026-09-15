from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from argon2 import PasswordHasher, Type
from fastapi.testclient import TestClient

from reponpc.admin.auth import AdminSessionService
from reponpc.admin.chat_profiles import ChatProfileRegistry
from reponpc.admin.model_connections import ModelConnectionRegistry, ProtectedModelSecretStore
from reponpc.admin.operations import AdminOperations
from reponpc.main import create_app
from reponpc.runtime.database import RuntimeDatabase

ORIGIN = "https://portfolio.example.com"
PASSWORD = "correct horse battery staple"
CANARY_KEY = "MODEL_API_KEY_CANARY_42"
CANARY_URL = "https://private-gateway.example.test/v1"


def _application(tmp_path: Path):
    database = RuntimeDatabase(tmp_path / "runtime")
    database.initialize()
    auth = AdminSessionService(
        database=database,
        username="admin",
        password_hash=PasswordHasher(type=Type.ID).hash(PASSWORD),
        identity_hmac_key=b"m" * 32,
        now=lambda: datetime(2026, 9, 10, tzinfo=UTC),
    )
    registry = ModelConnectionRegistry(
        database,
        ProtectedModelSecretStore(tmp_path / "secrets" / "model.key"),
    )
    chat_profiles = ChatProfileRegistry(database, registry, lambda _profile: None)
    operations = AdminOperations(
        github=None,
        database=database,
        public_base_url=ORIGIN,
        model_connections=registry,
        chat_profiles=chat_profiles,
    )
    return create_app(
        admin_session_service=auth,
        admin_origins=(ORIGIN,),
        admin_operations=operations,
    )


def _login(client: TestClient) -> str:
    response = client.post(
        "/api/admin/session",
        headers={"Origin": ORIGIN},
        json={"username": "admin", "password": PASSWORD},
    )
    assert response.status_code == 200
    return response.json()["csrf_token"]


def _body(*, url: str = CANARY_URL, key: str | None = CANARY_KEY) -> dict[str, object]:
    return {
        "display_name": "Private gateway",
        "provider": "openai_compatible",
        "base_url": url,
        "api_key": key,
        "credential_action": "replace" if key is not None else "retain",
    }


def test_model_connection_api_is_authenticated_write_only_and_revisioned(tmp_path: Path) -> None:
    app = _application(tmp_path)
    with TestClient(app, base_url=ORIGIN) as client:
        denied = client.get("/api/admin/model-connections", headers={"Origin": ORIGIN})
        assert denied.status_code == 401

        csrf = _login(client)
        empty = client.get("/api/admin/model-connections", headers={"Origin": ORIGIN})
        assert empty.status_code == 200
        assert empty.json() == {"connections": []}

        missing_csrf = client.post(
            "/api/admin/model-connections",
            headers={"Origin": ORIGIN},
            json=_body(),
        )
        assert missing_csrf.status_code == 403

        created = client.post(
            "/api/admin/model-connections",
            headers={"Origin": ORIGIN, "X-CSRF-Token": csrf},
            json=_body(),
        )
        assert created.status_code == 201
        assert CANARY_KEY not in created.text
        assert CANARY_URL not in created.text
        assert created.json()["key_configured"] is True
        connection_id = created.json()["connection_id"]

        listed = client.get("/api/admin/model-connections", headers={"Origin": ORIGIN})
        assert listed.status_code == 200
        assert listed.json()["connections"][0]["revision"] == 1
        assert CANARY_KEY not in listed.text
        assert CANARY_URL not in listed.text

        changed_without_key = client.put(
            f"/api/admin/model-connections/{connection_id}",
            headers={"Origin": ORIGIN, "X-CSRF-Token": csrf},
            json={
                **_body(url="https://other-gateway.example.test/v1", key=None),
                "credential_action": "retain",
            },
        )
        assert changed_without_key.status_code == 409
        assert changed_without_key.json()["error"]["code"] == "CREDENTIAL_REPLACE_REQUIRED"
        assert CANARY_KEY not in changed_without_key.text

        changed_path = client.put(
            f"/api/admin/model-connections/{connection_id}",
            headers={"Origin": ORIGIN, "X-CSRF-Token": csrf},
            json={
                **_body(url="https://private-gateway.example.test/v2", key=None),
                "credential_action": "retain",
            },
        )
        assert changed_path.status_code == 200
        assert changed_path.json()["revision"] == 2
        assert CANARY_KEY not in changed_path.text

        replaced = client.put(
            f"/api/admin/model-connections/{connection_id}",
            headers={"Origin": ORIGIN, "X-CSRF-Token": csrf},
            json=_body(url="https://other-gateway.example.test/v1", key="ROTATED_KEY_CANARY"),
        )
        assert replaced.status_code == 200
        assert replaced.json()["revision"] == 3
        assert "ROTATED_KEY_CANARY" not in replaced.text

        deleted = client.delete(
            f"/api/admin/model-connections/{connection_id}",
            headers={"Origin": ORIGIN, "X-CSRF-Token": csrf},
        )
        assert deleted.status_code == 204


def test_chat_profile_api_requires_probe_and_preserves_safe_revision_metadata(
    tmp_path: Path,
) -> None:
    app = _application(tmp_path)
    with TestClient(app, base_url=ORIGIN) as client:
        csrf = _login(client)
        connection = client.post(
            "/api/admin/model-connections",
            headers={"Origin": ORIGIN, "X-CSRF-Token": csrf},
            json=_body(key=None),
        )
        assert connection.status_code == 201
        connection_id = connection.json()["connection_id"]
        created = client.post(
            "/api/admin/chat-profiles",
            headers={"Origin": ORIGIN, "X-CSRF-Token": csrf},
            json={"connection_id": connection_id, "model_id": "typed-chat-model"},
        )
        assert created.status_code == 201
        profile_id = created.json()["profile_id"]
        assert created.json()["connection_revision"] == 1
        assert (
            client.post(
                f"/api/admin/chat-profiles/{profile_id}/activate",
                headers={"Origin": ORIGIN, "X-CSRF-Token": csrf},
            ).status_code
            == 409
        )
        listed = client.get("/api/admin/chat-profiles", headers={"Origin": ORIGIN})
        assert listed.status_code == 200
        assert listed.json()["profiles"][0]["model_id"] == "typed-chat-model"
        assert CANARY_KEY not in listed.text
        assert CANARY_URL not in listed.text
