"""Owner-selected, tested model pair used only by authenticated analysis."""

from __future__ import annotations

import sqlite3
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol

from reponpc.indexing.sources import EmbeddingIdentity
from reponpc.runtime.database import RuntimeDatabase, RuntimeDatabaseError


class _ChatProfile(Protocol):
    profile_id: str
    connection_id: str
    connection_revision: int
    model_id: str
    status: str
    last_probed_at: str | None
    last_error_code: str | None


class _EmbeddingProfile(Protocol):
    profile_id: str
    connection_reference: str
    connection_revision: int
    model_id: str
    status: str
    last_probed_at: str | None
    last_error_code: str | None
    identity: object


class AnalysisSelectionError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__("analysis model selection failed")


@dataclass(frozen=True, slots=True)
class AnalysisSelection:
    chat_profile_id: str | None
    chat_connection_revision: int | None
    embedding_profile_id: str | None
    embedding_connection_revision: int | None
    generation: int
    updated_at: str

    @property
    def configured(self) -> bool:
        return self.chat_profile_id is not None and self.embedding_profile_id is not None


@dataclass(frozen=True, slots=True)
class AnalysisSelectionView:
    selection: AnalysisSelection
    eligible: bool
    reason: str
    chat: dict[str, object]
    embedding: dict[str, object]

    def safe_dict(self) -> dict[str, object]:
        return {
            "selection": {
                "chat_profile_id": self.selection.chat_profile_id,
                "chat_connection_revision": self.selection.chat_connection_revision,
                "embedding_profile_id": self.selection.embedding_profile_id,
                "embedding_connection_revision": self.selection.embedding_connection_revision,
                "generation": self.selection.generation,
                "updated_at": self.selection.updated_at,
            },
            "eligible": self.eligible,
            "reason": self.reason,
            "chat": self.chat,
            "embedding": self.embedding,
        }


