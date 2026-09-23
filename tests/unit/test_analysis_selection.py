from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import pytest

from reponpc.admin.analysis_selection import (
    AnalysisModelPair,
    AnalysisSelectionError,
    AnalysisSelectionRegistry,
)
from reponpc.indexing.sources import EmbeddingIdentity
from reponpc.runtime.database import RuntimeDatabase


@dataclass
class Profile:
    profile_id: str
    connection_revision: int
    model_id: str
    connection_id: str = "chat-connection"
    connection_reference: str = "embedding-connection"
    provider: str = "ollama"
    status: str = "ready"
    last_probed_at: str | None = "2026-09-10T00:00:00Z"
    last_error_code: str | None = None

    @property
    def identity(self) -> EmbeddingIdentity:
        return EmbeddingIdentity(
            adapter="ollama",
            model_id=self.model_id,
            dimension=2,
            normalized=True,
            query_prefix="query: ",
            passage_prefix="passage: ",
        )


class Profiles:
    def __init__(self, *profiles: Profile) -> None:
        self._profiles = {profile.profile_id: profile for profile in profiles}

    def get(self, profile_id: str) -> Profile:
        return self._profiles[profile_id]


@dataclass
class Connection:
    connection_id: str
    revision: int
    provider: str = "ollama"


class Connections:
    def __init__(self, *connections: Connection) -> None:
        self._connections = {connection.connection_id: connection for connection in connections}

    def get(self, connection_id: str) -> Connection:
        return self._connections[connection_id]


def _persist_references(database: RuntimeDatabase) -> None:
    with database.connection() as connection:
        connection.execute(
            """
            INSERT INTO model_connections(
              connection_id, display_name, provider, source, revision, secret_ref,
              endpoint_configured, key_configured, status, created_at, updated_at
            ) VALUES ('connection', 'Connection', 'ollama', 'managed', 7, 'secret', 1, 0,
                      'configured', 'now', 'now')
            """
        )
        connection.execute(
            """
            INSERT INTO chat_profiles(
              profile_id, connection_id, connection_revision, model_id, status, active,
              created_at, updated_at, last_probed_at
            ) VALUES ('chat-a', 'connection', 3, 'chat-model', 'ready', 0, 'now', 'now', 'now')
            """
        )
        connection.execute(
            """
            INSERT INTO embedding_profiles(
              profile_id, provider, model_id, dimension, normalized, query_prefix,
              passage_prefix, connection_reference, connection_revision, status, active,
              created_at, updated_at, last_probed_at
            ) VALUES ('embed-a', 'ollama', 'embed-model', 2, 1, 'query: ', 'passage: ',
                      'connection', 7, 'reindex_required', 0, 'now', 'now', 'now')
            """
        )


def test_analysis_selection_requires_two_tested_profiles_and_detects_stale_revisions(
    tmp_path: Path,
) -> None:
    database = RuntimeDatabase(tmp_path / "runtime")
    database.initialize()
    _persist_references(database)
    chat = Profiles(Profile("chat-a", 3, "chat-model"))
    embedding = Profiles(Profile("embed-a", 7, "embed-model", status="reindex_required"))
    connections = Connections(
        Connection("chat-connection", 3),
        Connection("embedding-connection", 7),
    )
    registry = AnalysisSelectionRegistry(database, chat, embedding, connections)

    assert registry.view().safe_dict()["reason"] == "CHAT_MODEL_NOT_SELECTED"
    selected = registry.select(chat_profile_id="chat-a", embedding_profile_id="embed-a")
    assert selected.eligible is True
    assert selected.selection.generation == 1
    assert selected.safe_dict()["selection"] == {
        "chat_profile_id": "chat-a",
        "chat_connection_revision": 3,
        "embedding_profile_id": "embed-a",
        "embedding_connection_revision": 7,
        "generation": 1,
        "updated_at": selected.selection.updated_at,
    }
    pair = registry.frozen_pair()
    assert pair is not None
    assert pair.chat_model_id == "chat-model"
    assert pair.embedding_identity.model_id == "embed-model"

    chat.get("chat-a").connection_revision = 4
    assert registry.view().reason == "CHAT_MODEL_REVISION_STALE"
    with pytest.raises(AnalysisSelectionError, match="analysis model selection failed") as raised:
        registry.select(
            chat_profile_id="chat-a",
            embedding_profile_id="embed-a",
            expected_generation=0,
        )
    assert raised.value.code == "ANALYSIS_SELECTION_STALE"


def test_analysis_model_pair_round_trips_legal_empty_embedding_prefixes() -> None:
    pair = AnalysisModelPair(
        selection_generation=1,
        chat_profile_id="chat-a",
        chat_connection_id="chat-connection",
        chat_connection_revision=3,
        chat_provider="ollama",
        chat_model_id="chat-model",
        embedding_profile_id="embed-a",
        embedding_connection_id="embedding-connection",
        embedding_connection_revision=7,
        embedding_provider="ollama",
        embedding_identity=EmbeddingIdentity(
            adapter="ollama",
            model_id="embed-model",
            dimension=2,
            normalized=True,
            query_prefix="",
            passage_prefix="",
        ),
    )

    assert AnalysisModelPair.from_safe_dict(pair.safe_dict()) == pair


def test_analysis_model_pair_safe_shape_matches_frontend_contract_fixture() -> None:
    fixture_path = (
        Path(__file__).resolve().parents[2]
        / "apps"
        / "web"
        / "src"
        / "features"
        / "admin"
        / "__fixtures__"
        / "analysisModelPair.safe.json"
    )
    expected = json.loads(fixture_path.read_text(encoding="utf-8"))
    pair = AnalysisModelPair(
        selection_generation=7,
        chat_profile_id="chat-safe",
        chat_connection_id="chat-connection-safe",
        chat_connection_revision=3,
        chat_provider="ollama",
        chat_model_id="chat-model-safe",
        embedding_profile_id="embedding-safe",
        embedding_connection_id="embedding-connection-safe",
        embedding_connection_revision=5,
        embedding_provider="ollama",
        embedding_identity=EmbeddingIdentity(
            adapter="ollama",
            model_id="embedding-model-safe",
            dimension=2,
            normalized=True,
            query_prefix="query: ",
            passage_prefix="passage: ",
        ),
    )

    assert pair.safe_dict() == expected


def test_analysis_selection_never_selects_an_unprobed_role(tmp_path: Path) -> None:
    database = RuntimeDatabase(tmp_path / "runtime")
    database.initialize()
    _persist_references(database)
    chat = Profiles(Profile("chat-a", 1, "chat-model", status="probe", last_probed_at=None))
    embedding = Profiles(Profile("embed-a", 1, "embed-model"))
    registry = AnalysisSelectionRegistry(database, chat, embedding)

    with pytest.raises(AnalysisSelectionError) as raised:
        registry.select(chat_profile_id="chat-a", embedding_profile_id="embed-a")
    assert raised.value.code == "CHAT_PROBE_REQUIRED"
    assert registry.view().safe_dict()["selection"]["chat_profile_id"] is None
