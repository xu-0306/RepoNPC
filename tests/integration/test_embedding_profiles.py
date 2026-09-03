from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from threading import Event
from time import monotonic, sleep

import numpy as np
import pytest
from argon2 import PasswordHasher, Type
from fastapi.testclient import TestClient

from reponpc.admin.auth import AdminSessionService
from reponpc.admin.embedding_profiles import (
    EmbeddingProfile,
    EmbeddingProfileError,
    EmbeddingProfileInput,
    EmbeddingProfileRegistry,
)
from reponpc.admin.model_operations import OllamaModelOperationCoordinator
from reponpc.admin.operations import AdminOperations
from reponpc.indexing.sources import EmbeddingIdentity
from reponpc.main import create_app
from reponpc.runtime.database import RuntimeDatabase

ORIGIN = "https://portfolio.example.com"
PASSWORD = "npcx"
IDENTITY = EmbeddingIdentity(
    adapter="ollama",
    model_id="qwen3-embedding:0.6b",
    dimension=3,
    normalized=True,
    query_prefix="query: ",
    passage_prefix="passage: ",
)


class ProbeProvider:
    def identity(self) -> EmbeddingIdentity:
        return IDENTITY

    def embed_query(self, texts: list[str]) -> np.ndarray:
        assert texts == ["RepoNPC embedding readiness probe"]
        return np.asarray([[0.0, 0.6, 0.8]], dtype=np.float32)

    def installed_models(self) -> tuple[str, ...]:
        return ("qwen3-embedding:0.6b", "other-private-model:latest")

    def pull_model(self) -> None:
        return None

    def delete_model(self) -> None:
        return None


def _application(
    tmp_path: Path,
    *,
    provider_instance: ProbeProvider | None = None,
    model_operations: bool = False,
):
    database = RuntimeDatabase(tmp_path)
    database.initialize()
    auth = AdminSessionService(
        database=database,
        username="admin",
        password_hash=PasswordHasher(type=Type.ID).hash(PASSWORD),
        identity_hmac_key=b"e" * 32,
        now=lambda: datetime(2026, 8, 31, tzinfo=UTC),
    )

    def provider(profile: EmbeddingProfile):
        if profile.connection_reference == "environment":
            return provider_instance or ProbeProvider()
        return None

    registry = EmbeddingProfileRegistry(
        database=database,
        provider_resolver=provider,
        activation_compatible=lambda profile: profile.identity == IDENTITY,
        now=lambda: datetime(2026, 8, 31, tzinfo=UTC),
    )
    environment = registry.ensure_environment_profile(provider="ollama", identity=IDENTITY)
    registry.probe(environment.profile_id)
    registry.activate(environment.profile_id)
    coordinator = OllamaModelOperationCoordinator(registry) if model_operations else None
    operations = AdminOperations(
        github=None,
        database=database,
        public_base_url=ORIGIN,
        embedding_profiles=registry,
        ollama_model_operations=coordinator,
    )
    return create_app(
        admin_session_service=auth,
        admin_origins=(ORIGIN,),
        admin_operations=operations,
    )


class CancellableProbeProvider(ProbeProvider):
    def __init__(self) -> None:
        self.started = Event()

    def pull_model(self, **values: object) -> None:
        cancelled = values["cancelled"]
        on_progress = values["on_progress"]
        assert callable(cancelled) and callable(on_progress)
        on_progress(2, 10)
        self.started.set()
        while not cancelled():
            sleep(0.01)
        from reponpc.providers.ollama_embeddings import OllamaPullCancelled

        raise OllamaPullCancelled


def _login(client: TestClient) -> str:
    response = client.post(
        "/api/admin/session",
        headers={"Origin": ORIGIN},
        json={"username": "admin", "password": PASSWORD},
    )
    assert response.status_code == 200
    return str(response.json()["csrf_token"])


def _profile_body(**overrides: object) -> dict[str, object]:
    body: dict[str, object] = {
        "provider": "ollama",
        "model_id": IDENTITY.model_id,
        "dimension": IDENTITY.dimension,
        "normalized": True,
        "query_prefix": "query: ",
        "passage_prefix": "passage: ",
        "connection_reference": "environment",
    }
    body.update(overrides)
    return body


