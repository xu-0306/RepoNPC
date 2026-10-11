"""A6/A7 integration evidence uses disposable SQLite and synthetic providers only."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Callable, Iterator
from copy import deepcopy
from dataclasses import asdict, replace
from datetime import UTC, date, datetime
from pathlib import Path
from threading import Event
from time import monotonic, sleep
from types import SimpleNamespace
from typing import Any, cast

import numpy as np
import pytest
from argon2 import PasswordHasher, Type
from fastapi import FastAPI
from fastapi.testclient import TestClient

from reponpc.admin import operations as operation_module
from reponpc.admin.analysis_selection import (
    AnalysisModelPair,
    AnalysisSelectionError,
    AnalysisSelectionRegistry,
)
from reponpc.admin.auth import AdminSessionService
from reponpc.admin.chat_profiles import ChatProfileRegistry
from reponpc.admin.embedding_profiles import (
    EmbeddingProfile,
    EmbeddingProfileError,
    EmbeddingProfileInput,
    EmbeddingProfileRegistry,
)
from reponpc.admin.model_connections import ModelConnectionRegistry
from reponpc.admin.model_guidance import (
    CatalogModel,
    EnvelopeEvidence,
    HardwareProfile,
    ModelCatalog,
    ModelQuantization,
)
from reponpc.admin.model_operations import OllamaModelOperationCoordinator
from reponpc.admin.operations import AdminOperations
from reponpc.indexing.sources import EmbeddingIdentity
from reponpc.main import create_app
from reponpc.providers.builtin_artifacts import builtin_embedding_identity, load_builtin_manifest
from reponpc.providers.builtin_download import BuiltinDownloadCancelled, BuiltinDownloadError
from reponpc.runtime.database import MIGRATIONS, RuntimeDatabase

ORIGIN = "https://portfolio.example.com"
NOW = datetime(2026, 10, 3, tzinfo=UTC)
EXTERNAL = EmbeddingIdentity("ollama", "fixture-external", 3, True, "", "")
TABLES = (
    "embedding_profiles",
    "embedding_switch_intent",
    "analysis_model_selection",
    "chat_profiles",
    "model_connections",
)


class SyntheticEmbedding:
    def __init__(self, identity: EmbeddingIdentity) -> None:
        self._identity = identity
        self.calls = 0

    def identity(self) -> EmbeddingIdentity:
        return self._identity

    def embed_query(self, texts: list[str]) -> np.ndarray:
        self.calls += 1
        output = np.zeros((len(texts), self._identity.dimension), dtype=np.float32)
        output[:, 0] = 1.0
        return output

    def embed_passages(self, texts: list[str]) -> np.ndarray:
        return self.embed_query(texts)


def _registry(
    database: RuntimeDatabase,
) -> tuple[EmbeddingProfileRegistry, dict[str, SyntheticEmbedding]]:
    providers = {
        "ollama": SyntheticEmbedding(EXTERNAL),
        "builtin_onnx": SyntheticEmbedding(builtin_embedding_identity()),
    }

    def provider(profile: EmbeddingProfile) -> SyntheticEmbedding:
        return providers[profile.provider]

    registry = EmbeddingProfileRegistry(
        database=database,
        provider_resolver=provider,
        activation_compatible=lambda _profile: True,
        now=lambda: NOW,
    )
    return registry, providers


def _builtin_input(**changes: Any) -> EmbeddingProfileInput:
    identity = builtin_embedding_identity()
    values: dict[str, Any] = {
        "provider": "builtin_onnx",
        "model_id": identity.model_id,
        "dimension": identity.dimension,
        "normalized": identity.normalized,
        "query_prefix": identity.query_prefix,
        "passage_prefix": identity.passage_prefix,
        "connection_reference": None,
        "connection_revision": 0,
        **changes,
    }
    return EmbeddingProfileInput(**values)


def _seed_chat(database: RuntimeDatabase) -> None:
    with database.connection() as connection:
        connection.execute(
            "INSERT INTO model_connections(connection_id, display_name, provider, source, "
            "revision, secret_ref, endpoint_configured, key_configured, status, "
            "created_at, updated_at) "
            "VALUES ('chat-connection', 'Fixture', 'ollama', 'managed', 2, 'fixture-reference', "
            "1, 0, 'configured', 'fixture-time', 'fixture-time')"
        )
        connection.execute(
            "INSERT INTO chat_profiles(profile_id, connection_id, connection_revision, model_id, "
            "status, active, created_at, updated_at, last_probed_at) "
            "VALUES ('chat-tested', 'chat-connection', 2, 'fixture-chat', 'ready', 0, "
            "'fixture-time', 'fixture-time', 'fixture-time')"
        )


def _rows(database: RuntimeDatabase) -> dict[str, list[tuple[Any, ...]]]:
    with database.connection() as connection:
        return {
            table: [tuple(row) for row in connection.execute(f"SELECT * FROM {table}")]
            for table in TABLES
        }


def test_migration_34_preserves_external_rows_active_switch_selection_and_unknown_metadata(
    tmp_path: Path,
) -> None:
    database = RuntimeDatabase(tmp_path)
    database.initialize(migrations=tuple(m for m in MIGRATIONS if m.version <= 33))
    registry, _providers = _registry(database)
    active = registry.ensure_environment_profile(
        provider="ollama",
        identity=EXTERNAL,
        connection_reference="external-source",
        connection_revision=7,
    )
    registry.probe(active.profile_id)
    registry.activate(active.profile_id)
    target = registry.create(
        EmbeddingProfileInput("ollama", "external-target", 3, True, "", "", "external-source", 7)
    )
    unknown = registry.create(
        EmbeddingProfileInput(
            "openai_compatible", "unknown-dimension", None, True, "", "", "other-source", 3
        )
    )
    _seed_chat(database)
    with database.connection() as connection:
        connection.execute(
            "UPDATE embedding_profiles SET status='probe_failed', "
            "last_error_code='PROVIDER_UNAVAILABLE', "
            "last_error_message='Synthetic bounded upstream diagnostic', "
            "last_probed_at='fixture-time', "
            "observed_adapter='ollama', observed_model_id='external-target', observed_dimension=3 "
            "WHERE profile_id=?",
            (target.profile_id,),
        )
        connection.execute(
            "INSERT INTO embedding_switch_intent VALUES ('current', 5, ?, 'old-bundle', ?, "
            "'candidate-bundle', 'fixture-time')",
            (active.profile_id, target.profile_id),
        )
        connection.execute(
            "UPDATE analysis_model_selection SET chat_profile_id='chat-tested', "
            "chat_connection_revision=2, "
            "embedding_profile_id=?, embedding_connection_revision=7, selection_generation=11, "
            "updated_at='fixture-time'",
            (target.profile_id,),
        )
    before = _rows(database)
    database.initialize(migrations=tuple(m for m in MIGRATIONS if m.version <= 34))
    database.initialize(migrations=tuple(m for m in MIGRATIONS if m.version <= 34))
    assert database.schema_version() == 34
    assert _rows(database) == before
    assert registry.get(unknown.profile_id).dimension is None
    assert registry.get(unknown.profile_id).last_error_message is None
    assert (
        registry.get(target.profile_id).last_error_message
        == "Synthetic bounded upstream diagnostic"
    )
    active_after = registry.active()
    assert active_after is not None and active_after.profile_id == active.profile_id
    with database.connection() as connection:
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
        assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "UPDATE embedding_profiles SET active=1 WHERE profile_id=?", (target.profile_id,)
            )
    builtin = registry.create(_builtin_input())
    with database.connection() as connection:
        for column, value, profile_id in (
            ("connection_reference", "unexpected", builtin.profile_id),
            ("connection_revision", 1, builtin.profile_id),
            ("connection_reference", None, target.profile_id),
        ):
            with pytest.raises(sqlite3.IntegrityError):
                connection.execute(
                    f"UPDATE embedding_profiles SET {column}=? WHERE profile_id=?",
                    (value, profile_id),
                )
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []


class Connections:
    def __init__(self) -> None:
        self.revision = 2
        self.lookups: list[str] = []

    def get(self, connection_id: str) -> SimpleNamespace:
        assert connection_id == "chat-connection", "builtin must never look up a null connection"
        self.lookups.append(connection_id)
        return SimpleNamespace(
            connection_id=connection_id, revision=self.revision, provider="ollama"
        )


def _selection(
    tmp_path: Path,
) -> tuple[AnalysisSelectionRegistry, EmbeddingProfileRegistry, Connections, EmbeddingProfile]:
    database = RuntimeDatabase(tmp_path)
    database.initialize()
    _seed_chat(database)
    registry, _providers = _registry(database)
    builtin = registry.create(_builtin_input())
    probed = registry.probe(builtin.profile_id)
    assert probed.status == "ready" and probed.active is False
    connections = Connections()
    chats = ChatProfileRegistry(
        database, cast(ModelConnectionRegistry, connections), lambda _: None
    )
    selected = AnalysisSelectionRegistry(database, chats, registry, connections, now=lambda: NOW)
    return selected, registry, connections, probed


def test_builtin_registry_selection_frozen_pair_roundtrip_and_cache_identity(
    tmp_path: Path,
) -> None:
    selected, registry, connections, builtin = _selection(tmp_path)
    before = selected.current()
    assert before.configured is False
    view = selected.select(
        chat_profile_id="chat-tested",
        embedding_profile_id=builtin.profile_id,
        expected_generation=before.generation,
    )
    assert view.eligible and view.reason == "READY"
    assert view.selection.embedding_connection_revision == 0
    pair = selected.frozen_pair()
    assert pair is not None
    assert pair.embedding_connection_id is None and pair.embedding_connection_revision == 0
    assert pair.embedding_identity == builtin_embedding_identity()
    rendered = json.loads(json.dumps(pair.safe_dict()))
    assert AnalysisModelPair.from_safe_dict(rendered) == pair
    assert pair.cache_embedding_identity() == "\x1f".join(
        (
            "",
            "0",
            "builtin_onnx",
            "builtin_onnx",
            pair.embedding_identity.model_id,
            "1024",
            "True",
            "",
            "",
        )
    )
    external_pair = replace(
        pair,
        embedding_provider="ollama",
        embedding_connection_id="external",
        embedding_connection_revision=7,
        embedding_identity=EXTERNAL,
    )
    assert external_pair.cache_embedding_identity() != pair.cache_embedding_identity()
    assert connections.lookups and set(connections.lookups) == {"chat-connection"}
    assert registry.get(builtin.profile_id).active is False
    connections.revision = 3
    assert selected.view().reason == "CHAT_MODEL_REVISION_STALE"
    assert selected.frozen_pair() is None
    assert (
        AnalysisModelPair.from_safe_dict(rendered) == pair
    )  # Historical frozen identity stays unchanged.


@pytest.mark.parametrize("field,value", [("connection_id", "external"), ("connection_revision", 1)])
def test_frozen_builtin_pair_rejects_external_connection_metadata(
    tmp_path: Path, field: str, value: object
) -> None:
    selected, _profiles, _connections, builtin = _selection(tmp_path)
    selected.select(chat_profile_id="chat-tested", embedding_profile_id=builtin.profile_id)
    pair = selected.frozen_pair()
    assert pair is not None
    corrupted = cast(dict[str, Any], deepcopy(pair.safe_dict()))
    corrupted["embedding"][field] = value
    with pytest.raises(AnalysisSelectionError) as caught:
        AnalysisModelPair.from_safe_dict(corrupted)
    assert caught.value.code == "ANALYSIS_MODEL_PAIR_INVALID"


def test_historical_builtin_selection_revision_mismatch_fails_closed(tmp_path: Path) -> None:
    selected, _profiles, connections, builtin = _selection(tmp_path)
    selected.select(chat_profile_id="chat-tested", embedding_profile_id=builtin.profile_id)
    pair = selected.frozen_pair()
    assert pair is not None
    with RuntimeDatabase(tmp_path).connection() as connection:
        connection.execute("UPDATE analysis_model_selection SET embedding_connection_revision=1")
    assert selected.view().reason == "SEARCH_MODEL_REVISION_STALE"
    assert selected.frozen_pair() is None
    assert set(connections.lookups) == {"chat-connection"}
    assert AnalysisModelPair.from_safe_dict(pair.safe_dict()) == pair


@pytest.mark.parametrize(
    "changes",
    [
        {"connection_reference": "external"},
        {"connection_revision": 1},
        {"model_id": "unverified-revision"},
        {"dimension": None},
    ],
)
def test_builtin_profile_input_is_the_pinned_null_connection_identity(
    changes: dict[str, Any],
) -> None:
    with pytest.raises(EmbeddingProfileError) as caught:
        _builtin_input(**changes).validate()
    assert caught.value.code == "VALIDATION_ERROR"


class DownloadFixture:
    def __init__(self) -> None:
        self.calls = 0
        self.started = Event()
        self.release = Event()
        self.mode = "block"

    def __call__(
        self, *, cancelled: Callable[[], bool], on_progress: Callable[[int, int], None]
    ) -> None:
        self.calls += 1
        on_progress(3, 10)
        self.started.set()
        if self.mode == "fail":
            raise BuiltinDownloadError("builtin_download_checksum")
        if self.mode == "success":
            on_progress(10, 10)
            return
        while not self.release.wait(timeout=0.01):
            if cancelled():
                raise BuiltinDownloadCancelled
        if cancelled():
            raise BuiltinDownloadCancelled


@pytest.fixture
def application(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[SimpleNamespace]:
    database = RuntimeDatabase(tmp_path)
    database.initialize()
    registry, providers = _registry(database)
    active = registry.ensure_environment_profile(provider="ollama", identity=EXTERNAL)
    registry.probe(active.profile_id)
    registry.activate(active.profile_id)
    downloader = DownloadFixture()
    coordinator = OllamaModelOperationCoordinator(registry, builtin_download=downloader)
    hardware = HardwareProfile(
        host_ram_bytes=16 * 1024**3, free_memory_bytes=8 * 1024**3, free_disk_bytes=10 * 1024**3
    )
    device_calls: list[Path] = []

    def collect(path: Path) -> HardwareProfile:
        device_calls.append(path)
        return hardware

    monkeypatch.setattr(operation_module, "collect_hardware_profile", collect)
    operations = AdminOperations(
        github=None,
        database=database,
        public_base_url=ORIGIN,
        embedding_profiles=registry,
        ollama_model_operations=coordinator,
    )
    auth = AdminSessionService(
        database=database,
        username="admin",
        password_hash=PasswordHasher(type=Type.ID).hash("npcx"),
        identity_hmac_key=b"b" * 32,
        now=lambda: NOW,
    )
    app = create_app(
        admin_session_service=auth, admin_origins=(ORIGIN,), admin_operations=operations
    )
    try:
        yield SimpleNamespace(
            app=app,
            database=database,
            registry=registry,
            providers=providers,
            coordinator=coordinator,
            download=downloader,
            hardware=hardware,
            device_calls=device_calls,
            active=active.profile_id,
        )
    finally:
        downloader.release.set()
        coordinator.shutdown()


def _login(client: TestClient) -> dict[str, str]:
    response = client.post(
        "/api/admin/session",
        headers={"Origin": ORIGIN},
        json={"username": "admin", "password": "npcx"},
    )
    assert response.status_code == 200
    return {"Origin": ORIGIN, "X-CSRF-Token": response.json()["csrf_token"]}


def _terminal(client: TestClient, operation_id: str) -> dict[str, Any]:
    deadline = monotonic() + 2
    while monotonic() < deadline:
        response = client.get(
            f"/api/admin/embedding-model-operations/{operation_id}", headers={"Origin": ORIGIN}
        )
        assert response.status_code == 200 and response.headers["Cache-Control"] == "no-store"
        result = response.json()
        if result["status"] in {"failed", "cancelled", "succeeded"}:
            return cast(dict[str, Any], result)
        sleep(0.01)
    raise AssertionError("synthetic model operation did not terminate")


def test_builtin_metadata_read_is_authenticated_no_store_and_side_effect_free(
    application: SimpleNamespace,
) -> None:
    with TestClient(cast(FastAPI, application.app), base_url=ORIGIN) as client:
        denied = client.get("/api/admin/embedding-models/builtin", headers={"Origin": ORIGIN})
        assert denied.status_code == 401
        _login(client)
        before = _rows(application.database)
        probes = sum(provider.calls for provider in application.providers.values())
        response = client.get("/api/admin/embedding-models/builtin", headers={"Origin": ORIGIN})
        assert response.status_code == 200 and response.headers["Cache-Control"] == "no-store"
        manifest = load_builtin_manifest()
        assert response.json() == {
            "model_id": builtin_embedding_identity().model_id,
            "display_name": manifest.model_id,
            "total_bytes": manifest.total_bytes,
            "license": manifest.license,
            "source_url": manifest.source_url,
            "profile_id": None,
            "operation": None,
        }
        assert _rows(application.database) == before
        assert sum(provider.calls for provider in application.providers.values()) == probes
        assert application.download.calls == 0 and application.device_calls == []
        wrong_origin = client.get(
            "/api/admin/embedding-models/builtin",
            headers={"Origin": "https://other.example.invalid"},
        )
        assert wrong_origin.status_code == 403


def test_builtin_download_progress_conflict_authenticated_cancel_and_no_auto_activation(
    application: SimpleNamespace,
) -> None:
    with TestClient(cast(FastAPI, application.app), base_url=ORIGIN) as client:
        headers = _login(client)
        started = client.post(
            "/api/admin/embedding-models/builtin/download",
            headers=headers,
            json={"confirmed": True},
        )
        assert started.status_code == 202 and started.headers["Cache-Control"] == "no-store"
        operation_id = started.json()["operation_id"]
        assert application.download.started.wait(timeout=1)
        running = client.get(
            f"/api/admin/embedding-model-operations/{operation_id}", headers={"Origin": ORIGIN}
        )
        assert running.json()["completed"] == 3 and running.json()["total"] == 10
        conflict = client.post(
            "/api/admin/embedding-models/builtin/download",
            headers=headers,
            json={"confirmed": True},
        )
        assert conflict.status_code == 409
        assert conflict.json()["error"]["code"] == "EMBEDDING_MODEL_OPERATION_ACTIVE"
        unauthorized_cancel = client.delete(
            f"/api/admin/embedding-model-operations/{operation_id}", headers={"Origin": ORIGIN}
        )
        assert unauthorized_cancel.status_code == 403
        client.delete(f"/api/admin/embedding-model-operations/{operation_id}", headers=headers)
        assert _terminal(client, operation_id)["status"] == "cancelled"
        application.download.mode = "success"
        retried = client.post(
            "/api/admin/embedding-models/builtin/download",
            headers=headers,
            json={"confirmed": True},
        )
        assert retried.status_code == 202
        assert _terminal(client, retried.json()["operation_id"])["status"] == "succeeded"
        info = client.get("/api/admin/embedding-models/builtin", headers={"Origin": ORIGIN}).json()
        assert info["operation"]["status"] == "succeeded"
        builtin = application.registry.get(info["profile_id"])
        assert (
            builtin.status == "probe" and builtin.active is False and builtin.last_probed_at is None
        )
        assert application.registry.active().profile_id == application.active
        assert application.download.calls == 2
        assert application.providers["builtin_onnx"].calls == 0
        with application.database.connection() as connection:
            assert (
                connection.execute(
                    "SELECT embedding_profile_id FROM analysis_model_selection"
                ).fetchone()[0]
                is None
            )
    with TestClient(cast(FastAPI, application.app), base_url=ORIGIN) as anonymous:
        assert (
            anonymous.get(
                f"/api/admin/embedding-model-operations/{operation_id}", headers={"Origin": ORIGIN}
            ).status_code
            == 401
        )
        assert (
            anonymous.delete(
                f"/api/admin/embedding-model-operations/{operation_id}", headers={"Origin": ORIGIN}
            ).status_code
            == 401
        )


def test_failed_builtin_download_requires_explicit_retry_and_retains_last_known_good(
    application: SimpleNamespace,
) -> None:
    application.download.mode = "fail"
    with TestClient(cast(FastAPI, application.app), base_url=ORIGIN) as client:
        headers = _login(client)
        started = client.post(
            "/api/admin/embedding-models/builtin/download",
            headers=headers,
            json={"confirmed": True},
        )
        terminal = _terminal(client, started.json()["operation_id"])
        assert terminal["status"] == "failed"
        assert terminal["error_code"] == "BUILTIN_DOWNLOAD_CHECKSUM"
        for _ in range(2):
            client.get("/api/admin/embedding-models/builtin", headers={"Origin": ORIGIN})
        assert application.download.calls == 1
        assert application.registry.active().profile_id == application.active
        application.download.mode = "success"
        retried = client.post(
            "/api/admin/embedding-models/builtin/download",
            headers=headers,
            json={"confirmed": True},
        )
        assert _terminal(client, retried.json()["operation_id"])["status"] == "succeeded"
        assert application.download.calls == 2
        assert application.registry.active().profile_id == application.active


@pytest.mark.parametrize(
    "route,body",
    [
        ("/api/admin/embedding-models/builtin/download", {"confirmed": False}),
        ("/api/admin/embedding-models/builtin/download", {"confirmed": 1}),
        ("/api/admin/embedding-models/builtin/download", {"confirmed": "true"}),
        (
            "/api/admin/embedding-models/builtin/download",
            {"confirmed": True, "url": "https://example.invalid/model"},
        ),
        ("/api/admin/model-guidance/device-check", {"data_directory": "private-input"}),
    ],
)
def test_setup_rejects_unapproved_or_owner_controlled_download_device_inputs(
    application: SimpleNamespace, route: str, body: dict[str, object]
) -> None:
    with TestClient(cast(FastAPI, application.app), base_url=ORIGIN) as client:
        headers = _login(client)
        response = client.post(route, headers=headers, json=body)
        assert response.status_code == 400
        assert application.download.calls == 0 and application.device_calls == []


@pytest.mark.parametrize(
    "route,body",
    [
        ("/api/admin/embedding-models/builtin/download", {"confirmed": True}),
        ("/api/admin/model-guidance/device-check", {}),
    ],
)
def test_setup_mutations_require_session_csrf_and_origin(
    application: SimpleNamespace, route: str, body: dict[str, object]
) -> None:
    with TestClient(cast(FastAPI, application.app), base_url=ORIGIN) as client:
        assert client.post(route, headers={"Origin": ORIGIN}, json=body).status_code == 401
        headers = _login(client)
        assert client.post(route, headers={"Origin": ORIGIN}, json=body).status_code == 403
        assert (
            client.post(
                route, headers={**headers, "X-CSRF-Token": "incorrect"}, json=body
            ).status_code
            == 403
        )
        assert (
            client.post(
                route, headers={**headers, "Origin": "https://other.example.invalid"}, json=body
            ).status_code
            == 403
        )
        assert application.download.calls == 0 and application.device_calls == []


def test_device_check_returns_only_observations_and_read_only_catalog(
    application: SimpleNamespace,
) -> None:
    with TestClient(cast(FastAPI, application.app), base_url=ORIGIN) as client:
        headers = _login(client)
        before = _rows(application.database)
        response = client.post("/api/admin/model-guidance/device-check", headers=headers, json={})
        assert response.status_code == 200 and response.headers["Cache-Control"] == "no-store"
        assert response.json() == {"hardware": asdict(application.hardware), "models": []}
        assert _rows(application.database) == before
        assert application.device_calls == [application.database.database_path.parent]
        assert application.download.calls == 0
        assert all(
            value is None or type(value) is int for value in response.json()["hardware"].values()
        )
        assert str(application.database.database_path.parent) not in response.text


def test_device_check_exposes_authored_model_card_facts_without_provider_work(
    application: SimpleNamespace, monkeypatch: pytest.MonkeyPatch
) -> None:
    # A synthetic catalog exercises the DTO; it is not live-provider evidence.
    evidence = EnvelopeEvidence(
        "live_provider",
        2,
        "ollama",
        "fixture-revision",
        date(2026, 10, 3),
        "release-evidence/fixture/report.json",
        ("zh-TW", "en"),
        4,
        4,
    )
    quantization = ModelQuantization("fixture-q4", 4, 2_100_000_000, 1_000_000_000, evidence)
    model = CatalogModel(
        "fixture-chat:4b",
        4_000_000_000,
        date(2026, 10, 3),
        "https://example.org/fixture-model",
        "MIT",
        "https://example.org/fixture-license",
        (quantization,),
    )
    monkeypatch.setattr(operation_module, "load_model_catalog", lambda: ModelCatalog((model,)))
    with TestClient(cast(FastAPI, application.app), base_url=ORIGIN) as client:
        headers = _login(client)
        before = _rows(application.database)
        response = client.post("/api/admin/model-guidance/device-check", headers=headers, json={})
        assert response.status_code == 200
        row = response.json()["models"][0]
        assert set(row) == {
            "model_id",
            "quantization_id",
            "parameter_count",
            "bits_per_weight",
            "download_bytes",
            "memory_overhead_bytes",
            "last_reviewed",
            "source_url",
            "license_id",
            "license_url",
            "envelope_evidence",
            "suitability",
        }
        assert row["model_id"] == model.model_id
        assert row["download_bytes"] == quantization.download_bytes
        assert row["envelope_evidence"]["tested_on"] == "2026-10-03"
        assert row["envelope_evidence"]["tested_locales"] == ["zh-TW", "en"]
        assert row["suitability"]["estimated_memory_bytes"] == 3_000_000_000
        assert row["suitability"]["execution_target"] == "cpu"
        assert row["suitability"]["speed_estimate_tokens_per_second"] is None
        assert response.headers["Cache-Control"] == "no-store"
        assert _rows(application.database) == before
        assert application.download.calls == 0
        assert str(application.database.database_path.parent) not in response.text
