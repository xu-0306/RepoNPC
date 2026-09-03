"""Safe runtime registry for one active external embedding profile."""

from __future__ import annotations

import math
import re
import sqlite3
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from threading import RLock
from typing import Protocol

import numpy as np

from reponpc.bundles.manager import ActivationTransition
from reponpc.indexing.sources import EmbeddingIdentity
from reponpc.runtime.database import RuntimeDatabase, RuntimeDatabaseError

_PROFILE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")
_CONNECTION_REFERENCE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")
_MODEL_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:/-]{0,255}$")
_SAFE_ERROR_CODE = re.compile(r"^[A-Z][A-Z0-9_]{0,63}$")
_PROVIDERS = frozenset({"ollama", "openai_compatible", "vllm"})
_CURATED_OLLAMA_MODELS = frozenset({"qwen3-embedding:0.6b", "bge-m3", "embeddinggemma:300m"})


def embedding_model_catalog() -> tuple[dict[str, object], ...]:
    """Return the bounded, non-secret Ollama catalog approved by ADR-023."""

    return (
        {
            "provider": "ollama",
            "model_id": "qwen3-embedding:0.6b",
            "recommended": True,
            "license": "Apache-2.0",
            "language_context_notes": "zh-TW, English, and code; up to 32K upstream",
            "resource_hint": "approximately 639 MB for the curated Ollama tag",
            "operations": ["pull", "list", "probe", "delete"],
        },
        {
            "provider": "ollama",
            "model_id": "bge-m3",
            "recommended": False,
            "license": "MIT",
            "language_context_notes": "100+ languages; up to 8K upstream",
            "resource_hint": "approximately 1.2 GB for the curated Ollama tag",
            "operations": ["pull", "list", "probe", "delete"],
        },
        {
            "provider": "ollama",
            "model_id": "embeddinggemma:300m",
            "recommended": False,
            "license": "Google Gemma terms",
            "language_context_notes": "100+ languages; 2K Ollama context tag",
            "resource_hint": "small-resource 300M-class alternative",
            "operations": ["pull", "list", "probe", "delete"],
        },
    )


class EmbeddingProfileError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__("embedding profile operation failed")


class ProbeEmbeddingProvider(Protocol):
    def identity(self) -> EmbeddingIdentity: ...

    def embed_query(self, texts: list[str]) -> object: ...


@dataclass(frozen=True, slots=True)
class EmbeddingProfileInput:
    provider: str
    model_id: str
    dimension: int
    normalized: bool
    query_prefix: str
    passage_prefix: str
    connection_reference: str

    def validate(self) -> None:
        if (
            self.provider not in _PROVIDERS
            or not self.normalized
            or not 1 <= len(self.model_id) <= 256
            or not 1 <= self.dimension <= 65536
            or len(self.query_prefix) > 128
            or len(self.passage_prefix) > 128
            or not _CONNECTION_REFERENCE.fullmatch(self.connection_reference)
        ):
            raise EmbeddingProfileError("VALIDATION_ERROR")

    @property
    def identity(self) -> EmbeddingIdentity:
        return EmbeddingIdentity(
            adapter=("openai_compatible" if self.provider == "vllm" else self.provider),
            model_id=self.model_id,
            dimension=self.dimension,
            normalized=self.normalized,
            query_prefix=self.query_prefix,
            passage_prefix=self.passage_prefix,
        )


@dataclass(frozen=True, slots=True)
class EmbeddingProfile:
    profile_id: str
    provider: str
    model_id: str
    dimension: int
    normalized: bool
    query_prefix: str
    passage_prefix: str
    connection_reference: str
    status: str
    active: bool
    observed_adapter: str | None
    observed_model_id: str | None
    observed_dimension: int | None
    last_error_code: str | None
    created_at: str
    updated_at: str
    last_probed_at: str | None
    reindex_generation: int
    reindex_started_at: str | None
    reindex_completed_at: str | None
    bundle_id: str | None

    @property
    def identity(self) -> EmbeddingIdentity:
        return EmbeddingIdentity(
            adapter=("openai_compatible" if self.provider == "vllm" else self.provider),
            model_id=self.model_id,
            dimension=self.dimension,
            normalized=self.normalized,
            query_prefix=self.query_prefix,
            passage_prefix=self.passage_prefix,
        )


