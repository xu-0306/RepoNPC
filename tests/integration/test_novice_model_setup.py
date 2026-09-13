"""Novice setup contracts through authenticated APIs and real adapters/stores."""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path

import pytest
from argon2 import PasswordHasher
from fastapi.testclient import TestClient

from reponpc.admin.auth import AdminSessionService
from reponpc.admin.embedding_profiles import EmbeddingProfileInput, EmbeddingProfileRegistry
from reponpc.admin.model_connections import (
    ModelConnectionError,
    ModelConnectionInput,
    ModelConnectionRegistry,
    ProtectedModelSecretStore,
)
from reponpc.admin.operations import AdminOperations
from reponpc.main import _embedding_provider_from_connection, create_app
from reponpc.providers.http_transport import ProviderHttpResponse, UrllibProviderHttpTransport
from reponpc.runtime.database import MIGRATIONS, RuntimeDatabase, RuntimeDatabaseError

ORIGIN = "https://portfolio.example.com"
PASSWORD = "fixture novice setup password"
KEY = "SYNTHETIC_NOVICE_KEY_CANARY"
URL = "https://private-model.example.test/v1"


def application(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    database = RuntimeDatabase(tmp_path / "runtime")
    database.initialize()
    connections = ModelConnectionRegistry(
        database, ProtectedModelSecretStore(tmp_path / "secrets" / "key")
    )
    state = {"calls": 0, "mismatch": False, "status": 200}

    def response(_transport, _method, _url, **_kwargs):
        state["calls"] += 1
        if state["status"] != 200:
            return ProviderHttpResponse(state["status"], {}, KEY.encode())
        vector = [1.0, 0.0] if state["mismatch"] and state["calls"] % 2 == 0 else [0.0, 0.6, 0.8]
        payload = {"data": [{"embedding": vector}], "embeddings": [vector]}
        return ProviderHttpResponse(200, {}, json.dumps(payload).encode())

    monkeypatch.setattr(UrllibProviderHttpTransport, "request", response)

    def resolve(profile):
        connection = connections.get(profile.connection_reference)
        assert connection.revision == profile.connection_revision
        secret = connections.secret_for(connection.connection_id, profile.connection_revision)
        return _embedding_provider_from_connection(
            connection.provider,
            secret.base_url,
            secret.api_key,
            profile.identity if profile.dimension is not None else None,
            model=profile.model_id,
            query_prefix=profile.query_prefix,
            passage_prefix=profile.passage_prefix,
        )

    profiles = EmbeddingProfileRegistry(
        database=database, provider_resolver=resolve, activation_compatible=lambda _: False
    )
    auth = AdminSessionService(
        database=database,
        username="admin",
        password_hash=PasswordHasher().hash(PASSWORD),
        identity_hmac_key=b"n" * 32,
    )
    app = create_app(
        admin_session_service=auth,
        admin_origins=(ORIGIN,),
        admin_operations=AdminOperations(
            github=None,
            database=database,
            public_base_url=ORIGIN,
            model_connections=connections,
            embedding_profiles=profiles,
        ),
    )
    return app, database, connections, profiles, state


def login(client: TestClient) -> dict[str, str]:
    result = client.post(
        "/api/admin/session",
        headers={"Origin": ORIGIN},
        json={"username": "admin", "password": PASSWORD},
    )
    assert result.status_code == 200
    return {"Origin": ORIGIN, "X-CSRF-Token": result.json()["csrf_token"]}


def test_edit_endpoint_requires_owner_origin_csrf_and_returns_only_url(
    tmp_path, monkeypatch, caplog
):
    app, _, connections, _, state = application(tmp_path, monkeypatch)
    saved = connections.create(
        ModelConnectionInput("Fixture", "openai_compatible", URL, KEY, "replace")
    )
    route = f"/api/admin/model-connections/{saved.connection_id}/edit-endpoint"
    with TestClient(app, base_url=ORIGIN) as client:
        assert client.post(route, headers={"Origin": ORIGIN}).status_code == 401
        headers = login(client)
        assert client.post(route, headers={"Origin": ORIGIN}).status_code == 403
        assert (
            client.post(
                route, headers={**headers, "Origin": "https://attacker.example"}
            ).status_code
            == 403
        )
        result = client.post(route, headers=headers)
        assert result.status_code == 200
        assert result.headers["cache-control"] == "no-store"
        assert result.json() == {
            "connection_id": saved.connection_id,
            "revision": saved.revision,
            "base_url": URL,
        }
        assert KEY not in result.text
        for path in (
            "/api/admin/model-connections",
            f"/api/admin/model-connections/{saved.connection_id}",
        ):
            metadata = client.get(path, headers=headers)
            assert URL not in metadata.text and KEY not in metadata.text
        # The application's catch-all GET route returns its safe 404.
        assert client.get(route, headers=headers).status_code == 404
    assert connections.get(saved.connection_id) == saved
    assert state["calls"] == 0
    assert URL not in caplog.text and KEY not in caplog.text


def test_edit_endpoint_denies_host_managed_and_unknown_connections(tmp_path, monkeypatch):
    app, database, connections, _, _ = application(tmp_path, monkeypatch)
    saved = connections.create(
        ModelConnectionInput("Fixture", "openai_compatible", URL, KEY, "replace")
    )
    with database.connection() as db:
        db.execute(
            "UPDATE model_connections SET source = 'host-managed' WHERE connection_id = ?",
            (saved.connection_id,),
        )
        db.commit()
    with TestClient(app, base_url=ORIGIN) as client:
        headers = login(client)
        for identifier in (saved.connection_id, "missing-fixture"):
            result = client.post(
                f"/api/admin/model-connections/{identifier}/edit-endpoint", headers=headers
            )
            assert result.status_code == 404
            assert URL not in result.text and KEY not in result.text


def test_owner_can_replace_and_delete_host_managed_connection(tmp_path, monkeypatch):
    app, _, connections, _, _ = application(tmp_path, monkeypatch)
    saved = connections.ensure_host_managed(
        "environment-chat",
        display_name="Environment chat",
        provider="ollama",
        base_url="http://127.0.0.1:11434",
        api_key=None,
    )
    assert saved is not None
    route = f"/api/admin/model-connections/{saved.connection_id}"
    replacement_url = "http://127.0.0.1:22434"

    with TestClient(app, base_url=ORIGIN) as client:
        headers = login(client)
        retained = client.put(
            route,
            headers=headers,
            json={
                "display_name": "My Ollama",
                "provider": "ollama",
                "endpoint_action": "retain",
                "credential_action": "retain",
            },
        )
        assert retained.status_code == 409
        assert retained.json()["error"]["code"] == "HOST_CONNECTION_REPLACEMENT_REQUIRED"

        replaced = client.put(
            route,
            headers=headers,
            json={
                "display_name": "My Ollama",
                "provider": "ollama",
                "base_url": replacement_url,
                "endpoint_action": "replace",
                "credential_action": "retain",
            },
        )
        assert replaced.status_code == 200
        assert replaced.json()["source"] == "managed"
        assert replacement_url not in replaced.text
        assert connections.secret_for(saved.connection_id).base_url == replacement_url

        endpoint = client.post(f"{route}/edit-endpoint", headers=headers)
        assert endpoint.status_code == 200
        assert endpoint.json()["base_url"] == replacement_url
        assert client.delete(route, headers=headers).status_code == 204

    assert (
        connections.ensure_host_managed(
            "environment-chat",
            display_name="Environment chat",
            provider="ollama",
            base_url="http://127.0.0.1:11434",
            api_key=None,
        )
        is None
    )


def test_edit_endpoint_secret_store_failure_has_no_private_values(tmp_path, monkeypatch):
    app, _, connections, _, _ = application(tmp_path, monkeypatch)
    saved = connections.create(
        ModelConnectionInput("Fixture", "openai_compatible", URL, KEY, "replace")
    )
    (tmp_path / "secrets" / "key").unlink()
    with TestClient(app, base_url=ORIGIN) as client:
        result = client.post(
            f"/api/admin/model-connections/{saved.connection_id}/edit-endpoint",
            headers=login(client),
        )
        assert result.status_code == 503
        assert result.headers["cache-control"] == "no-store"
        assert URL not in result.text and KEY not in result.text
    assert not (tmp_path / "secrets" / "key").exists()


def test_installed_model_lookup_is_explicit_scoped_and_authenticated(tmp_path, monkeypatch):
    app, _, _, _, state = application(tmp_path, monkeypatch)
    looked_up = []

    def list_models(connection_id):
        looked_up.append(connection_id)
        return ("fixture-installed-model",)

    app.state.admin_operations = replace(
        app.state.admin_operations, connection_model_lister=list_models
    )
    with TestClient(app, base_url=ORIGIN) as client:
        route = "/api/admin/embedding-models/installed?connection_id=fixture-selected"
        assert client.get(route).status_code == 401
        assert looked_up == []
        headers = login(client)
        client.get("/api/admin/embedding-profiles", headers=headers)
        assert looked_up == [] and state["calls"] == 0
        response = client.get(route, headers=headers)
        assert response.status_code == 200
        assert response.json()["models"] == ["fixture-installed-model"]
        assert looked_up == ["fixture-selected"]
        assert (
            client.get(
                "/api/admin/embedding-models/installed?connection_id=https://private.invalid",
                headers=headers,
            ).status_code
            == 400
        )
        assert looked_up == ["fixture-selected"]


@pytest.mark.parametrize("fault", ["BEGIN IMMEDIATE", "UPDATE model_connection_secrets", "COMMIT"])
def test_failed_key_rotation_preserves_all_secret_revisions(tmp_path, monkeypatch, fault):
    _, database, connections, _, _ = application(tmp_path, monkeypatch)
    original = connections.create(
        ModelConnectionInput("Fixture", "openai_compatible", URL, KEY, "replace")
    )
    connections.update(
        original.connection_id,
        ModelConnectionInput(
            "Fixture renamed",
            "openai_compatible",
            None,
            "SYNTHETIC_SECOND_KEY",
            "replace",
            "retain",
        ),
    )
    key_path = tmp_path / "secrets" / "key"
    old_key = key_path.read_bytes()
    original_connection = database.connection
    triggered = []

    class FaultConnection:
        def __init__(self, connection):
            self.connection = connection

        def execute(self, sql, parameters=()):
            if sql.startswith(fault):
                triggered.append(fault)
                raise sqlite3.OperationalError("synthetic write failure")
            return self.connection.execute(sql, parameters)

        def __getattr__(self, name):
            return getattr(self.connection, name)

    @contextmanager
    def failing_connection():
        with original_connection() as connection:
            yield FaultConnection(connection)

    monkeypatch.setattr(database, "connection", failing_connection)
    with pytest.raises(ModelConnectionError) as failure:
        connections.rotate_key()
    assert failure.value.code == "MODEL_SECRET_STORAGE_UNAVAILABLE"
    assert triggered == [fault]
    assert key_path.read_bytes() == old_key
    assert connections.secret_for(original.connection_id, 1).api_key == KEY
    assert connections.secret_for(original.connection_id, 2).api_key == "SYNTHETIC_SECOND_KEY"


@pytest.mark.parametrize("adapter", ["ollama", "openai_compatible", "vllm"])
def test_unknown_dimensions_are_sampled_only_on_explicit_probe(tmp_path, monkeypatch, adapter):
    app, _, connections, profiles, state = application(tmp_path, monkeypatch)
    connection = connections.create(ModelConnectionInput("Fixture", adapter, URL, KEY, "replace"))
    with TestClient(app, base_url=ORIGIN) as client:
        headers = login(client)
        created = client.post(
            "/api/admin/embedding-profiles",
            headers=headers,
            json={
                "provider": adapter,
                "model_id": "fixture-model",
                "connection_reference": connection.connection_id,
                "query_prefix": "",
                "passage_prefix": "",
            },
        )
        assert created.status_code == 201
        profile_id = created.json()["profile_id"]
        assert created.json()["dimension"] is None
        assert created.json()["connection_revision"] == connection.revision
        assert created.json()["last_probed_at"] is None
        assert (
            client.get("/api/admin/embedding-profiles", headers=headers).json()["profiles"][0][
                "dimension"
            ]
            is None
        )
        assert state["calls"] == 0
        rejected = client.post(
            f"/api/admin/embedding-profiles/{profile_id}/activate", headers=headers
        )
        assert rejected.status_code == 409
        assert state["calls"] == 0
        tested = client.post(f"/api/admin/embedding-profiles/{profile_id}/probe", headers=headers)
        assert tested.status_code == 200
        assert tested.json()["dimension"] == 3
        assert tested.json()["status"] == "reindex_required"
        assert tested.json()["active"] is False
        assert tested.json()["last_error_code"] is None
        assert state["calls"] == 2
        assert profiles.get(profile_id).identity.dimension == 3
        rendered = created.text + tested.text
        assert KEY not in rendered and URL not in rendered


@pytest.mark.parametrize("failure", ["mismatch", "http"])
def test_failed_discovery_keeps_dimension_unknown_then_retest_recovers(
    tmp_path, monkeypatch, failure
):
    app, _, connections, _, state = application(tmp_path, monkeypatch)
    connection = connections.create(ModelConnectionInput("Fixture", "openai_compatible", URL))
    with TestClient(app, base_url=ORIGIN) as client:
        headers = login(client)
        profile_id = client.post(
            "/api/admin/embedding-profiles",
            headers=headers,
            json={
                "provider": "openai_compatible",
                "model_id": "fixture-model",
                "connection_reference": connection.connection_id,
            },
        ).json()["profile_id"]
        state["mismatch"] = failure == "mismatch"
        state["status"] = 503 if failure == "http" else 200
        failed = client.post(
            f"/api/admin/embedding-profiles/{profile_id}/probe", headers=headers
        ).json()
        assert failed["dimension"] is None
        assert failed["status"] == "probe_failed"
        assert failed["last_error_code"] == (
            "PROVIDER_HTTP_503" if failure == "http" else "PROVIDER_INVALID_RESPONSE"
        )
        state.update(mismatch=False, status=200)
        passed = client.post(
            f"/api/admin/embedding-profiles/{profile_id}/probe", headers=headers
        ).json()
        assert passed["dimension"] == 3 and passed["last_error_code"] is None


def test_connection_update_rebinds_candidate_and_allows_explicit_retest(tmp_path, monkeypatch):
    app, _, connections, _, state = application(tmp_path, monkeypatch)
    model_connection = connections.create(ModelConnectionInput("Fixture", "openai_compatible", URL))
    with TestClient(app, base_url=ORIGIN) as client:
        headers = login(client)
        created = client.post(
            "/api/admin/embedding-profiles",
            headers=headers,
            json={
                "provider": "openai_compatible",
                "model_id": "fixture-model",
                "connection_reference": model_connection.connection_id,
            },
        )
        assert created.status_code == 201
        profile_id = created.json()["profile_id"]
        first_probe = client.post(
            f"/api/admin/embedding-profiles/{profile_id}/probe", headers=headers
        )
        assert first_probe.status_code == 200
        assert first_probe.json()["dimension"] == 3
        assert state["calls"] == 2

        changed = client.put(
            f"/api/admin/model-connections/{model_connection.connection_id}",
            headers=headers,
            json={
                "display_name": "Changed fixture",
                "provider": "openai_compatible",
                "endpoint_action": "replace",
                "base_url": "https://changed-model.example.test/v1",
                "credential_action": "remove",
            },
        )
        assert changed.status_code == 200
        assert changed.json()["revision"] == 2
        rebound = client.get(f"/api/admin/embedding-profiles/{profile_id}", headers=headers).json()
        assert rebound["connection_revision"] == 2
        assert rebound["status"] == "reindex_required"
        assert rebound["last_probed_at"] is None
        assert rebound["last_error_code"] is None
        assert state["calls"] == 2

        retested = client.post(f"/api/admin/embedding-profiles/{profile_id}/probe", headers=headers)
        assert retested.status_code == 200
        assert retested.json()["connection_revision"] == 2
        assert retested.json()["dimension"] == 3
        assert retested.json()["last_error_code"] is None
        assert state["calls"] == 4
        assert URL not in changed.text + rebound.__repr__() + retested.text


def test_private_endpoint_retention_and_label_edit_do_not_invalidate_tests(tmp_path, monkeypatch):
    app, _, connections, _, state = application(tmp_path, monkeypatch)
    saved = connections.create(
        ModelConnectionInput("Before", "openai_compatible", URL, KEY, "replace")
    )
    with TestClient(app, base_url=ORIGIN) as client:
        headers = login(client)
        renamed = client.put(
            f"/api/admin/model-connections/{saved.connection_id}",
            headers=headers,
            json={
                "display_name": "After",
                "provider": "openai_compatible",
                "endpoint_action": "retain",
                "credential_action": "retain",
            },
        )
        assert renamed.status_code == 200
        assert renamed.json()["revision"] == saved.revision
        assert connections.secret_for(saved.connection_id).base_url == URL
        assert connections.secret_for(saved.connection_id).api_key == KEY
        denied = client.put(
            f"/api/admin/model-connections/{saved.connection_id}",
            headers=headers,
            json={
                "display_name": "Other",
                "provider": "openai_compatible",
                "endpoint_action": "replace",
                "base_url": "https://other.example.test",
                "credential_action": "retain",
            },
        )
        assert denied.status_code == 409
        assert connections.secret_for(saved.connection_id).base_url == URL
        assert connections.get(saved.connection_id).revision == saved.revision
        assert state["calls"] == 0
        assert KEY not in renamed.text + denied.text and URL not in renamed.text + denied.text


def old_database(tmp_path):
    database = RuntimeDatabase(tmp_path / "runtime")
    database.initialize(migrations=tuple(m for m in MIGRATIONS if m.version <= 18))
    profiles = EmbeddingProfileRegistry(
        database=database, provider_resolver=lambda _: None, activation_compatible=lambda _: True
    )
    profile = profiles.create(
        EmbeddingProfileInput("ollama", "fixture", 3, True, "", "", "environment")
    )
    with database.connection() as connection:
        connection.execute(
            "UPDATE embedding_profiles SET active = 1, status = 'ready' WHERE profile_id = ?",
            (profile.profile_id,),
        )
        connection.execute(
            "UPDATE analysis_model_selection SET embedding_profile_id = ?, "
            "embedding_connection_revision = 0, selection_generation = 7",
            (profile.profile_id,),
        )
        connection.execute(
            "INSERT INTO embedding_switch_intent VALUES "
            "('current', 2, ?, 'old-bundle', ?, 'new-bundle', 'fixture-time')",
            (profile.profile_id, profile.profile_id),
        )
    return database, profile.profile_id


def test_dimension_migration_preserves_active_selection_and_switch_intent(tmp_path):
    database, profile_id = old_database(tmp_path)
    with database.connection() as connection:
        before = {
            table: [tuple(row) for row in connection.execute(f"SELECT * FROM {table}")]
            for table in (
                "embedding_profiles",
                "analysis_model_selection",
                "embedding_switch_intent",
            )
        }
    database.initialize()
    database.initialize()
    with database.connection() as connection:
        for table, values in before.items():
            rows = [tuple(row) for row in connection.execute(f"SELECT * FROM {table}")]
            if table == "embedding_profiles":
                assert [row[:-1] for row in rows] == values
                assert all(row[-1] is None for row in rows)
            else:
                assert rows == values
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "UPDATE embedding_profiles SET dimension = NULL WHERE profile_id = ?", (profile_id,)
            )


def test_dimension_migration_rolls_back_if_parent_rebuild_fails(tmp_path):
    database, profile_id = old_database(tmp_path)
    migration = next(m for m in MIGRATIONS if m.version == 19)
    broken = replace(
        migration, statements=(*migration.statements[:7], "SELECT * FROM fixture_missing_table")
    )
    with pytest.raises(RuntimeDatabaseError):
        database.initialize(migrations=(*(m for m in MIGRATIONS if m.version <= 18), broken))
    assert database.schema_version() == 18
    with database.connection() as connection:
        assert (
            connection.execute(
                "SELECT embedding_profile_id FROM analysis_model_selection"
            ).fetchone()[0]
            == profile_id
        )
        assert (
            connection.execute("SELECT to_profile_id FROM embedding_switch_intent").fetchone()[0]
            == profile_id
        )
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