def test_embedding_profile_crud_probe_and_one_active_are_safe(tmp_path: Path) -> None:
    app = _application(tmp_path)
    with TestClient(app, base_url=ORIGIN) as client:
        csrf = _login(client)
        listed = client.get("/api/admin/embedding-profiles", headers={"Origin": ORIGIN})
        denied = client.post(
            "/api/admin/embedding-profiles",
            headers={"Origin": ORIGIN},
            json=_profile_body(),
        )
        created = client.post(
            "/api/admin/embedding-profiles",
            headers={"Origin": ORIGIN, "X-CSRF-Token": csrf},
            json=_profile_body(),
        )
        profile_id = created.json()["profile_id"]
        probed = client.post(
            f"/api/admin/embedding-profiles/{profile_id}/probe",
            headers={"Origin": ORIGIN, "X-CSRF-Token": csrf},
        )
        activated = client.post(
            f"/api/admin/embedding-profiles/{profile_id}/activate",
            headers={"Origin": ORIGIN, "X-CSRF-Token": csrf},
        )
        after = client.get("/api/admin/embedding-profiles", headers={"Origin": ORIGIN})
        deleted = client.delete(
            "/api/admin/embedding-profiles/environment",
            headers={"Origin": ORIGIN, "X-CSRF-Token": csrf},
        )

    assert listed.status_code == 200
    assert listed.json()["profiles"][0]["active"] is True
    assert denied.status_code == 403
    assert created.status_code == 201
    assert probed.json()["status"] == "ready"
    assert probed.json()["observed_identity"] == {
        "adapter": "ollama",
        "model_id": IDENTITY.model_id,
        "dimension": IDENTITY.dimension,
    }
    assert activated.status_code == 200 and activated.json()["active"] is True
    assert sum(profile["active"] for profile in after.json()["profiles"]) == 1
    assert deleted.status_code == 204
    rendered = listed.text + created.text + probed.text + after.text
    assert "http://" not in rendered
    assert "api_key" not in rendered
    assert "token" not in rendered


def test_probe_failure_is_actionable_and_preserves_active_profile(tmp_path: Path) -> None:
    app = _application(tmp_path)
    with TestClient(app, base_url=ORIGIN) as client:
        csrf = _login(client)
        created = client.post(
            "/api/admin/embedding-profiles",
            headers={"Origin": ORIGIN, "X-CSRF-Token": csrf},
            json=_profile_body(
                provider="vllm",
                model_id="unconfigured-model",
                connection_reference="unconfigured",
            ),
        )
        profile_id = created.json()["profile_id"]
        probed = client.post(
            f"/api/admin/embedding-profiles/{profile_id}/probe",
            headers={"Origin": ORIGIN, "X-CSRF-Token": csrf},
        )
        activation = client.post(
            f"/api/admin/embedding-profiles/{profile_id}/activate",
            headers={"Origin": ORIGIN, "X-CSRF-Token": csrf},
        )
        listed = client.get("/api/admin/embedding-profiles", headers={"Origin": ORIGIN})

    assert probed.status_code == 200
    assert probed.json()["status"] == "probe_failed"
    assert probed.json()["last_error_code"] == "EMBEDDING_CONNECTION_REQUIRED"
    assert activation.status_code == 409
    active = [profile for profile in listed.json()["profiles"] if profile["active"]]
    assert [profile["profile_id"] for profile in active] == ["environment"]


def test_embedding_model_catalog_is_authenticated_bounded_and_non_secret(
    tmp_path: Path,
) -> None:
    app = _application(tmp_path)
    with TestClient(app, base_url=ORIGIN) as client:
        denied = client.get("/api/admin/embedding-models/catalog", headers={"Origin": ORIGIN})
        _login(client)
        response = client.get("/api/admin/embedding-models/catalog", headers={"Origin": ORIGIN})
        installed = client.get("/api/admin/embedding-models/installed", headers={"Origin": ORIGIN})

    assert denied.status_code == 401
    assert response.status_code == 200
    assert {model["model_id"] for model in response.json()["models"]} == {
        "qwen3-embedding:0.6b",
        "bge-m3",
        "embeddinggemma:300m",
    }
    assert all(model["provider"] == "ollama" for model in response.json()["models"])
    assert "http://" not in response.text
    assert "api_key" not in response.text
    assert "token" not in response.text
    assert installed.status_code == 200
    assert installed.json() == {
        "provider": "ollama",
        "models": ["other-private-model:latest", "qwen3-embedding:0.6b"],
    }
    assert "http://" not in installed.text