class EmbeddingProfileRegistry:
    """Persist safe profile metadata; credentials and private URLs stay external."""

    def __init__(
        self,
        *,
        database: RuntimeDatabase,
        provider_resolver: Callable[[EmbeddingProfile], ProbeEmbeddingProvider | None],
        activation_compatible: Callable[[EmbeddingProfile], bool],
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self._database = database
        self._provider_resolver = provider_resolver
        self._activation_compatible = activation_compatible
        self._now = now or (lambda: datetime.now(UTC))
        self._lock = RLock()

    def ensure_environment_profile(
        self, *, provider: str, identity: EmbeddingIdentity
    ) -> EmbeddingProfile:
        values = EmbeddingProfileInput(
            provider=provider,
            model_id=identity.model_id,
            dimension=identity.dimension,
            normalized=identity.normalized,
            query_prefix=identity.query_prefix,
            passage_prefix=identity.passage_prefix,
            connection_reference="environment",
        )
        values.validate()
        now = _time(self._now())
        profile_id = "environment"
        with self._database.connection() as connection:
            try:
                connection.execute("BEGIN IMMEDIATE")
                rows = connection.execute(
                    "SELECT * FROM embedding_profiles WHERE connection_reference = 'environment'"
                ).fetchall()
                matching = next(
                    (
                        _profile(row)
                        for row in rows
                        if _profile(row).provider == provider and _profile(row).identity == identity
                    ),
                    None,
                )
                if matching is not None:
                    profile_id = matching.profile_id
                else:
                    primary_row = next(
                        (row for row in rows if row["profile_id"] == "environment"),
                        None,
                    )
                    if primary_row is not None and bool(primary_row["active"]):
                        profile_id = _environment_candidate_id(provider, identity)
                    existing = connection.execute(
                        "SELECT active FROM embedding_profiles WHERE profile_id = ?",
                        (profile_id,),
                    ).fetchone()
                    if existing is not None and bool(existing["active"]):
                        raise RuntimeDatabaseError("runtime_embedding_profile_failed")
                if matching is None and existing is None:
                    connection.execute(
                        """
                        INSERT INTO embedding_profiles(
                          profile_id, provider, model_id, dimension, normalized,
                          query_prefix, passage_prefix, connection_reference,
                          status, active, observed_adapter, observed_model_id,
                          observed_dimension, last_error_code, created_at, updated_at,
                          last_probed_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, 'environment', 'probe', 0,
                                  NULL, NULL, NULL, NULL, ?, ?, NULL)
                        """,
                        (
                            profile_id,
                            values.provider,
                            values.model_id,
                            values.dimension,
                            int(values.normalized),
                            values.query_prefix,
                            values.passage_prefix,
                            now,
                            now,
                        ),
                    )
                elif matching is None:
                    connection.execute(
                        """
                        UPDATE embedding_profiles SET
                          provider = ?, model_id = ?, dimension = ?, normalized = ?,
                          query_prefix = ?, passage_prefix = ?,
                          status = 'reindex_required', observed_adapter = NULL,
                          observed_model_id = NULL, observed_dimension = NULL,
                          last_error_code = NULL, updated_at = ?, last_probed_at = NULL
                        WHERE profile_id = ? AND active = 0
                        """,
                        (
                            values.provider,
                            values.model_id,
                            values.dimension,
                            int(values.normalized),
                            values.query_prefix,
                            values.passage_prefix,
                            now,
                            profile_id,
                        ),
                    )
                connection.execute("COMMIT")
            except (sqlite3.Error, RuntimeDatabaseError) as exc:
                _rollback(connection)
                raise RuntimeDatabaseError("runtime_embedding_profile_failed") from exc
        return self.get(profile_id)

    def list(self) -> tuple[EmbeddingProfile, ...]:
        with self._database.connection() as connection:
            rows = connection.execute(
                "SELECT * FROM embedding_profiles ORDER BY active DESC, created_at, profile_id"
            ).fetchall()
        return tuple(_profile(row) for row in rows)

    def get(self, profile_id: str) -> EmbeddingProfile:
        if not _PROFILE_ID.fullmatch(profile_id):
            raise EmbeddingProfileError("VALIDATION_ERROR")
        with self._database.connection() as connection:
            row = connection.execute(
                "SELECT * FROM embedding_profiles WHERE profile_id = ?", (profile_id,)
            ).fetchone()
        if row is None:
            raise EmbeddingProfileError("NOT_FOUND")
        return _profile(row)

    def create(self, values: EmbeddingProfileInput) -> EmbeddingProfile:
        values.validate()
        profile_id = f"profile-{uuid.uuid4().hex[:16]}"
        now = _time(self._now())
        with self._database.connection() as connection:
            try:
                connection.execute(
                    """
                    INSERT INTO embedding_profiles(
                      profile_id, provider, model_id, dimension, normalized,
                      query_prefix, passage_prefix, connection_reference,
                      status, active, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'probe', 0, ?, ?)
                    """,
                    (
                        profile_id,
                        values.provider,
                        values.model_id,
                        values.dimension,
                        int(values.normalized),
                        values.query_prefix,
                        values.passage_prefix,
                        values.connection_reference,
                        now,
                        now,
                    ),
                )
            except sqlite3.Error as exc:
                raise RuntimeDatabaseError("runtime_embedding_profile_failed") from exc
        return self.get(profile_id)

    def update(self, profile_id: str, values: EmbeddingProfileInput) -> EmbeddingProfile:
        values.validate()
        current = self.get(profile_id)
        if current.active:
            raise EmbeddingProfileError("EMBEDDING_PROFILE_ACTIVE_IMMUTABLE")
        if current.status == "reindexing":
            raise EmbeddingProfileError("EMBEDDING_REINDEX_ACTIVE")
        now = _time(self._now())
        with self._database.connection() as connection:
            connection.execute(
                """
                UPDATE embedding_profiles SET
                  provider = ?, model_id = ?, dimension = ?, normalized = ?,
                  query_prefix = ?, passage_prefix = ?, connection_reference = ?,
                  status = 'reindex_required', observed_adapter = NULL,
                  observed_model_id = NULL, observed_dimension = NULL,
                  last_error_code = NULL, updated_at = ?, last_probed_at = NULL
                WHERE profile_id = ?
                """,
                (
                    values.provider,
                    values.model_id,
                    values.dimension,
                    int(values.normalized),
                    values.query_prefix,
                    values.passage_prefix,
                    values.connection_reference,
                    now,
                    profile_id,
                ),
            )
        return self.get(profile_id)

    def delete(self, profile_id: str) -> None:
        current = self.get(profile_id)
        if current.active:
            raise EmbeddingProfileError("EMBEDDING_PROFILE_ACTIVE_REQUIRED")
        if current.status == "reindexing":
            raise EmbeddingProfileError("EMBEDDING_REINDEX_ACTIVE")
        with self._database.connection() as connection:
            connection.execute("DELETE FROM embedding_profiles WHERE profile_id = ?", (profile_id,))

    def probe(self, profile_id: str) -> EmbeddingProfile:
        profile = self.get(profile_id)
        provider = self._provider_resolver(profile)
        now = _time(self._now())
        error_code: str | None = None
        observed: EmbeddingIdentity | None = None
        try:
            if provider is None:
                raise EmbeddingProfileError("EMBEDDING_CONNECTION_REQUIRED")
            observed = provider.identity()
            output = provider.embed_query(["RepoNPC embedding readiness probe"])
            shape = getattr(output, "shape", None)
            if shape != (1, observed.dimension):
                raise EmbeddingProfileError("EMBEDDING_PROBE_DIMENSION_MISMATCH")
            if getattr(output, "dtype", None) != np.dtype(np.float32):
                raise EmbeddingProfileError("EMBEDDING_PROBE_INVALID_VECTOR")
            vector = np.asarray(output, dtype=np.float32)
            if not all(math.isfinite(float(value)) for value in vector.flat):
                raise EmbeddingProfileError("EMBEDDING_PROBE_INVALID_VECTOR")
            if not np.allclose(np.linalg.norm(vector, axis=1), 1.0, rtol=1e-4, atol=1e-6):
                raise EmbeddingProfileError("EMBEDDING_PROBE_NOT_NORMALIZED")
            if observed != profile.identity:
                raise EmbeddingProfileError("EMBEDDING_PROFILE_IDENTITY_MISMATCH")
        except EmbeddingProfileError as exc:
            error_code = exc.code
        except Exception:
            error_code = "EMBEDDING_PROBE_FAILED"

        status = (
            "last_known_good"
            if error_code is not None and profile.active
            else "probe_failed"
            if error_code is not None
            else "ready"
            if self._activation_compatible(profile)
            else "last_known_good"
            if profile.active
            else "reindex_required"
        )
        with self._database.connection() as connection:
            connection.execute(
                """
                UPDATE embedding_profiles SET status = ?, observed_adapter = ?,
                  observed_model_id = ?, observed_dimension = ?, last_error_code = ?,
                  updated_at = ?, last_probed_at = ? WHERE profile_id = ?
                """,
                (
                    status,
                    observed.adapter if observed else None,
                    observed.model_id if observed else None,
                    observed.dimension if observed else None,
                    error_code,
                    now,
                    now,
                    profile_id,
                ),
            )
        return self.get(profile_id)

    def active_matches(self, identity: EmbeddingIdentity) -> bool:
        """Return whether the sole active profile is ready for this runtime identity."""

        with self._database.connection() as connection:
            row = connection.execute("SELECT * FROM embedding_profiles WHERE active = 1").fetchone()
        if row is None:
            return False
        profile = _profile(row)
        return profile.status in {"ready", "last_known_good"} and profile.identity == identity

    def active(self) -> EmbeddingProfile | None:
        """Return the sole active profile, if one has completed activation."""

        with self._database.connection() as connection:
            row = connection.execute("SELECT * FROM embedding_profiles WHERE active = 1").fetchone()
        return _profile(row) if row is not None else None

    def resolve_provider(self, profile: EmbeddingProfile) -> ProbeEmbeddingProvider | None:
        """Resolve only the server-side connection reference for a frozen profile."""

        return self._provider_resolver(profile)

    def begin_reindex(self, profile_id: str) -> EmbeddingProfile:
        """Freeze one successfully probed candidate and durably start a generation."""

        with self._lock:
            profile = self.get(profile_id)
            if profile.active:
                raise EmbeddingProfileError("EMBEDDING_PROFILE_ACTIVE_IMMUTABLE")
            if (
                profile.last_probed_at is None
                or profile.last_error_code is not None
                or profile.observed_adapter != profile.identity.adapter
                or profile.observed_model_id != profile.identity.model_id
                or profile.observed_dimension != profile.identity.dimension
            ):
                raise EmbeddingProfileError("EMBEDDING_PROBE_REQUIRED")
            now = _time(self._now())
            with self._database.connection() as connection:
                try:
                    connection.execute("BEGIN IMMEDIATE")
                    other = connection.execute(
                        "SELECT profile_id FROM embedding_profiles "
                        "WHERE status = 'reindexing' AND profile_id <> ?",
                        (profile_id,),
                    ).fetchone()
                    if other is not None:
                        raise EmbeddingProfileError("EMBEDDING_REINDEX_ACTIVE")
                    connection.execute(
                        """
                        UPDATE embedding_profiles SET status = 'reindexing',
                          reindex_generation = reindex_generation + 1,
                          reindex_started_at = ?, reindex_completed_at = NULL,
                          last_error_code = NULL, updated_at = ?
                        WHERE profile_id = ?
                        """,
                        (now, now, profile_id),
                    )
                    connection.execute("COMMIT")
                except EmbeddingProfileError:
                    _rollback(connection)
                    raise
                except sqlite3.Error as exc:
                    _rollback(connection)
                    raise RuntimeDatabaseError("runtime_embedding_profile_failed") from exc
            return self.get(profile_id)

    def fail_reindex(self, profile_id: str, generation: int, error_code: str) -> EmbeddingProfile:
        """Fail one exact generation without changing the active last-known-good."""

        if not _SAFE_ERROR_CODE.fullmatch(error_code):
            error_code = "EMBEDDING_REINDEX_FAILED"
        now = _time(self._now())
        with self._database.connection() as connection:
            connection.execute(
                """
                UPDATE embedding_profiles SET status = 'reindex_required',
                  last_error_code = ?, reindex_completed_at = ?, updated_at = ?
                WHERE profile_id = ? AND reindex_generation = ?
                  AND active = 0 AND status = 'reindexing'
                """,
                (error_code, now, now, profile_id, generation),
            )
        return self.get(profile_id)

    def activate_reindexed(
        self,
        profile_id: str,
        generation: int,
        bundle_id: str,
    ) -> ActivationTransition:
        """Commit profile metadata and return a bounded activation rollback."""

        now = _time(self._now())
        with self._lock, self._database.connection() as connection:
            try:
                connection.execute("BEGIN IMMEDIATE")
                target = connection.execute(
                    "SELECT * FROM embedding_profiles WHERE profile_id = ?",
                    (profile_id,),
                ).fetchone()
                if (
                    target is None
                    or int(target["reindex_generation"]) != generation
                    or str(target["status"]) != "reindexing"
                    or bool(target["active"])
                ):
                    raise EmbeddingProfileError("EMBEDDING_REINDEX_STALE")
                previous = connection.execute(
                    "SELECT profile_id, status, bundle_id FROM embedding_profiles WHERE active = 1"
                ).fetchone()
                connection.execute(
                    """
                    INSERT OR REPLACE INTO embedding_switch_intent(
                      state_key, generation, from_profile_id, from_bundle_id,
                      to_profile_id, to_bundle_id, created_at
                    ) VALUES ('current', ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        generation,
                        str(previous["profile_id"]) if previous is not None else None,
                        (
                            str(previous["bundle_id"])
                            if previous is not None and previous["bundle_id"] is not None
                            else None
                        ),
                        profile_id,
                        bundle_id,
                        now,
                    ),
                )
                connection.execute(
                    "UPDATE embedding_profiles SET active = 0, "
                    "status = 'last_known_good', updated_at = ? WHERE active = 1",
                    (now,),
                )
                connection.execute(
                    """
                    UPDATE embedding_profiles SET active = 1, status = 'ready',
                      bundle_id = ?, last_error_code = NULL,
                      reindex_completed_at = ?, updated_at = ?
                    WHERE profile_id = ?
                    """,
                    (bundle_id, now, now, profile_id),
                )
                connection.execute("COMMIT")
            except EmbeddingProfileError:
                _rollback(connection)
                raise
            except sqlite3.Error as exc:
                _rollback(connection)
                raise RuntimeDatabaseError("runtime_embedding_profile_failed") from exc

        previous_id = str(previous["profile_id"]) if previous is not None else None
        previous_status = str(previous["status"]) if previous is not None else None
        previous_bundle = (
            str(previous["bundle_id"])
            if previous is not None and previous["bundle_id"] is not None
            else None
        )

        def rollback() -> None:
            rollback_now = _time(self._now())
            with self._lock, self._database.connection() as rollback_connection:
                try:
                    rollback_connection.execute("BEGIN IMMEDIATE")
                    current = rollback_connection.execute(
                        "SELECT active, reindex_generation FROM embedding_profiles "
                        "WHERE profile_id = ?",
                        (profile_id,),
                    ).fetchone()
                    if (
                        current is None
                        or not bool(current["active"])
                        or int(current["reindex_generation"]) != generation
                    ):
                        rollback_connection.execute("ROLLBACK")
                        return
                    rollback_connection.execute(
                        "UPDATE embedding_profiles SET active = 0, status = 'reindexing', "
                        "bundle_id = NULL, reindex_completed_at = NULL, updated_at = ? "
                        "WHERE profile_id = ?",
                        (rollback_now, profile_id),
                    )
                    if previous_id is not None:
                        rollback_connection.execute(
                            "UPDATE embedding_profiles SET active = 1, status = ?, "
                            "bundle_id = ?, updated_at = ? WHERE profile_id = ?",
                            (
                                previous_status or "last_known_good",
                                previous_bundle,
                                rollback_now,
                                previous_id,
                            ),
                        )
                    rollback_connection.execute(
                        "DELETE FROM embedding_switch_intent WHERE state_key = 'current' "
                        "AND generation = ? AND to_profile_id = ? AND to_bundle_id = ?",
                        (generation, profile_id, bundle_id),
                    )
                    rollback_connection.execute("COMMIT")
                except sqlite3.Error as exc:
                    _rollback(rollback_connection)
                    raise RuntimeDatabaseError("runtime_embedding_profile_failed") from exc

        def commit() -> None:
            with self._database.connection() as commit_connection:
                commit_connection.execute(
                    "DELETE FROM embedding_switch_intent WHERE state_key = 'current' "
                    "AND generation = ? AND to_profile_id = ? AND to_bundle_id = ?",
                    (generation, profile_id, bundle_id),
                )

        return ActivationTransition(rollback=rollback, commit=commit)

    def recover_interrupted_reindexes(self) -> None:
        """Make restart-interrupted work explicitly retryable without fallback."""

        now = _time(self._now())
        with self._database.connection() as connection:
            connection.execute(
                """
                UPDATE embedding_profiles SET status = 'reindex_required',
                  last_error_code = 'EMBEDDING_REINDEX_INTERRUPTED',
                  reindex_completed_at = ?, updated_at = ?
                WHERE status = 'reindexing' AND active = 0
                """,
                (now, now),
            )

    def reconcile_active_bundle(
        self, identity: EmbeddingIdentity | None, bundle_id: str | None
    ) -> None:
        """Repair only crash-window metadata from a reverified retained bundle."""

        self.recover_interrupted_reindexes()
        now = _time(self._now())
        with self._lock, self._database.connection() as connection:
            rows = connection.execute("SELECT * FROM embedding_profiles").fetchall()
            intent = connection.execute(
                "SELECT * FROM embedding_switch_intent WHERE state_key = 'current'"
            ).fetchone()
            current = next((row for row in rows if bool(row["active"])), None)
            if identity is None or bundle_id is None:
                if current is not None:
                    connection.execute(
                        "UPDATE embedding_profiles SET active = 0, status = 'reindex_required', "
                        "last_error_code = 'EMBEDDING_BUNDLE_UNAVAILABLE', updated_at = ? "
                        "WHERE profile_id = ?",
                        (now, str(current["profile_id"])),
                    )
                return
            matching = [row for row in rows if _profile(row).identity == identity]
            intent_profile_id = None
            if intent is not None:
                if str(intent["to_bundle_id"]) == bundle_id:
                    intent_profile_id = str(intent["to_profile_id"])
                elif intent["from_bundle_id"] == bundle_id and intent["from_profile_id"]:
                    intent_profile_id = str(intent["from_profile_id"])
            selected = next(
                (
                    row
                    for row in matching
                    if intent_profile_id is not None and str(row["profile_id"]) == intent_profile_id
                ),
                next(
                    (row for row in matching if bool(row["active"])),
                    next(
                        (
                            row
                            for row in matching
                            if row["bundle_id"] == bundle_id and row["last_probed_at"] is not None
                        ),
                        next(
                            (
                                row
                                for row in matching
                                if str(row["status"]) == "last_known_good"
                                and row["last_probed_at"] is not None
                            ),
                            None,
                        ),
                    ),
                ),
            )
            if selected is None:
                return
            try:
                connection.execute("BEGIN IMMEDIATE")
                connection.execute(
                    "UPDATE embedding_profiles SET active = 0, "
                    "status = CASE WHEN active = 1 THEN 'last_known_good' ELSE status END, "
                    "updated_at = ? WHERE active = 1",
                    (now,),
                )
                connection.execute(
                    "UPDATE embedding_profiles SET active = 1, status = 'ready', "
                    "bundle_id = ?, last_error_code = NULL, updated_at = ? "
                    "WHERE profile_id = ?",
                    (bundle_id, now, str(selected["profile_id"])),
                )
                connection.execute(
                    "DELETE FROM embedding_switch_intent WHERE state_key = 'current'"
                )
                connection.execute("COMMIT")
            except sqlite3.Error as exc:
                _rollback(connection)
                raise RuntimeDatabaseError("runtime_embedding_profile_failed") from exc

    def installed_ollama_models(self) -> tuple[str, ...]:
        """List safe model IDs from the configured Ollama connection."""

        for profile in self.list():
            if profile.provider != "ollama":
                continue
            provider = self._provider_resolver(profile)
            operation = getattr(provider, "installed_models", None)
            if not callable(operation):
                continue
            try:
                models = operation()
            except Exception:
                raise EmbeddingProfileError("EMBEDDING_MODEL_OPERATION_FAILED") from None
            if not isinstance(models, tuple) or any(
                not isinstance(model, str) or not _MODEL_ID.fullmatch(model) for model in models
            ):
                raise EmbeddingProfileError("EMBEDDING_MODEL_OPERATION_FAILED")
            return tuple(sorted(set(models)))
        raise EmbeddingProfileError("EMBEDDING_CONNECTION_REQUIRED")

    def activate(self, profile_id: str) -> EmbeddingProfile:
        profile = self.get(profile_id)
        if profile.status != "ready" or not self._activation_compatible(profile):
            raise EmbeddingProfileError("EMBEDDING_REINDEX_REQUIRED")
        now = _time(self._now())
        with self._database.connection() as connection:
            try:
                connection.execute("BEGIN IMMEDIATE")
                connection.execute(
                    "UPDATE embedding_profiles SET active = 0, status = CASE "
                    "WHEN active = 1 THEN 'last_known_good' ELSE status END, updated_at = ? "
                    "WHERE active = 1",
                    (now,),
                )
                connection.execute(
                    "UPDATE embedding_profiles SET active = 1, status = 'ready', "
                    "updated_at = ? WHERE profile_id = ?",
                    (now, profile_id),
                )
                connection.execute("COMMIT")
            except sqlite3.Error as exc:
                _rollback(connection)
                raise RuntimeDatabaseError("runtime_embedding_profile_failed") from exc
        return self.get(profile_id)

    def ollama_model_action(
        self, profile_id: str, *, action: str, confirmed: bool
    ) -> EmbeddingProfile:
        profile, operation = self.prepare_ollama_model_action(
            profile_id, action=action, confirmed=confirmed
        )
        try:
            operation()
        except Exception:
            raise EmbeddingProfileError("EMBEDDING_MODEL_OPERATION_FAILED") from None
        return self.complete_ollama_model_action(profile.profile_id, action=action, succeeded=True)

    def prepare_ollama_model_action(
        self, profile_id: str, *, action: str, confirmed: bool
    ) -> tuple[EmbeddingProfile, Callable[..., None]]:
        """Validate a curated operation and return only its provider-owned callable."""

        profile = self.get(profile_id)
        if not confirmed or action not in {"pull", "delete"} or profile.provider != "ollama":
            raise EmbeddingProfileError("VALIDATION_ERROR")
        if profile.model_id not in _CURATED_OLLAMA_MODELS:
            raise EmbeddingProfileError("VALIDATION_ERROR")
        if any(
            candidate.active
            and candidate.provider == profile.provider
            and candidate.model_id == profile.model_id
            and candidate.connection_reference == profile.connection_reference
            for candidate in self.list()
        ):
            raise EmbeddingProfileError("EMBEDDING_PROFILE_ACTIVE_REQUIRED")
        provider = self._provider_resolver(profile)
        operation = getattr(provider, f"{action}_model", None)
        if not callable(operation):
            raise EmbeddingProfileError("EMBEDDING_CONNECTION_REQUIRED")
        return profile, operation

    def complete_ollama_model_action(
        self, profile_id: str, *, action: str, succeeded: bool
    ) -> EmbeddingProfile:
        """Publish only the safe terminal effect of a provider-owned operation."""

        if action not in {"pull", "delete"} or not succeeded:
            raise EmbeddingProfileError("VALIDATION_ERROR")
        now = _time(self._now())
        with self._database.connection() as connection:
            connection.execute(
                "UPDATE embedding_profiles SET status = ?, last_error_code = NULL, "
                "updated_at = ?, last_probed_at = NULL WHERE profile_id = ?",
                ("probe" if action == "pull" else "probe_failed", now, profile_id),
            )
        return self.get(profile_id)


def _profile(row: sqlite3.Row) -> EmbeddingProfile:
    return EmbeddingProfile(
        profile_id=str(row["profile_id"]),
        provider=str(row["provider"]),
        model_id=str(row["model_id"]),
        dimension=int(row["dimension"]),
        normalized=bool(row["normalized"]),
        query_prefix=str(row["query_prefix"]),
        passage_prefix=str(row["passage_prefix"]),
        connection_reference=str(row["connection_reference"]),
        status=str(row["status"]),
        active=bool(row["active"]),
        observed_adapter=(str(row["observed_adapter"]) if row["observed_adapter"] else None),
        observed_model_id=(str(row["observed_model_id"]) if row["observed_model_id"] else None),
        observed_dimension=(int(row["observed_dimension"]) if row["observed_dimension"] else None),
        last_error_code=(str(row["last_error_code"]) if row["last_error_code"] else None),
        created_at=str(row["created_at"]),
        updated_at=str(row["updated_at"]),
        last_probed_at=(str(row["last_probed_at"]) if row["last_probed_at"] else None),
        reindex_generation=int(row["reindex_generation"]),
        reindex_started_at=(str(row["reindex_started_at"]) if row["reindex_started_at"] else None),
        reindex_completed_at=(
            str(row["reindex_completed_at"]) if row["reindex_completed_at"] else None
        ),
        bundle_id=(str(row["bundle_id"]) if row["bundle_id"] else None),
    )


def _time(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _environment_candidate_id(provider: str, identity: EmbeddingIdentity) -> str:
    value = "\x1f".join(
        (
            provider,
            identity.adapter,
            identity.model_id,
            str(identity.dimension),
            str(identity.normalized),
            identity.query_prefix,
            identity.passage_prefix,
        )
    )
    return f"environment-{sha256(value.encode()).hexdigest()[:12]}"


def _rollback(connection: sqlite3.Connection) -> None:
    if connection.in_transaction:
        connection.execute("ROLLBACK")