@dataclass(frozen=True, slots=True)
class AnalysisModelPair:
    """One durable, secret-free analysis provider pair."""

    selection_generation: int
    chat_profile_id: str
    chat_connection_id: str
    chat_connection_revision: int
    chat_provider: str
    chat_model_id: str
    embedding_profile_id: str
    embedding_connection_id: str
    embedding_connection_revision: int
    embedding_provider: str
    embedding_identity: EmbeddingIdentity

    def safe_dict(self) -> dict[str, object]:
        return {
            "selection_generation": self.selection_generation,
            "chat": {
                "profile_id": self.chat_profile_id,
                "connection_id": self.chat_connection_id,
                "connection_revision": self.chat_connection_revision,
                "provider": self.chat_provider,
                "model_id": self.chat_model_id,
            },
            "embedding": {
                "profile_id": self.embedding_profile_id,
                "connection_id": self.embedding_connection_id,
                "connection_revision": self.embedding_connection_revision,
                "provider": self.embedding_provider,
                "identity": {
                    "adapter": self.embedding_identity.adapter,
                    "model_id": self.embedding_identity.model_id,
                    "dimension": self.embedding_identity.dimension,
                    "normalized": self.embedding_identity.normalized,
                    "query_prefix": self.embedding_identity.query_prefix,
                    "passage_prefix": self.embedding_identity.passage_prefix,
                },
            },
        }

    def cache_embedding_identity(self) -> str:
        identity = self.embedding_identity
        return "\x1f".join(
            (
                self.embedding_connection_id,
                str(self.embedding_connection_revision),
                self.embedding_provider,
                identity.adapter,
                identity.model_id,
                str(identity.dimension),
                str(identity.normalized),
                identity.query_prefix,
                identity.passage_prefix,
            )
        )

    def cache_chat_identity(self) -> str:
        return "\x1f".join(
            (
                self.chat_connection_id,
                str(self.chat_connection_revision),
                self.chat_provider,
                self.chat_model_id,
            )
        )

    @classmethod
    def from_safe_dict(cls, value: dict[str, object]) -> AnalysisModelPair:
        try:
            chat = value["chat"]
            embedding = value["embedding"]
            if not isinstance(chat, dict) or not isinstance(embedding, dict):
                raise ValueError
            identity = embedding["identity"]
            if not isinstance(identity, dict):
                raise ValueError
            return cls(
                selection_generation=_required_int(value["selection_generation"]),
                chat_profile_id=_required_text(chat["profile_id"]),
                chat_connection_id=_required_text(chat["connection_id"]),
                chat_connection_revision=_required_int(chat["connection_revision"]),
                chat_provider=_required_text(chat["provider"]),
                chat_model_id=_required_text(chat["model_id"]),
                embedding_profile_id=_required_text(embedding["profile_id"]),
                embedding_connection_id=_required_text(embedding["connection_id"]),
                embedding_connection_revision=_required_int(embedding["connection_revision"]),
                embedding_provider=_required_text(embedding["provider"]),
                embedding_identity=EmbeddingIdentity(
                    adapter=_required_text(identity["adapter"]),
                    model_id=_required_text(identity["model_id"]),
                    dimension=_required_int(identity["dimension"]),
                    normalized=identity["normalized"] is True,
                    query_prefix=_bounded_text(identity["query_prefix"]),
                    passage_prefix=_bounded_text(identity["passage_prefix"]),
                ),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise AnalysisSelectionError("ANALYSIS_MODEL_PAIR_INVALID") from exc


class AnalysisSelectionRegistry:
    """Persist one explicit pair without changing public active profiles."""

    def __init__(
        self,
        database: RuntimeDatabase,
        chat_profiles: object,
        embedding_profiles: object,
        connections: object | None = None,
        *,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self._database = database
        self._chat_profiles = chat_profiles
        self._embedding_profiles = embedding_profiles
        self._connections = connections
        self._now = now or (lambda: datetime.now(UTC))

    def current(self) -> AnalysisSelection:
        with self._database.connection() as connection:
            row = connection.execute(
                "SELECT * FROM analysis_model_selection WHERE selection_key = 'current'"
            ).fetchone()
        if row is None:
            raise RuntimeDatabaseError("runtime_analysis_selection_failed")
        return AnalysisSelection(
            chat_profile_id=_optional(row["chat_profile_id"]),
            chat_connection_revision=_optional_int(row["chat_connection_revision"]),
            embedding_profile_id=_optional(row["embedding_profile_id"]),
            embedding_connection_revision=_optional_int(row["embedding_connection_revision"]),
            generation=int(row["selection_generation"]),
            updated_at=str(row["updated_at"]),
        )

    def view(self) -> AnalysisSelectionView:
        selection = self.current()
        chat = self._role_view(selection.chat_profile_id, "chat")
        embedding = self._role_view(selection.embedding_profile_id, "embedding")
        if selection.chat_profile_id is None:
            return AnalysisSelectionView(
                selection, False, "CHAT_MODEL_NOT_SELECTED", chat, embedding
            )
        if selection.embedding_profile_id is None:
            return AnalysisSelectionView(
                selection, False, "SEARCH_MODEL_NOT_SELECTED", chat, embedding
            )
        if chat["status"] != "ready" or chat.get("tested") is not True:
            return AnalysisSelectionView(selection, False, "CHAT_MODEL_NOT_READY", chat, embedding)
        if (
            embedding["status"] not in {"ready", "reindex_required", "last_known_good"}
            or embedding.get("tested") is not True
        ):
            return AnalysisSelectionView(
                selection, False, "SEARCH_MODEL_NOT_READY", chat, embedding
            )
        if chat["connection_revision"] != selection.chat_connection_revision:
            return AnalysisSelectionView(
                selection, False, "CHAT_MODEL_REVISION_STALE", chat, embedding
            )
        if embedding["connection_revision"] != selection.embedding_connection_revision:
            return AnalysisSelectionView(
                selection, False, "SEARCH_MODEL_REVISION_STALE", chat, embedding
            )
        if self._connections is not None:
            try:
                chat_profile = self._get(self._chat_profiles, selection.chat_profile_id, "chat")
                if (
                    self._connections.get(chat_profile.connection_id).revision  # type: ignore[attr-defined]
                    != chat_profile.connection_revision
                ):
                    return AnalysisSelectionView(
                        selection, False, "CHAT_MODEL_REVISION_STALE", chat, embedding
                    )
                embedding_profile = self._get(
                    self._embedding_profiles, selection.embedding_profile_id, "embedding"
                )
                embedding_connection = self._connections.get(  # type: ignore[attr-defined]
                    embedding_profile.connection_reference
                )
                if (
                    embedding_connection.revision != embedding_profile.connection_revision
                    or embedding_connection.provider != embedding_profile.provider
                ):
                    return AnalysisSelectionView(
                        selection, False, "SEARCH_MODEL_REVISION_STALE", chat, embedding
                    )
            except Exception:
                return AnalysisSelectionView(
                    selection, False, "MODEL_CONNECTION_UNAVAILABLE", chat, embedding
                )
        return AnalysisSelectionView(selection, True, "READY", chat, embedding)

    def select(
        self,
        *,
        chat_profile_id: str,
        embedding_profile_id: str,
        expected_generation: int | None = None,
    ) -> AnalysisSelectionView:
        chat = self._get(self._chat_profiles, chat_profile_id, "chat")
        embedding = self._get(self._embedding_profiles, embedding_profile_id, "embedding")
        if chat.status != "ready" or chat.last_probed_at is None or chat.last_error_code:
            raise AnalysisSelectionError("CHAT_PROBE_REQUIRED")
        if (
            embedding.status not in {"ready", "reindex_required", "last_known_good"}
            or embedding.last_probed_at is None
            or embedding.last_error_code
        ):
            raise AnalysisSelectionError("EMBEDDING_PROBE_REQUIRED")
        now = _time(self._now())
        try:
            with self._database.connection() as connection:
                connection.execute("BEGIN IMMEDIATE")
                row = connection.execute(
                    "SELECT selection_generation FROM analysis_model_selection "
                    "WHERE selection_key = 'current'"
                ).fetchone()
                if row is None:
                    raise RuntimeDatabaseError("runtime_analysis_selection_failed")
                generation = int(row["selection_generation"])
                if expected_generation is not None and expected_generation != generation:
                    raise AnalysisSelectionError("ANALYSIS_SELECTION_STALE")
                connection.execute(
                    """
                    UPDATE analysis_model_selection SET
                      chat_profile_id = ?, chat_connection_revision = ?,
                      embedding_profile_id = ?, embedding_connection_revision = ?,
                      selection_generation = selection_generation + 1, updated_at = ?
                    WHERE selection_key = 'current'
                    """,
                    (
                        chat.profile_id,
                        chat.connection_revision,
                        embedding.profile_id,
                        embedding.connection_revision,
                        now,
                    ),
                )
                connection.execute("COMMIT")
        except AnalysisSelectionError:
            raise
        except sqlite3.Error as exc:
            raise RuntimeDatabaseError("runtime_analysis_selection_failed") from exc
        return self.view()

    def frozen_pair(self) -> AnalysisModelPair | None:
        """Capture the currently eligible revisions for one durable batch."""

        view = self.view()
        if not view.eligible:
            return None
        selection = view.selection
        if self._connections is None:
            return None
        try:
            chat = self._get(self._chat_profiles, selection.chat_profile_id or "", "chat")
            embedding = self._get(
                self._embedding_profiles, selection.embedding_profile_id or "", "embedding"
            )
            if (
                chat.connection_revision != selection.chat_connection_revision
                or embedding.connection_revision != selection.embedding_connection_revision
            ):
                return None
            connection = self._connections.get(chat.connection_id)  # type: ignore[attr-defined]
            if connection.revision != chat.connection_revision:
                return None
            embedding_connection = self._connections.get(  # type: ignore[attr-defined]
                embedding.connection_reference
            )
            if (
                embedding_connection.revision != embedding.connection_revision
                or embedding_connection.provider != embedding.provider
            ):
                return None
            return AnalysisModelPair(
                selection_generation=selection.generation,
                chat_profile_id=chat.profile_id,
                chat_connection_id=chat.connection_id,
                chat_connection_revision=chat.connection_revision,
                chat_provider=connection.provider,
                chat_model_id=chat.model_id,
                embedding_profile_id=embedding.profile_id,
                embedding_connection_id=embedding.connection_reference,
                embedding_connection_revision=embedding.connection_revision,
                embedding_provider=embedding.provider,
                embedding_identity=embedding.identity,
            )
        except (AnalysisSelectionError, AttributeError):
            return None

    def clear_reference(self, profile_id: str) -> None:
        now = _time(self._now())
        with self._database.connection() as connection:
            connection.execute(
                """
                UPDATE analysis_model_selection SET
                  chat_profile_id = CASE WHEN chat_profile_id = ?
                    THEN NULL ELSE chat_profile_id END,
                  chat_connection_revision = CASE WHEN chat_profile_id = ?
                    THEN NULL ELSE chat_connection_revision END,
                  embedding_profile_id = CASE WHEN embedding_profile_id = ?
                    THEN NULL ELSE embedding_profile_id END,
                  embedding_connection_revision = CASE WHEN embedding_profile_id = ?
                    THEN NULL ELSE embedding_connection_revision END,
                  selection_generation = selection_generation + 1, updated_at = ?
                WHERE selection_key = 'current'
                """,
                (profile_id, profile_id, profile_id, profile_id, now),
            )

    def _role_view(self, profile_id: str | None, role: str) -> dict[str, object]:
        if profile_id is None:
            return {"profile_id": None, "status": "unconfigured", "model_id": None}
        try:
            profile = self._get(
                self._chat_profiles if role == "chat" else self._embedding_profiles,
                profile_id,
                role,
            )
        except AnalysisSelectionError:
            return {"profile_id": profile_id, "status": "missing", "model_id": None}
        return {
            "profile_id": profile.profile_id,
            "model_id": profile.model_id,
            "status": profile.status,
            "connection_revision": profile.connection_revision,
            "tested": profile.last_probed_at is not None and profile.last_error_code is None,
        }

    @staticmethod
    def _get(registry: object, profile_id: str, role: str):
        try:
            return registry.get(profile_id)  # type: ignore[attr-defined]
        except Exception:
            raise AnalysisSelectionError(
                "CHAT_PROFILE_NOT_FOUND" if role == "chat" else "EMBEDDING_PROFILE_NOT_FOUND"
            ) from None


def _optional(value: object) -> str | None:
    return str(value) if value is not None else None


def _optional_int(value: object) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        raise RuntimeDatabaseError("runtime_analysis_selection_failed")
    return int(value)


def _required_text(value: object) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError
    return value


def _bounded_text(value: object) -> str:
    """Accept an explicit string, including a provider's legal empty prefix."""

    if not isinstance(value, str) or len(value) > 4_096:
        raise ValueError
    return value


def _required_int(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError
    return value


def _time(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")
