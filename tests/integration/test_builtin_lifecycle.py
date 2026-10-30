"""Production assembly/lifespan evidence with disposable data and synthetic inference.

These tests do not establish real-model quality, performance, or hardware suitability.
"""

from __future__ import annotations

import socket
import urllib.request
from collections.abc import Callable, Iterator
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from dataclasses import dataclass, replace
from pathlib import Path
from time import monotonic, sleep
from typing import Any, NoReturn, cast

import numpy as np
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from numpy.typing import NDArray

import reponpc.main as main
from reponpc.admin.analysis_selection import AnalysisModelPair, AnalysisSelectionError
from reponpc.admin.chat_profiles import ChatProfileInput, ChatProfileRegistry
from reponpc.admin.embedding_profiles import (
    EmbeddingProfile,
    EmbeddingProfileError,
    EmbeddingProfileInput,
    EmbeddingProfileRegistry,
)
from reponpc.admin.model_connections import ModelConnectionInput, ModelConnectionRegistry
from reponpc.admin.model_operations import OllamaModelOperationCoordinator
from reponpc.bundles.manager import BundleActivationError, BundleManager
from reponpc.config.environment import EnvironmentSettings, load_environment
from reponpc.indexing.sources import EmbeddingIdentity
from reponpc.providers import (
    ProviderCapabilities,
    ProviderError,
    ProviderFailureCode,
    ProviderHealth,
    ProviderMessage,
    ProviderResult,
)
from reponpc.providers.builtin_artifacts import builtin_embedding_identity, load_builtin_manifest
from reponpc.providers.runtime import ProviderRuntime
from reponpc.runtime.database import RuntimeDatabase
from tests.integration.test_embedding_reindex import RuntimeFixtureEmbedding, _candidate


def forbidden(*_args: object, **_kwargs: object) -> NoReturn:
    raise AssertionError("network or external embedding fallback is forbidden in this fixture")


class SyntheticChat:
    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(False, True, True, True, True, 32768, 16384)

    def health(self) -> ProviderHealth:
        return ProviderHealth(True, "2026-10-03T00:00:00Z")

    def generate(
        self,
        messages: tuple[ProviderMessage, ...],
        response_schema: dict[str, Any],
        max_output_tokens: int,
        timeout: float,
    ) -> ProviderResult:
        return ProviderResult({"ok": True}, "stop", None, None, 0.0)


class LazyBuiltin:
    """A tiny synthetic session; construction/identity never read or create files."""

    def __init__(self, directory: Path, events: list[str]) -> None:
        self.directory = directory
        self.events = events
        self.loaded = False
        self.closed = False
        self.loads = 0
        self.close_calls = 0
        self.query_calls = 0

    def identity(self) -> EmbeddingIdentity:
        return builtin_embedding_identity()

    def _load(self) -> None:
        if self.closed or not (self.directory / "synthetic-install.txt").is_file():
            raise ProviderError(ProviderFailureCode.UNAVAILABLE)
        if not self.loaded:
            self.loads += 1
            self.loaded = True

    def embed_query(self, texts: list[str]) -> NDArray[np.float32]:
        self._load()
        self.query_calls += 1
        output = np.zeros((len(texts), self.identity().dimension), dtype=np.float32)
        output[:, 0] = 1.0
        return output

    def embed_passages(self, texts: list[str]) -> NDArray[np.float32]:
        return self.embed_query(texts)

    def health(self) -> ProviderHealth:
        try:
            self._load()
        except ProviderError:
            return ProviderHealth(False, "2026-10-03T00:00:00Z", ProviderFailureCode.UNAVAILABLE)
        return ProviderHealth(True, "2026-10-03T00:00:00Z")

    def close(self) -> None:
        self.events.append("builtin-close")
        self.close_calls += 1
        self.closed = True
        self.loaded = False