def test_ollama_model_actions_use_the_frozen_routes_and_explicit_profile(
    tmp_path: Path,
) -> None:
    app = _application(tmp_path)
    with TestClient(app, base_url=ORIGIN) as client:
        csrf = _login(client)
        created = client.post(
            "/api/admin/embedding-profiles",
            headers={"Origin": ORIGIN, "X-CSRF-Token": csrf},
            json=_profile_body(model_id="bge-m3"),
        )
        profile_id = created.json()["profile_id"]
        pulled = client.post(
            "/api/admin/embedding-models/ollama/pull",
            headers={"Origin": ORIGIN, "X-CSRF-Token": csrf},
            json={"profile_id": profile_id, "confirmed": True},
        )
        mismatched_delete = client.request(
            "DELETE",
            "/api/admin/embedding-models/ollama/embeddinggemma:300m",
            headers={"Origin": ORIGIN, "X-CSRF-Token": csrf},
            json={"profile_id": profile_id, "confirmed": True},
        )
        deleted = client.request(
            "DELETE",
            "/api/admin/embedding-models/ollama/bge-m3",
            headers={"Origin": ORIGIN, "X-CSRF-Token": csrf},
            json={"profile_id": profile_id, "confirmed": True},
        )
        legacy = client.post(
            f"/api/admin/embedding-profiles/{profile_id}/ollama/pull",
            headers={"Origin": ORIGIN, "X-CSRF-Token": csrf},
            json={"confirmed": True},
        )

    assert pulled.status_code == 200
    assert pulled.json()["status"] == "probe"
    assert mismatched_delete.status_code == 400
    assert mismatched_delete.json()["error"]["code"] == "VALIDATION_ERROR"
    assert deleted.status_code == 200
    assert legacy.status_code in {404, 405}


def test_ollama_pull_progress_and_cancel_are_safe_and_authenticated(tmp_path: Path) -> None:
    provider = CancellableProbeProvider()
    app = _application(tmp_path, provider_instance=provider, model_operations=True)
    with TestClient(app, base_url=ORIGIN) as client:
        csrf = _login(client)
        created = client.post(
            "/api/admin/embedding-profiles",
            headers={"Origin": ORIGIN, "X-CSRF-Token": csrf},
            json=_profile_body(model_id="bge-m3"),
        )
        started = client.post(
            "/api/admin/embedding-models/ollama/pull",
            headers={"Origin": ORIGIN, "X-CSRF-Token": csrf},
            json={"profile_id": created.json()["profile_id"], "confirmed": True},
        )
        assert started.status_code == 202
        operation_id = started.json()["operation_id"]
        assert provider.started.wait(timeout=1)
        running = client.get(
            f"/api/admin/embedding-model-operations/{operation_id}",
            headers={"Origin": ORIGIN},
        )
        cancelled = client.delete(
            f"/api/admin/embedding-model-operations/{operation_id}",
            headers={"Origin": ORIGIN, "X-CSRF-Token": csrf},
        )
        deadline = monotonic() + 1
        terminal = cancelled
        while terminal.json()["status"] != "cancelled" and monotonic() < deadline:
            sleep(0.01)
            terminal = client.get(
                f"/api/admin/embedding-model-operations/{operation_id}",
                headers={"Origin": ORIGIN},
            )

    assert running.json()["status"] == "running"
    assert running.json()["completed"] == 2
    assert running.json()["total"] == 10
    assert terminal.json()["status"] == "cancelled"
    assert "http://" not in terminal.text


def test_environment_profile_requires_probe_before_it_can_be_active(tmp_path: Path) -> None:
    database = RuntimeDatabase(tmp_path)
    database.initialize()
    registry = EmbeddingProfileRegistry(
        database=database,
        provider_resolver=lambda _profile: ProbeProvider(),
        activation_compatible=lambda _profile: True,
        now=lambda: datetime(2026, 8, 31, tzinfo=UTC),
    )

    profile = registry.ensure_environment_profile(provider="ollama", identity=IDENTITY)

    assert profile.status == "probe"
    assert profile.active is False
    assert registry.active_matches(IDENTITY) is False