@dataclass
class Boot:
    application: FastAPI
    database: RuntimeDatabase
    settings: EnvironmentSettings
    instances: list[LazyBuiltin]
    downloads: list[Path]
    events: list[str]

    @property
    def profiles(self) -> EmbeddingProfileRegistry:
        return cast(EmbeddingProfileRegistry, self.application.state.embedding_profile_registry)

    @property
    def coordinator(self) -> OllamaModelOperationCoordinator:
        return cast(OllamaModelOperationCoordinator, self.application.state.ollama_model_operations)


@pytest.fixture
def boot(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Boot]:
    settings = load_environment(
        {
            "REPONPC_DATA_DIR": str(tmp_path / "host"),
            "REPONPC_PUBLIC_BASE_URL": "https://portfolio.example.com",
            "REPONPC_IP_HASH_KEY": "synthetic-lifecycle-fixture-key",
        },
        secret_roots=(tmp_path,),
    )
    database = RuntimeDatabase(settings.data_dir)
    database.initialize()
    application = main.create_app(runtime_database=database, provider_health_seconds=3600)
    instances: list[LazyBuiltin] = []
    downloads: list[Path] = []
    events: list[str] = []

    def constructor(directory: Path) -> LazyBuiltin:
        instance = LazyBuiltin(directory, events)
        instances.append(instance)
        return instance

    def download(
        directory: Path,
        *,
        transport: object,
        cancelled: Callable[[], bool],
        on_progress: Callable[[int, int], None],
    ) -> None:
        assert not cancelled()
        downloads.append(directory)
        directory.mkdir()
        (directory / "synthetic-install.txt").write_text("fixture only", encoding="utf-8")
        total = load_builtin_manifest().total_bytes
        on_progress(total, total)

    monkeypatch.setattr(main, "app", application)
    monkeypatch.setattr(main, "BuiltinOnnxEmbeddingProvider", constructor)
    monkeypatch.setattr(main, "download_builtin_model", download)
    monkeypatch.setattr(main, "PinnedBuiltinHttpTransport", object)
    monkeypatch.setattr(main, "_chat_provider_from_connection", lambda *_a, **_k: SyntheticChat())
    monkeypatch.setattr(main, "_embedding_provider_from_connection", forbidden)
    monkeypatch.setattr(urllib.request, "urlopen", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    main._configure_admin(settings, database)
    fixture = Boot(application, database, settings, instances, downloads, events)
    try:
        yield fixture
    finally:
        fixture.coordinator.shutdown()
        for instance in instances:
            if not instance.closed:
                instance.close()


def installed(boot: Boot) -> EmbeddingProfile:
    queued = boot.coordinator.queue_builtin(confirmed=True)
    deadline = monotonic() + 5
    while monotonic() < deadline:
        current = boot.coordinator.get(queued.operation_id)
        if current.status in {"succeeded", "failed", "cancelled"}:
            assert current.status == "succeeded", current
            return boot.profiles.get(current.profile_id)
        sleep(0.01)
    raise AssertionError("synthetic download did not complete")


def selected_pair(boot: Boot, profile: EmbeddingProfile | None = None) -> AnalysisModelPair:
    profile = profile or installed(boot)
    operations = boot.application.state.admin_operations
    connections = cast(ModelConnectionRegistry, operations.model_connections)
    connection = connections.create(
        ModelConnectionInput("Synthetic chat", "ollama", "http://127.0.0.1:11434")
    )
    chats = cast(ChatProfileRegistry, boot.application.state.chat_profile_registry)
    chat = chats.create(ChatProfileInput(connection.connection_id, "synthetic-chat"))
    assert chats.probe(chat.profile_id).status == "ready"
    probed = boot.profiles.probe(profile.profile_id)
    assert probed.last_error_code is None
    selection = boot.application.state.analysis_selection_registry
    assert selection.select(
        chat_profile_id=chat.profile_id, embedding_profile_id=profile.profile_id
    ).eligible
    pair = selection.frozen_pair()
    assert isinstance(pair, AnalysisModelPair)
    return pair


def test_fresh_production_boot_has_no_builtin_profile_adapter_session_or_model_directory(
    boot: Boot,
) -> None:
    with TestClient(boot.application):
        assert boot.profiles.list() == ()
        assert boot.application.state.builtin_embedding_provider is None
        assert boot.instances == []
        assert boot.downloads == []
        assert not (boot.settings.data_dir / "models").exists()
        assert boot.application.state.analysis_runtime_supplier() is None
        assert boot.application.state.contribution_runtime_supplier() is None
        assert boot.application.state.admin_operations.model_connections.list() == ()


def test_only_confirmed_coordinator_download_creates_a_connectionless_unselected_profile(
    boot: Boot,
) -> None:
    with pytest.raises(EmbeddingProfileError) as unconfirmed:
        boot.coordinator.queue_builtin(confirmed=False)
    assert unconfirmed.value.code == "VALIDATION_ERROR"
    assert boot.profiles.list() == ()
    assert boot.downloads == []
    assert not (boot.settings.data_dir / "models").exists()

    profile = installed(boot)
    identity = builtin_embedding_identity()
    assert profile.identity == identity
    assert profile.connection_reference is None and profile.connection_revision == 0
    assert profile.last_probed_at is None and not profile.active
    assert boot.profiles.active() is None
    assert not boot.application.state.analysis_selection_registry.current().configured
    assert boot.instances == []
    assert boot.downloads == [
        boot.settings.data_dir / "models" / ("bge-m3-" + load_builtin_manifest().revision)
    ]
    assert boot.application.state.admin_operations.model_connections.list() == ()
    latest = boot.coordinator.latest_builtin()
    assert latest is not None and latest.status == "succeeded"
    assert latest.completed == latest.total == load_builtin_manifest().total_bytes


def test_all_production_resolvers_share_one_lazy_builtin_until_explicit_probe(
    boot: Boot, monkeypatch: pytest.MonkeyPatch
) -> None:
    profile = installed(boot)
    with ThreadPoolExecutor(max_workers=4) as executor:
        providers = list(
            executor.map(lambda _n: boot.profiles.resolve_provider(profile), range(12))
        )
    assert len(boot.instances) == 1
    instance = boot.instances[0]
    assert all(provider is instance for provider in providers)
    assert instance.loads == 0 and not instance.loaded
    assert boot.application.state.analysis_runtime_supplier() is None

    # Selection is explicit and requires probes; re-use the existing installed row.
    pair = selected_pair(boot, profile)
    assert pair.embedding_identity == builtin_embedding_identity()
    assert pair.embedding_connection_id is None and pair.embedding_connection_revision == 0
    assert instance.loads == 1
    connections = boot.application.state.admin_operations.model_connections
    revision_for = connections.revision_for
    lookups: list[tuple[str, int]] = []

    def guarded_revision(connection_id: str, revision: int) -> Any:
        assert connection_id == pair.chat_connection_id
        lookups.append((connection_id, revision))
        return revision_for(connection_id, revision)

    monkeypatch.setattr(connections, "revision_for", guarded_revision)
    for factory in (
        boot.application.state.analysis_runtime_supplier,
        boot.application.state.contribution_runtime_supplier,
        lambda: boot.application.state.analysis_frozen_runtime_resolver(pair),
    ):
        for _ in range(3):
            runtime = factory()
            assert isinstance(runtime, ProviderRuntime)
            assert runtime.embedding is instance
    assert lookups and all(item[0] == pair.chat_connection_id for item in lookups)
    assert len(boot.instances) == 1 and instance.loads == 1


def test_builtin_resolver_requires_a_persisted_matching_row_even_after_adapter_is_cached(
    boot: Boot,
) -> None:
    pair = selected_pair(boot)
    profile = boot.profiles.get(pair.embedding_profile_id)
    assert boot.profiles.resolve_provider(profile) is boot.instances[0]
    boot.profiles.delete(profile.profile_id)
    assert boot.profiles.resolve_provider(profile) is None
    assert boot.application.state.analysis_frozen_runtime_resolver(pair) is None
    assert len(boot.instances) == 1


@pytest.mark.parametrize(
    "changes",
    [
        {"model_id": "wrong-revision"},
        {"dimension": 3},
        {"normalized": False},
        {"query_prefix": "unexpected: "},
        {"passage_prefix": "unexpected: "},
        {"connection_reference": "fake-http-connection"},
        {"connection_revision": 1},
    ],
)
def test_profile_resolver_rejects_builtin_pin_or_connection_mismatch_without_http_fallback(
    boot: Boot, changes: dict[str, Any]
) -> None:
    profile = installed(boot)
    if changes.get("normalized") is False:
        # The shared immutable identity contract rejects non-normalized vectors
        # before a builtin adapter or any HTTP connection can be resolved.
        with pytest.raises(ValueError, match="must be normalized"):
            boot.profiles.resolve_provider(replace(profile, **changes))
    else:
        assert boot.profiles.resolve_provider(replace(profile, **changes)) is None
    assert boot.instances == []


@pytest.mark.parametrize(
    "changes",
    [
        {"embedding_connection_id": "fake-http-connection"},
        {"embedding_connection_revision": 1},
        {"embedding_identity": replace(builtin_embedding_identity(), model_id="wrong-revision")},
        {"embedding_identity": replace(builtin_embedding_identity(), adapter="ollama")},
    ],
)
def test_frozen_builtin_pair_rejects_mismatch_before_any_secret_lookup(
    boot: Boot, monkeypatch: pytest.MonkeyPatch, changes: dict[str, Any]
) -> None:
    pair = selected_pair(boot)
    connections = boot.application.state.admin_operations.model_connections
    monkeypatch.setattr(connections, "revision_for", forbidden)
    monkeypatch.setattr(connections, "secret_for", forbidden)
    with pytest.raises(ValueError, match="invalid built-in model identity"):
        replace(pair, **changes)
    safe = deepcopy(pair.safe_dict())
    embedding = cast(dict[str, object], safe["embedding"])
    if "embedding_identity" in changes:
        identity = cast(dict[str, object], embedding["identity"])
        identity["model_id"] = "wrong-revision"
    elif "embedding_connection_id" in changes:
        embedding["connection_id"] = changes["embedding_connection_id"]
    else:
        embedding["connection_revision"] = changes["embedding_connection_revision"]
    with pytest.raises(AnalysisSelectionError) as malformed:
        AnalysisModelPair.from_safe_dict(safe)
    assert malformed.value.code == "ANALYSIS_MODEL_PAIR_INVALID"


def test_real_app_shutdown_waits_for_coordinators_then_closes_builtin_once_without_reload(
    boot: Boot, monkeypatch: pytest.MonkeyPatch
) -> None:
    pair = selected_pair(boot)
    instance = boot.instances[0]
    model_shutdown = boot.coordinator.shutdown

    def shutdown_models() -> None:
        boot.events.append("model-operations-shutdown")
        model_shutdown()

    class Reindex:
        def shutdown(self) -> None:
            boot.events.append("reindex-shutdown")

    boot.application.state.embedding_reindex_coordinator = Reindex()
    monkeypatch.setattr(boot.coordinator, "shutdown", shutdown_models)
    with TestClient(boot.application):
        assert not instance.closed
        assert instance.loaded
    assert boot.events == ["reindex-shutdown", "model-operations-shutdown", "builtin-close"]
    assert instance.close_calls == 1 and not instance.loaded
    loads = instance.loads
    runtime = boot.application.state.analysis_frozen_runtime_resolver(pair)
    assert runtime is not None and runtime.embedding is instance
    with pytest.raises(ProviderError) as closed:
        runtime.embed_query_once(["synthetic query after shutdown"], timeout=1)
    assert closed.value.code == ProviderFailureCode.UNAVAILABLE
    assert instance.loads == loads and len(boot.instances) == 1


def test_external_builtin_switch_retains_leased_identities_and_lkg_on_failed_commit(
    boot: Boot, tmp_path: Path
) -> None:
    builtin_profile = installed(boot)
    builtin = boot.profiles.resolve_provider(builtin_profile)
    assert isinstance(builtin, LazyBuiltin)
    external = RuntimeFixtureEmbedding("synthetic-external", 8)
    external_identity = external.identity()
    external_profile = boot.profiles.create(
        EmbeddingProfileInput(
            "ollama",
            external_identity.model_id,
            external_identity.dimension,
            True,
            external_identity.query_prefix,
            external_identity.passage_prefix,
            "fixture-external",
        )
    )
    runtime = ProviderRuntime(chat=SyntheticChat(), embedding=external, max_attempts=1)
    manager = BundleManager(
        data_directory=boot.settings.data_dir,
        runtime_database=boot.database,
        expected_embedding=external_identity,
    )
    candidate_a = _candidate(tmp_path, external_profile, external, 1)
    manager.activate(candidate_a.verified)
    candidate_b = _candidate(tmp_path, builtin_profile, cast(RuntimeFixtureEmbedding, builtin), 2)

    def switch_to_builtin() -> Callable[[], None]:
        previous = runtime.replace_embedding(builtin)

        def rollback() -> None:
            runtime.replace_embedding(previous)

        return rollback

    with manager.acquire_snapshot() as (old_index, old_bundle, _public):
        manager.activate(
            candidate_b.verified,
            expected_embedding=builtin.identity(),
            state_transition=switch_to_builtin,
        )
        assert manager.status().previous_bundle_id == old_bundle
        assert runtime.embedding is builtin
        assert runtime.embed_query_for(old_index.embedding, ["old lease"], timeout=1).shape == (
            1,
            8,
        )
        assert old_index.lexical_candidates("retrieval", limit=1)
        with manager.acquire_snapshot() as (builtin_index, builtin_bundle, _public):
            assert runtime.embed_query_for(
                builtin_index.embedding, ["new lease"], timeout=1
            ).shape == (1, builtin.identity().dimension)
            candidate_c = _candidate(tmp_path, external_profile, external, 3)

            def switch_to_external() -> Callable[[], None]:
                previous = runtime.replace_embedding(external)

                def rollback() -> None:
                    runtime.replace_embedding(previous)

                return rollback

            def fail_commit() -> NoReturn:
                raise RuntimeError("synthetic commit fault")

            with pytest.raises(BundleActivationError) as failed:
                manager.activate(
                    candidate_c.verified,
                    expected_embedding=external_identity,
                    state_transition=switch_to_external,
                    before_commit=fail_commit,
                )
            assert failed.value.code == "bundle_pointer_swap_failed"
            assert runtime.embedding is builtin
            assert manager.status().active_bundle_id == builtin_bundle
            assert manager.status().previous_bundle_id == old_bundle
            assert manager.active_embedding_identity() == builtin.identity()
            assert (
                runtime.embed_query_for(builtin_index.embedding, ["LKG query"], timeout=1).shape[1]
                == builtin.identity().dimension
            )
            assert builtin.close_calls == 0 and len(boot.instances) == 1
            candidate_d = _candidate(tmp_path, external_profile, external, 4)
            manager.activate(
                candidate_d.verified,
                expected_embedding=external_identity,
                state_transition=switch_to_external,
            )
            assert runtime.embedding is external
            assert manager.status().previous_bundle_id == builtin_bundle
            # A builtin lease from before the reverse switch retains its adapter.
            assert (
                runtime.embed_query_for(
                    builtin_index.embedding, ["retained builtin"], timeout=1
                ).shape[1]
                == builtin.identity().dimension
            )
            with manager.acquire_snapshot() as (external_index, _bundle, _public):
                assert runtime.embed_query_for(
                    external_index.embedding, ["external again"], timeout=1
                ).shape == (1, 8)
            assert builtin.close_calls == 0 and len(boot.instances) == 1