def test_probe_requires_a_compatible_verified_bundle_before_ready(tmp_path: Path) -> None:
    database = RuntimeDatabase(tmp_path)
    database.initialize()
    registry = EmbeddingProfileRegistry(
        database=database,
        provider_resolver=lambda _profile: ProbeProvider(),
        activation_compatible=lambda _profile: False,
    )
    profile = registry.ensure_environment_profile(provider="ollama", identity=IDENTITY)

    probed = registry.probe(profile.profile_id)

    assert probed.status == "reindex_required"
    assert probed.active is False
    with pytest.raises(EmbeddingProfileError) as exc_info:
        registry.activate(profile.profile_id)
    assert exc_info.value.code == "EMBEDDING_REINDEX_REQUIRED"


def test_changed_environment_identity_preserves_active_last_known_good(
    tmp_path: Path,
) -> None:
    database = RuntimeDatabase(tmp_path)
    database.initialize()
    registry = EmbeddingProfileRegistry(
        database=database,
        provider_resolver=lambda _profile: ProbeProvider(),
        activation_compatible=lambda _profile: True,
        now=lambda: datetime(2026, 8, 31, tzinfo=UTC),
    )
    original = registry.ensure_environment_profile(provider="ollama", identity=IDENTITY)
    registry.probe(original.profile_id)
    registry.activate(original.profile_id)
    changed_identity = EmbeddingIdentity(
        adapter="ollama",
        model_id="embeddinggemma:300m",
        dimension=IDENTITY.dimension,
        normalized=True,
        query_prefix="query: ",
        passage_prefix="passage: ",
    )

    candidate = registry.ensure_environment_profile(provider="ollama", identity=changed_identity)

    active = [profile for profile in registry.list() if profile.active]
    assert [profile.profile_id for profile in active] == [original.profile_id]
    assert active[0].identity == IDENTITY
    assert candidate.profile_id != original.profile_id
    assert candidate.active is False
    assert candidate.status == "probe"


def test_ollama_model_actions_reject_non_curated_model_ids(tmp_path: Path) -> None:
    database = RuntimeDatabase(tmp_path)
    database.initialize()
    registry = EmbeddingProfileRegistry(
        database=database,
        provider_resolver=lambda _profile: ProbeProvider(),
        activation_compatible=lambda _profile: True,
    )
    profile = registry.create(
        EmbeddingProfileInput(
            provider="ollama",
            model_id="owner/arbitrary-model:latest",
            dimension=3,
            normalized=True,
            query_prefix="query: ",
            passage_prefix="passage: ",
            connection_reference="environment",
        )
    )

    with pytest.raises(EmbeddingProfileError) as exc_info:
        registry.ollama_model_action(profile.profile_id, action="pull", confirmed=True)

    assert exc_info.value.code == "VALIDATION_ERROR"


@pytest.mark.parametrize(
    ("vector", "error_code"),
    [
        (np.asarray([[0.0, 0.6, 0.8]], dtype=np.float64), "EMBEDDING_PROBE_INVALID_VECTOR"),
        (np.asarray([[0.0, 0.3, 0.4]], dtype=np.float32), "EMBEDDING_PROBE_NOT_NORMALIZED"),
    ],
)
def test_probe_rejects_wrong_dtype_and_non_normalized_vectors(
    tmp_path: Path,
    vector: np.ndarray,
    error_code: str,
) -> None:
    class BadProbeProvider(ProbeProvider):
        def embed_query(self, texts: list[str]) -> np.ndarray:
            assert texts == ["RepoNPC embedding readiness probe"]
            return vector

    database = RuntimeDatabase(tmp_path)
    database.initialize()
    registry = EmbeddingProfileRegistry(
        database=database,
        provider_resolver=lambda _profile: BadProbeProvider(),
        activation_compatible=lambda _profile: False,
    )
    profile = registry.ensure_environment_profile(provider="ollama", identity=IDENTITY)

    probed = registry.probe(profile.profile_id)

    assert probed.status == "probe_failed"
    assert probed.last_error_code == error_code
    assert probed.active is False


def test_profile_rejects_non_normalized_bundle_contract(tmp_path: Path) -> None:
    database = RuntimeDatabase(tmp_path)
    database.initialize()
    registry = EmbeddingProfileRegistry(
        database=database,
        provider_resolver=lambda _profile: ProbeProvider(),
        activation_compatible=lambda _profile: False,
    )

    with pytest.raises(EmbeddingProfileError) as exc_info:
        registry.create(
            EmbeddingProfileInput(
                provider="ollama",
                model_id="fixture",
                dimension=3,
                normalized=False,
                query_prefix="query: ",
                passage_prefix="passage: ",
                connection_reference="environment",
            )
        )

    assert exc_info.value.code == "VALIDATION_ERROR"
