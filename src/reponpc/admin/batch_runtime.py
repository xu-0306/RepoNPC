"""Durable, secret-free state for bounded guided-analysis batches.

The runtime store deliberately persists only scheduling state, public repository
selection policy, immutable commits, safe events, and already validated output.
It owns neither a GitHub credential nor raw archive/provider content.
"""

from __future__ import annotations

import hashlib
import json
import secrets
import sqlite3
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Final

from reponpc.admin.batch_resolver import (
    GITHUB_ARCHIVE_BASE_URL,
    GitHubRateResource,
    RateBudget,
    RepositoryMetadataHint,
    RepositorySelection,
    ResolvedRepository,
)
from reponpc.runtime.database import RuntimeDatabase, RuntimeDatabaseError

BATCH_TTL: Final = timedelta(hours=24)
GITHUB_RESOLUTION_TTL: Final = timedelta(hours=2)
EVENT_REPLAY_LIMIT: Final = 200
ACTIVE_BATCH_STATES: Final = frozenset({"queued", "running", "paused", "cancelling"})
ITEM_TERMINAL_STATES: Final = frozenset(
    {"complete", "failed", "cancelled", "needs_retry_confirmation"}
)
ITEM_ACTIVE_STAGES: Final = frozenset(
    {
        "resolving_commit",
        "fetching_source",
        "filtering",
        "indexing",
        "embedding",
        "generating",
        "validating",
        "cleaning_up",
    }
)
ITEM_SCHEDULABLE_STATES: Final = frozenset({"queued", "waiting_rate_limit"})
FAILED_ITEM_STATES: Final = frozenset({"failed", "needs_retry_confirmation"})
TERMINAL_BATCH_STATES: Final = frozenset(
    {"cancelled", "completed", "completed_with_errors", "failed"}
)


class BatchRuntimeError(RuntimeError):
    """A stable, safe batch-state failure."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__("analysis batch operation failed")


class SQLiteGitHubResolutionCache:
    """Persist safe partial/exact anonymous resolution across rate resets."""

    def __init__(
        self,
        database: RuntimeDatabase,
        *,
        ttl: timedelta = GITHUB_RESOLUTION_TTL,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        if ttl <= timedelta(0):
            raise ValueError("GitHub resolution cache TTL must be positive")
        self._database = database
        self._ttl = ttl
        self._now = now or (lambda: datetime.now(UTC))

    def metadata(self, slug: str) -> RepositoryMetadataHint | None:
        row = self._load(_github_resolution_key("metadata", slug, None), "metadata")
        if row is None:
            return None
        return RepositoryMetadataHint(
            slug=str(row["repository_slug"]),
            node_id=str(row["node_id"]),
            default_branch=str(row["default_branch"]),
            is_archived=bool(row["is_archived"]),
        )

    def resolved(self, selection: RepositorySelection) -> ResolvedRepository | None:
        row = self._load(
            _github_resolution_key("resolved", selection.slug, selection.ref),
            "resolved",
        )
        if row is None or not _is_commit(str(row["commit_sha"] or "")):
            return None
        owner, name = selection.slug.split("/", 1)
        commit = str(row["commit_sha"])
        return ResolvedRepository(
            slug=selection.slug,
            node_id=str(row["node_id"]),
            default_branch=str(row["default_branch"]),
            commit_sha=commit,
            is_archived=bool(row["is_archived"]),
            archive_url=f"{GITHUB_ARCHIVE_BASE_URL}/repos/{owner}/{name}/tarball/{commit}",
        )

    def save_metadata(self, metadata: RepositoryMetadataHint) -> None:
        self._save(
            key=_github_resolution_key("metadata", metadata.slug, None),
            kind="metadata",
            slug=metadata.slug,
            requested_ref=None,
            node_id=metadata.node_id,
            default_branch=metadata.default_branch,
            commit_sha=None,
            is_archived=metadata.is_archived,
        )

    def save_resolved(self, selection: RepositorySelection, repository: ResolvedRepository) -> None:
        if repository.slug != selection.slug or not _is_commit(repository.commit_sha):
            raise BatchRuntimeError("VALIDATION_ERROR")
        self._save(
            key=_github_resolution_key("resolved", selection.slug, selection.ref),
            kind="resolved",
            slug=selection.slug,
            requested_ref=selection.ref,
            node_id=repository.node_id,
            default_branch=repository.default_branch,
            commit_sha=repository.commit_sha,
            is_archived=repository.is_archived,
        )

    def discard(self, selections: Sequence[RepositorySelection]) -> None:
        keys = [
            key
            for selection in selections
            for key in (
                _github_resolution_key("metadata", selection.slug, None),
                _github_resolution_key("resolved", selection.slug, selection.ref),
            )
        ]
        if not keys:
            return
        try:
            with self._database.connection() as connection:
                connection.executemany(
                    "DELETE FROM github_public_resolution_cache WHERE cache_key = ?",
                    ((key,) for key in keys),
                )
        except sqlite3.Error as exc:
            raise RuntimeDatabaseError("runtime_github_resolution_cache_failed") from exc

    def _load(self, key: str, kind: str) -> sqlite3.Row | None:
        now = _timestamp(_utc(self._now()))
        try:
            with self._database.connection() as connection:
                connection.execute(
                    "DELETE FROM github_public_resolution_cache WHERE expires_at <= ?",
                    (now,),
                )
                row = connection.execute(
                    """
                    SELECT * FROM github_public_resolution_cache
                    WHERE cache_key = ? AND entry_kind = ? AND expires_at > ?
                    """,
                    (key, kind, now),
                ).fetchone()
            return row
        except sqlite3.Error as exc:
            raise RuntimeDatabaseError("runtime_github_resolution_cache_failed") from exc

    def _save(
        self,
        *,
        key: str,
        kind: str,
        slug: str,
        requested_ref: str | None,
        node_id: str,
        default_branch: str,
        commit_sha: str | None,
        is_archived: bool,
    ) -> None:
        now = _utc(self._now())
        try:
            with self._database.connection() as connection:
                connection.execute(
                    """
                    INSERT INTO github_public_resolution_cache(
                      cache_key, entry_kind, repository_slug, requested_ref, node_id,
                      default_branch, commit_sha, is_archived, created_at, expires_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(cache_key) DO UPDATE SET
                      node_id = excluded.node_id,
                      default_branch = excluded.default_branch,
                      commit_sha = excluded.commit_sha,
                      is_archived = excluded.is_archived,
                      created_at = excluded.created_at,
                      expires_at = excluded.expires_at
                    """,
                    (
                        key,
                        kind,
                        slug,
                        requested_ref,
                        node_id,
                        default_branch,
                        commit_sha,
                        int(is_archived),
                        _timestamp(now),
                        _timestamp(now + self._ttl),
                    ),
                )
        except sqlite3.Error as exc:
            raise RuntimeDatabaseError("runtime_github_resolution_cache_failed") from exc


@dataclass(frozen=True, slots=True)
class BatchItemInput:
    """Safe persisted policy and immutable source identity for one item."""

    slug: str
    ref: str | None
    include: tuple[str, ...]
    exclude: tuple[str, ...]
    commit_sha: str
    source_item_id: str | None = None

    def policy_json(self) -> str:
        return json.dumps(
            {
                "slug": self.slug,
                "ref": self.ref,
                "include": list(self.include),
                "exclude": list(self.exclude),
            },
            sort_keys=True,
            separators=(",", ":"),
        )


@dataclass(frozen=True, slots=True)
class BatchCreateRequest:
    plan_id: str
    selection_hash: str
    idempotency_key: str
    items: tuple[BatchItemInput, ...]
    maximum_generation_attempts: int = 3
    execution_budget_seconds: int = 1800
    analysis_model_pair: dict[str, object] | None = None
    source_batch_id: str | None = None
    analysis_round: int = 1
    idempotency_request_hash: str | None = None


@dataclass(frozen=True, slots=True)
class BatchEvent:
    event_id: int
    batch_id: str
    item_id: str | None
    event_type: str
    payload: dict[str, object]
    occurred_at: str


@dataclass(frozen=True, slots=True)
class BatchItemSnapshot:
    item_id: str
    slug: str
    requested_ref: str | None
    commit_sha: str | None
    state: str
    retryable: bool
    reanalyzable: bool
    retry_blocker: str | None
    error_code: str | None
    error_reason: str | None
    failure_stage: str | None
    retry_at: str | None
    execution_elapsed_seconds: int
    execution_budget_seconds: int
    recovery_execution_budget_seconds: int
    generation_attempt_count: int
    source_item_id: str | None
    result: dict[str, object] | None


@dataclass(frozen=True, slots=True)
class BatchSnapshot:
    batch_id: str
    state: str
    plan_id: str
    selection_hash: str
    maximum_generation_attempts: int
    recovery_maximum_generation_attempts: int
    source_batch_id: str | None
    analysis_round: int
    analysis_model_pair: dict[str, object] | None
    created_at: str
    started_at: str | None
    completed_at: str | None
    expires_at: str | None
    error_code: str | None
    items: tuple[BatchItemSnapshot, ...]

    @property
    def progress(self) -> dict[str, int]:
        terminal = sum(item.state in ITEM_TERMINAL_STATES for item in self.items)
        return {
            "total": len(self.items),
            "complete": sum(item.state == "complete" for item in self.items),
            "failed": sum(item.state == "failed" for item in self.items),
            "cancelled": sum(item.state == "cancelled" for item in self.items),
            "needs_retry_confirmation": sum(
                item.state == "needs_retry_confirmation" for item in self.items
            ),
            "terminal": terminal,
            "active": sum(item.state in ITEM_ACTIVE_STAGES for item in self.items),
        }


@dataclass(frozen=True, slots=True)
class ClaimedBatchItem:
    batch_id: str
    item_id: str
    lease_id: str
    selection_hash: str
    input: BatchItemInput
    execution_elapsed_seconds: int
    execution_budget_seconds: int
    generation_attempt_count: int
    maximum_generation_attempts: int
    analysis_model_pair: dict[str, object] | None


@dataclass(frozen=True, slots=True)
class BatchReanalysisSource:
    """Validated secret-free inputs for one successor analysis round."""

    source_batch_id: str
    analysis_round: int
    items: tuple[BatchItemInput, ...]
    analysis_model_pair: dict[str, object] | None


@dataclass(frozen=True, slots=True)
class CacheEntry:
    cache_key: str
    cache_kind: str
    derived_index_key: str
    metadata: dict[str, object]
    payload: dict[str, object]


class SQLiteGitHubRateStateStore:
    """Persist sanitized GitHub rate budgets across bounded-worker restarts."""

    def __init__(
        self, database: RuntimeDatabase, *, now: Callable[[], datetime] | None = None
    ) -> None:
        self._database = database
        self._now = now or (lambda: datetime.now(UTC))

    def load(self) -> tuple[RateBudget, datetime | None]:
        values = {
            GitHubRateResource.CORE: RateBudget(GitHubRateResource.CORE, None, None, None),
        }
        secondary: datetime | None = None
        try:
            with self._database.connection() as connection:
                rows = connection.execute("SELECT * FROM github_rate_state").fetchall()
        except sqlite3.Error as exc:
            raise RuntimeDatabaseError("runtime_github_rate_state_failed") from exc
        for row in rows:
            resource = str(row["resource"])
            if resource == "secondary":
                secondary = _parse_optional_timestamp(row["retry_at"])
            elif resource == GitHubRateResource.CORE:
                parsed_resource = GitHubRateResource(resource)
                values[parsed_resource] = RateBudget(
                    resource=parsed_resource,
                    limit=_optional_int(row["limit_value"]),
                    remaining=_optional_int(row["remaining"]),
                    reset_at=_parse_optional_timestamp(row["reset_at"]),
                )
        return values[GitHubRateResource.CORE], secondary

    def save(
        self,
        *,
        core: RateBudget,
        secondary_retry_at: datetime | None,
    ) -> None:
        now = _timestamp(_utc(self._now()))
        rows = (
            (
                GitHubRateResource.CORE,
                core.remaining,
                core.limit,
                _timestamp(core.reset_at) if core.reset_at is not None else None,
                None,
                now,
            ),
            (
                "secondary",
                None,
                None,
                None,
                _timestamp(secondary_retry_at) if secondary_retry_at is not None else None,
                now,
            ),
        )
        try:
            with self._database.connection() as connection:
                connection.executemany(
                    """
                    INSERT INTO github_rate_state(
                      resource, remaining, limit_value, reset_at, retry_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(resource) DO UPDATE SET
                      remaining = excluded.remaining,
                      limit_value = excluded.limit_value,
                      reset_at = excluded.reset_at,
                      retry_at = excluded.retry_at,
                      updated_at = excluded.updated_at
                    """,
                    rows,
                )
        except sqlite3.Error as exc:
            raise RuntimeDatabaseError("runtime_github_rate_state_failed") from exc


class BatchRuntimeStore:
    """SQLite transitions for at most one active owner-scoped batch."""

    def __init__(
        self,
        database: RuntimeDatabase,
        *,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self._database = database
        self._now = now or (lambda: datetime.now(UTC))

    def create_batch(self, request: BatchCreateRequest) -> tuple[BatchSnapshot, bool]:
        """Create a batch once, returning an existing idempotent result if any."""

        if not request.plan_id or not _is_hash(request.selection_hash):
            raise BatchRuntimeError("ANALYSIS_PLAN_STALE")
        if not request.idempotency_key or len(request.idempotency_key) > 512:
            raise BatchRuntimeError("VALIDATION_ERROR")
        if not request.items or len(request.items) > 50:
            raise BatchRuntimeError("VALIDATION_ERROR")
        if not 1 <= request.maximum_generation_attempts <= 10:
            raise BatchRuntimeError("VALIDATION_ERROR")
        if not 1 <= request.execution_budget_seconds <= 7200:
            raise BatchRuntimeError("VALIDATION_ERROR")
        if request.analysis_model_pair is not None and not _is_analysis_model_pair(
            request.analysis_model_pair
        ):
            raise BatchRuntimeError("VALIDATION_ERROR")
        if request.source_batch_id is not None and not 1 <= len(request.source_batch_id) <= 64:
            raise BatchRuntimeError("VALIDATION_ERROR")
        if request.analysis_round < 1:
            raise BatchRuntimeError("VALIDATION_ERROR")
        if request.idempotency_request_hash is not None and not _is_hash(
            request.idempotency_request_hash
        ):
            raise BatchRuntimeError("VALIDATION_ERROR")
        if any(
            item.source_item_id is not None and not 1 <= len(item.source_item_id) <= 64
            for item in request.items
        ):
            raise BatchRuntimeError("VALIDATION_ERROR")
        if len({item.slug.casefold() for item in request.items}) != len(request.items):
            raise BatchRuntimeError("VALIDATION_ERROR")
        idempotency_hash = _hash(request.idempotency_key)
        now = _timestamp(_utc(self._now()))
        batch_id = secrets.token_urlsafe(18)
        item_rows = [
            (
                secrets.token_urlsafe(18),
                batch_id,
                position,
                item.slug,
                item.ref,
                request.selection_hash,
                item.commit_sha,
                item.policy_json(),
                "queued",
                request.execution_budget_seconds,
                item.source_item_id,
                now,
                now,
            )
            for position, item in enumerate(request.items)
        ]
        try:
            with self._database.connection() as connection:
                connection.execute("BEGIN IMMEDIATE")
                receipt = connection.execute(
                    "SELECT * FROM analysis_batch_idempotency_receipts "
                    "WHERE idempotency_key_hash = ?",
                    (idempotency_hash,),
                ).fetchone()
                if receipt is not None:
                    if (
                        request.idempotency_request_hash is None
                        or str(receipt["request_hash"]) != request.idempotency_request_hash
                    ):
                        connection.execute("ROLLBACK")
                        raise BatchRuntimeError("ANALYSIS_IDEMPOTENCY_CONFLICT")
                    receipt_batch_id = str(receipt["batch_id"])
                    receipt_batch = connection.execute(
                        "SELECT batch_id FROM analysis_batches WHERE batch_id = ?",
                        (receipt_batch_id,),
                    ).fetchone()
                    if receipt_batch is None:
                        connection.execute("ROLLBACK")
                        raise BatchRuntimeError("ANALYSIS_IDEMPOTENCY_CONFLICT")
                    connection.execute("COMMIT")
                    return self.get_batch(receipt_batch_id), False
                existing = connection.execute(
                    "SELECT * FROM analysis_batches WHERE idempotency_key_hash = ?",
                    (idempotency_hash,),
                ).fetchone()
                if existing is not None:
                    existing_items = connection.execute(
                        "SELECT * FROM analysis_batch_items WHERE batch_id = ? ORDER BY position",
                        (str(existing["batch_id"]),),
                    ).fetchall()
                    if not _request_matches_existing(request, existing, existing_items):
                        connection.execute("ROLLBACK")
                        raise BatchRuntimeError("ANALYSIS_IDEMPOTENCY_CONFLICT")
                    if request.idempotency_request_hash is not None:
                        self._bind_reanalysis_receipt_locked(
                            connection,
                            idempotency_hash=idempotency_hash,
                            request_hash=request.idempotency_request_hash,
                            batch_id=str(existing["batch_id"]),
                            created_at=now,
                        )
                    connection.execute("COMMIT")
                    return self.get_batch(str(existing["batch_id"])), False
                if request.source_batch_id is not None:
                    source_batch = connection.execute(
                        "SELECT * FROM analysis_batches WHERE batch_id = ?",
                        (request.source_batch_id,),
                    ).fetchone()
                    if source_batch is None:
                        connection.execute("ROLLBACK")
                        raise BatchRuntimeError("NOT_FOUND")
                    if (
                        str(source_batch["state"]) not in {"failed", "completed_with_errors"}
                        or request.analysis_round != int(source_batch["analysis_round"]) + 1
                    ):
                        connection.execute("ROLLBACK")
                        raise BatchRuntimeError("ANALYSIS_SOURCE_STATE_CHANGED")
                    source_ids = tuple(item.source_item_id for item in request.items)
                    if any(item_id is None for item_id in source_ids):
                        connection.execute("ROLLBACK")
                        raise BatchRuntimeError("ANALYSIS_REANALYZE_ITEM_INVALID")
                    placeholders = ",".join("?" for _ in source_ids)
                    source_rows = connection.execute(
                        f"SELECT * FROM analysis_batch_items WHERE batch_id = ? "
                        f"AND item_id IN ({placeholders})",
                        (request.source_batch_id, *source_ids),
                    ).fetchall()
                    source_by_id = {str(row["item_id"]): row for row in source_rows}
                    if len(source_by_id) != len(request.items):
                        connection.execute("ROLLBACK")
                        raise BatchRuntimeError("ANALYSIS_REANALYZE_ITEM_INVALID")
                    for item in request.items:
                        source_row = source_by_id[str(item.source_item_id)]
                        retryable, _blocker = _retry_eligibility(
                            source_row,
                            request.maximum_generation_attempts,
                            execution_budget_seconds=request.execution_budget_seconds,
                            batch_state=str(source_batch["state"]),
                        )
                        source_input = _input_from_row(source_row)
                        if (
                            str(source_row["state"]) not in FAILED_ITEM_STATES
                            or retryable
                            or source_input.slug != item.slug
                            or source_input.ref != item.ref
                            or source_input.include != item.include
                            or source_input.exclude != item.exclude
                            or source_input.commit_sha != item.commit_sha
                        ):
                            connection.execute("ROLLBACK")
                            raise BatchRuntimeError("ANALYSIS_SOURCE_STATE_CHANGED")
                    # A successor request has a durable identity in addition
                    # to its transport idempotency key.  This closes the
                    # response-loss/two-tab gap where another key could create
                    # the same round after the first successor became terminal.
                    successor = connection.execute(
                        """
                        SELECT * FROM analysis_batches
                        WHERE source_batch_id = ? AND analysis_round = ?
                          AND selection_hash = ?
                        """,
                        (
                            request.source_batch_id,
                            request.analysis_round,
                            request.selection_hash,
                        ),
                    ).fetchone()
                    if successor is not None:
                        successor_items = connection.execute(
                            "SELECT * FROM analysis_batch_items "
                            "WHERE batch_id = ? ORDER BY position",
                            (str(successor["batch_id"]),),
                        ).fetchall()
                        if not _request_matches_existing(request, successor, successor_items):
                            connection.execute("ROLLBACK")
                            raise BatchRuntimeError("ANALYSIS_SUCCESSOR_CONFLICT")
                        if request.idempotency_request_hash is not None:
                            self._bind_reanalysis_receipt_locked(
                                connection,
                                idempotency_hash=idempotency_hash,
                                request_hash=request.idempotency_request_hash,
                                batch_id=str(successor["batch_id"]),
                                created_at=now,
                            )
                        connection.execute("COMMIT")
                        return self.get_batch(str(successor["batch_id"])), False
                    if any(
                        _optional_text(row["successor_batch_id"]) is not None for row in source_rows
                    ):
                        connection.execute("ROLLBACK")
                        raise BatchRuntimeError("ANALYSIS_SUCCESSOR_CONFLICT")
                    overlapping = connection.execute(
                        f"SELECT item_id FROM analysis_batch_items "
                        f"WHERE source_item_id IN ({placeholders}) LIMIT 1",
                        source_ids,
                    ).fetchone()
                    if overlapping is not None:
                        connection.execute("ROLLBACK")
                        raise BatchRuntimeError("ANALYSIS_SUCCESSOR_CONFLICT")
                active = connection.execute(
                    """
                    SELECT batch_id FROM analysis_batches
                    WHERE owner_scope = 'singleton'
                      AND state IN ('queued', 'running', 'paused', 'cancelling')
                    """
                ).fetchone()
                if active is not None:
                    connection.execute("ROLLBACK")
                    raise BatchRuntimeError("ANALYSIS_BATCH_ACTIVE")
                connection.execute(
                    """
                    INSERT INTO analysis_batches(
                      batch_id, owner_scope, plan_id, selection_hash,
                      idempotency_key_hash, selected_credential_id, analysis_model_pair_json, state,
                      maximum_generation_attempts, source_batch_id, analysis_round,
                      created_at, updated_at
                    ) VALUES (?, 'singleton', ?, ?, ?, ?, ?, 'queued', ?, ?, ?, ?, ?)
                    """,
                    (
                        batch_id,
                        request.plan_id,
                        request.selection_hash,
                        idempotency_hash,
                        None,
                        (
                            _safe_json(request.analysis_model_pair)
                            if request.analysis_model_pair is not None
                            else None
                        ),
                        request.maximum_generation_attempts,
                        request.source_batch_id,
                        request.analysis_round,
                        now,
                        now,
                    ),
                )
                connection.executemany(
                    """
                    INSERT INTO analysis_batch_items(
                      item_id, batch_id, position, repository_slug, requested_ref,
                      selection_hash, resolved_commit_sha, selection_json, state,
                      execution_budget_seconds, source_item_id, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    item_rows,
                )
                if request.source_batch_id is not None:
                    changed = connection.execute(
                        f"UPDATE analysis_batch_items SET successor_batch_id = ? "
                        f"WHERE batch_id = ? AND item_id IN ({placeholders}) "
                        "AND successor_batch_id IS NULL",
                        (batch_id, request.source_batch_id, *source_ids),
                    ).rowcount
                    if changed != len(source_ids):
                        connection.execute("ROLLBACK")
                        raise BatchRuntimeError("ANALYSIS_SUCCESSOR_CONFLICT")
                if request.idempotency_request_hash is not None:
                    self._bind_reanalysis_receipt_locked(
                        connection,
                        idempotency_hash=idempotency_hash,
                        request_hash=request.idempotency_request_hash,
                        batch_id=batch_id,
                        created_at=now,
                    )
                self._event_locked(
                    connection,
                    batch_id=batch_id,
                    item_id=None,
                    event_type="batch_created",
                    payload={"state": "queued", "items": len(item_rows)},
                    occurred_at=now,
                )
                connection.execute("COMMIT")
        except BatchRuntimeError:
            raise
        except sqlite3.Error as exc:
            raise RuntimeDatabaseError("runtime_analysis_batch_failed") from exc
        return self.get_batch(batch_id), True

    def get_batch(
        self,
        batch_id: str,
        *,
        execution_budget_seconds: int | None = None,
        maximum_generation_attempts: int | None = None,
    ) -> BatchSnapshot:
        expired = False
        with self._database.connection() as connection:
            batch = connection.execute(
                "SELECT * FROM analysis_batches WHERE batch_id = ?", (batch_id,)
            ).fetchone()
            if batch is None:
                raise BatchRuntimeError("NOT_FOUND")
            expires_at = _parse_optional_timestamp(batch["expires_at"])
            expired = (
                str(batch["state"]) in TERMINAL_BATCH_STATES
                and expires_at is not None
                and expires_at <= _utc(self._now())
            )
            if expired:
                rows = []
            else:
                rows = connection.execute(
                    """
                    SELECT item.*,
                           (item.successor_batch_id IS NOT NULL OR EXISTS(
                             SELECT 1 FROM analysis_batch_items AS successor
                             WHERE successor.source_item_id = item.item_id
                           )) AS has_successor
                    FROM analysis_batch_items AS item
                    WHERE item.batch_id = ?
                    ORDER BY item.position
                    """,
                    (batch_id,),
                ).fetchall()
        if expired:
            self.cleanup_expired()
            raise BatchRuntimeError("NOT_FOUND")
        return _snapshot(
            batch,
            rows,
            now=_timestamp(_utc(self._now())),
            execution_budget_seconds=execution_budget_seconds,
            maximum_generation_attempts=maximum_generation_attempts,
        )

    def active_batch(self) -> BatchSnapshot:
        with self._database.connection() as connection:
            row = connection.execute(
                """
                SELECT batch_id FROM analysis_batches
                WHERE owner_scope = 'singleton'
                  AND state IN ('queued', 'running', 'paused', 'cancelling')
                ORDER BY created_at DESC LIMIT 1
                """
            ).fetchone()
        if row is None:
            raise BatchRuntimeError("NOT_FOUND")
        return self.get_batch(str(row["batch_id"]))

    def idempotent_create(
        self,
        *,
        idempotency_key: str,
        plan_id: str,
        selections: Sequence[RepositorySelection],
    ) -> BatchSnapshot | None:
        """Recover an accepted create before consulting the in-memory plan cache."""

        if not idempotency_key or len(idempotency_key) > 512:
            raise BatchRuntimeError("VALIDATION_ERROR")
        with self._database.connection() as connection:
            receipt = connection.execute(
                "SELECT 1 FROM analysis_batch_idempotency_receipts WHERE idempotency_key_hash = ?",
                (_hash(idempotency_key),),
            ).fetchone()
            if receipt is not None:
                raise BatchRuntimeError("ANALYSIS_IDEMPOTENCY_CONFLICT")
            batch = connection.execute(
                "SELECT * FROM analysis_batches WHERE idempotency_key_hash = ?",
                (_hash(idempotency_key),),
            ).fetchone()
            if batch is None:
                return None
            rows = connection.execute(
                "SELECT * FROM analysis_batch_items WHERE batch_id = ? ORDER BY position",
                (str(batch["batch_id"]),),
            ).fetchall()
        matches = (
            str(batch["plan_id"]) == plan_id
            and batch["source_batch_id"] is None
            and len(rows) == len(selections)
        )
        if matches:
            for row, selection in zip(rows, selections, strict=True):
                persisted = _input_from_row(row)
                if (
                    persisted.slug != selection.slug
                    or persisted.ref != selection.ref
                    or persisted.include != selection.include
                    or persisted.exclude != selection.exclude
                ):
                    matches = False
                    break
        if not matches:
            raise BatchRuntimeError("ANALYSIS_IDEMPOTENCY_CONFLICT")
        return self.get_batch(str(batch["batch_id"]))

    def idempotent_reanalysis(
        self,
        *,
        idempotency_key: str,
        source_batch_id: str,
        item_ids: Sequence[str],
        model_selection: str,
        confirm_model_change: bool,
        expected_selection_generation: int | None,
    ) -> BatchSnapshot | None:
        """Recover an accepted successor before re-reading mutable model state."""

        if not idempotency_key or len(idempotency_key) > 512:
            raise BatchRuntimeError("VALIDATION_ERROR")
        request_hash = reanalysis_request_hash(
            source_batch_id=source_batch_id,
            item_ids=item_ids,
            model_selection=model_selection,
            confirm_model_change=confirm_model_change,
            expected_selection_generation=expected_selection_generation,
        )
        with self._database.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            receipt = connection.execute(
                "SELECT * FROM analysis_batch_idempotency_receipts WHERE idempotency_key_hash = ?",
                (_hash(idempotency_key),),
            ).fetchone()
            if receipt is not None:
                if str(receipt["request_hash"]) != request_hash:
                    connection.execute("ROLLBACK")
                    raise BatchRuntimeError("ANALYSIS_IDEMPOTENCY_CONFLICT")
                batch_id = str(receipt["batch_id"])
                connection.execute("COMMIT")
                return self.get_batch(batch_id)
            batch = connection.execute(
                "SELECT * FROM analysis_batches WHERE idempotency_key_hash = ?",
                (_hash(idempotency_key),),
            ).fetchone()
            if batch is None:
                source = connection.execute(
                    "SELECT analysis_round FROM analysis_batches WHERE batch_id = ?",
                    (source_batch_id,),
                ).fetchone()
                if source is None:
                    connection.execute("COMMIT")
                    return None
                expected_round = int(source["analysis_round"]) + 1
                expected_plan = reanalysis_plan_id(
                    source_batch_id=source_batch_id,
                    analysis_round=expected_round,
                    model_selection=model_selection,
                    confirm_model_change=confirm_model_change,
                    expected_selection_generation=expected_selection_generation,
                )
                candidates = connection.execute(
                    "SELECT * FROM analysis_batches WHERE source_batch_id = ? "
                    "AND analysis_round = ? AND plan_id = ?",
                    (source_batch_id, expected_round, expected_plan),
                ).fetchall()
                for candidate in candidates:
                    candidate_rows = connection.execute(
                        "SELECT source_item_id FROM analysis_batch_items "
                        "WHERE batch_id = ? ORDER BY position",
                        (str(candidate["batch_id"]),),
                    ).fetchall()
                    candidate_ids = tuple(
                        _optional_text(row["source_item_id"]) for row in candidate_rows
                    )
                    if set(candidate_ids) == set(item_ids) and len(candidate_ids) == len(item_ids):
                        batch = candidate
                        break
                if batch is None:
                    connection.execute("COMMIT")
                    return None
            rows = connection.execute(
                "SELECT source_item_id FROM analysis_batch_items "
                "WHERE batch_id = ? ORDER BY position",
                (str(batch["batch_id"]),),
            ).fetchall()
            expected_plan = reanalysis_plan_id(
                source_batch_id=source_batch_id,
                analysis_round=int(batch["analysis_round"]),
                model_selection=model_selection,
                confirm_model_change=confirm_model_change,
                expected_selection_generation=expected_selection_generation,
            )
            persisted_ids = tuple(_optional_text(row["source_item_id"]) for row in rows)
            if (
                _optional_text(batch["source_batch_id"]) != source_batch_id
                or str(batch["plan_id"]) != expected_plan
                or set(persisted_ids) != set(item_ids)
                or len(persisted_ids) != len(item_ids)
            ):
                connection.execute("ROLLBACK")
                raise BatchRuntimeError("ANALYSIS_IDEMPOTENCY_CONFLICT")
            batch_id = str(batch["batch_id"])
            self._bind_reanalysis_receipt_locked(
                connection,
                idempotency_hash=_hash(idempotency_key),
                request_hash=request_hash,
                batch_id=batch_id,
                created_at=_timestamp(_utc(self._now())),
            )
            connection.execute("COMMIT")
        return self.get_batch(batch_id)

    def reanalysis_source(
        self,
        batch_id: str,
        *,
        item_ids: Sequence[str],
        execution_budget_seconds: int | None = None,
        maximum_generation_attempts: int | None = None,
    ) -> BatchReanalysisSource:
        """Return validated failed-item inputs for an explicit successor round."""

        requested = tuple(dict.fromkeys(item_ids))
        if not requested or len(requested) != len(item_ids) or len(requested) > 50:
            raise BatchRuntimeError("ANALYSIS_REANALYZE_ITEM_INVALID")
        with self._database.connection() as connection:
            batch = connection.execute(
                "SELECT * FROM analysis_batches WHERE batch_id = ?", (batch_id,)
            ).fetchone()
            if batch is None:
                raise BatchRuntimeError("NOT_FOUND")
            if str(batch["state"]) not in {"failed", "completed_with_errors"}:
                raise BatchRuntimeError("ANALYSIS_SOURCE_BATCH_NOT_TERMINAL")
            placeholders = ",".join("?" for _ in requested)
            rows = connection.execute(
                f"""
                SELECT item.*,
                       (item.successor_batch_id IS NOT NULL OR EXISTS(
                         SELECT 1 FROM analysis_batch_items AS successor
                         WHERE successor.source_item_id = item.item_id
                       )) AS has_successor
                FROM analysis_batch_items AS item
                WHERE batch_id = ? AND item_id IN ({placeholders})
                ORDER BY position
                """,
                (batch_id, *requested),
            ).fetchall()
        if len(rows) != len(requested):
            raise BatchRuntimeError("ANALYSIS_REANALYZE_ITEM_INVALID")
        maximum_attempts = (
            int(batch["maximum_generation_attempts"])
            if maximum_generation_attempts is None
            else maximum_generation_attempts
        )
        items: list[BatchItemInput] = []
        for row in rows:
            retryable, blocker = _retry_eligibility(
                row,
                maximum_attempts,
                execution_budget_seconds=execution_budget_seconds,
                batch_state=str(batch["state"]),
            )
            if (
                str(row["state"]) not in FAILED_ITEM_STATES
                or retryable
                or blocker == "SUCCESSOR_EXISTS"
            ):
                raise BatchRuntimeError("ANALYSIS_REANALYZE_NOT_AVAILABLE")
            source = _input_from_row(row)
            items.append(
                BatchItemInput(
                    slug=source.slug,
                    ref=source.ref,
                    include=source.include,
                    exclude=source.exclude,
                    commit_sha=source.commit_sha,
                    source_item_id=str(row["item_id"]),
                )
            )
        return BatchReanalysisSource(
            source_batch_id=batch_id,
            analysis_round=int(batch["analysis_round"]) + 1,
            items=tuple(items),
            analysis_model_pair=_json_object_optional(batch["analysis_model_pair_json"]),
        )

    def transition_batch(self, batch_id: str, *, action: str) -> BatchSnapshot:
        """Apply idempotent owner actions without changing terminal results."""

        targets = {
            "pause": (frozenset({"running"}), "paused"),
            "resume": (frozenset({"paused"}), "running"),
            "cancel": (frozenset({"queued", "running", "paused", "cancelling"}), "cancelling"),
        }
        if action not in targets:
            raise BatchRuntimeError("VALIDATION_ERROR")
        source_states, target = targets[action]
        now = _timestamp(_utc(self._now()))
        try:
            with self._database.connection() as connection:
                connection.execute("BEGIN IMMEDIATE")
                row = connection.execute(
                    "SELECT state, analysis_model_pair_json FROM analysis_batches "
                    "WHERE batch_id = ?",
                    (batch_id,),
                ).fetchone()
                if row is None:
                    connection.execute("ROLLBACK")
                    raise BatchRuntimeError("NOT_FOUND")
                state = str(row["state"])
                if state in TERMINAL_BATCH_STATES:
                    connection.execute("COMMIT")
                    return self.get_batch(batch_id)
                if state not in source_states and state != target:
                    connection.execute("ROLLBACK")
                    raise BatchRuntimeError("VALIDATION_ERROR")
                if state != target:
                    connection.execute(
                        "UPDATE analysis_batches SET state = ?, updated_at = ? WHERE batch_id = ?",
                        (target, now, batch_id),
                    )
                    if target == "cancelling":
                        connection.execute(
                            """
                            UPDATE analysis_batch_items SET state = 'cancelled', updated_at = ?
                            WHERE batch_id = ? AND state IN ('queued', 'waiting_rate_limit',
                              'waiting_reconnection', 'needs_retry_confirmation')
                            """,
                            (now, batch_id),
                        )
                    self._event_locked(
                        connection,
                        batch_id=batch_id,
                        item_id=None,
                        event_type=f"batch_{action}",
                        payload={"state": target},
                        occurred_at=now,
                    )
                self._finish_batch_locked(connection, batch_id, now)
                connection.execute("COMMIT")
        except BatchRuntimeError:
            raise
        except sqlite3.Error as exc:
            raise RuntimeDatabaseError("runtime_analysis_batch_failed") from exc
        return self.get_batch(batch_id)

    def retry_items(
        self,
        batch_id: str,
        *,
        execution_budget_seconds: int | None = None,
        maximum_generation_attempts: int | None = None,
    ) -> BatchSnapshot:
        """Explicitly requeue terminal items under an optional current policy."""

        if execution_budget_seconds is not None and not 1 <= execution_budget_seconds <= 7200:
            raise BatchRuntimeError("VALIDATION_ERROR")
        if maximum_generation_attempts is not None and not 1 <= maximum_generation_attempts <= 10:
            raise BatchRuntimeError("VALIDATION_ERROR")

        now = _timestamp(_utc(self._now()))
        try:
            with self._database.connection() as connection:
                connection.execute("BEGIN IMMEDIATE")
                batch = connection.execute(
                    "SELECT state, maximum_generation_attempts "
                    "FROM analysis_batches WHERE batch_id = ?",
                    (batch_id,),
                ).fetchone()
                if batch is None:
                    connection.execute("ROLLBACK")
                    raise BatchRuntimeError("NOT_FOUND")
                if str(batch["state"]) not in {"failed", "completed_with_errors"}:
                    connection.execute("ROLLBACK")
                    raise BatchRuntimeError("ANALYSIS_RETRY_NOT_AVAILABLE")
                other_active = connection.execute(
                    """
                    SELECT batch_id FROM analysis_batches
                    WHERE batch_id <> ? AND owner_scope = 'singleton'
                      AND state IN ('queued', 'running', 'paused', 'cancelling')
                    """,
                    (batch_id,),
                ).fetchone()
                if other_active is not None:
                    connection.execute("ROLLBACK")
                    raise BatchRuntimeError("ANALYSIS_BATCH_ACTIVE")
                effective_attempts = (
                    int(batch["maximum_generation_attempts"])
                    if maximum_generation_attempts is None
                    else maximum_generation_attempts
                )
                candidates = connection.execute(
                    """
                SELECT item.*,
                           (item.successor_batch_id IS NOT NULL OR EXISTS(
                             SELECT 1 FROM analysis_batch_items AS successor
                             WHERE successor.source_item_id = item.item_id
                           )) AS has_successor
                    FROM analysis_batch_items AS item
                    WHERE item.batch_id = ?
                      AND item.state IN (
                        'needs_retry_confirmation', 'failed', 'waiting_reconnection'
                      )
                    """,
                    (batch_id,),
                ).fetchall()
                changed = connection.execute(
                    """
                    UPDATE analysis_batch_items
                    SET state = 'queued', error_code = NULL, error_reason = NULL,
                        retry_at = NULL,
                        lease_id = NULL, execution_started_at = NULL,
                        failure_stage = NULL,
                        execution_budget_seconds = COALESCE(?, execution_budget_seconds),
                        updated_at = ?
                    WHERE batch_id = ?
                      AND state IN ('needs_retry_confirmation', 'failed', 'waiting_reconnection')
                      AND generation_attempt_count < ?
                      AND execution_elapsed_seconds < COALESCE(?, execution_budget_seconds)
                      AND NOT EXISTS (
                        SELECT 1 FROM analysis_batch_items AS successor
                        WHERE successor.source_item_id = analysis_batch_items.item_id
                      )
                      AND successor_batch_id IS NULL
                    """,
                    (
                        execution_budget_seconds,
                        now,
                        batch_id,
                        effective_attempts,
                        execution_budget_seconds,
                    ),
                ).rowcount
                if not changed:
                    connection.execute("ROLLBACK")
                    if any(bool(row["has_successor"]) for row in candidates):
                        raise BatchRuntimeError("ANALYSIS_SUCCESSOR_CONFLICT")
                    if any(
                        int(row["generation_attempt_count"]) >= effective_attempts
                        for row in candidates
                    ):
                        raise BatchRuntimeError("ANALYSIS_GENERATION_ATTEMPTS_EXHAUSTED")
                    if any(
                        int(row["execution_elapsed_seconds"])
                        >= (
                            int(row["execution_budget_seconds"])
                            if execution_budget_seconds is None
                            else execution_budget_seconds
                        )
                        for row in candidates
                    ):
                        raise BatchRuntimeError("ANALYSIS_EXECUTION_BUDGET_EXHAUSTED")
                    raise BatchRuntimeError("ANALYSIS_RETRY_NOT_AVAILABLE")
                connection.execute(
                    """
                    UPDATE analysis_batches SET state = 'running', error_code = NULL,
                      maximum_generation_attempts = ?,
                      completed_at = NULL, expires_at = NULL, updated_at = ?
                    WHERE batch_id = ?
                    """,
                    (effective_attempts, now, batch_id),
                )
                self._event_locked(
                    connection,
                    batch_id=batch_id,
                    item_id=None,
                    event_type="batch_retry",
                    payload={"items": int(changed), "state": "running"},
                    occurred_at=now,
                )
                connection.execute("COMMIT")
        except BatchRuntimeError:
            raise
        except sqlite3.Error as exc:
            raise RuntimeDatabaseError("runtime_analysis_batch_failed") from exc
        return self.get_batch(batch_id)

    def claim_next_item(self, batch_id: str) -> ClaimedBatchItem | None:
        """Lease one schedulable item; paused/cancelling work is never claimed."""

        now_instant = _utc(self._now())
        now = _timestamp(now_instant)
        lease_id = secrets.token_urlsafe(18)
        try:
            with self._database.connection() as connection:
                connection.execute("BEGIN IMMEDIATE")
                batch = connection.execute(
                    "SELECT state, analysis_model_pair_json, maximum_generation_attempts "
                    "FROM analysis_batches WHERE batch_id = ?",
                    (batch_id,),
                ).fetchone()
                if batch is None:
                    connection.execute("ROLLBACK")
                    raise BatchRuntimeError("NOT_FOUND")
                state = str(batch["state"])
                if state == "queued":
                    connection.execute(
                        """
                        UPDATE analysis_batches
                        SET state = 'running', started_at = COALESCE(started_at, ?),
                          updated_at = ? WHERE batch_id = ?
                        """,
                        (now, now, batch_id),
                    )
                elif state != "running":
                    connection.execute("COMMIT")
                    return None
                exhausted = connection.execute(
                    """
                    SELECT * FROM analysis_batch_items
                    WHERE batch_id = ? AND lease_id IS NULL
                      AND state IN ('queued', 'waiting_rate_limit')
                      AND (
                        execution_elapsed_seconds >= execution_budget_seconds
                        OR generation_attempt_count >= ?
                      )
                    ORDER BY position
                    """,
                    (batch_id, int(batch["maximum_generation_attempts"])),
                ).fetchall()
                for exhausted_row in exhausted:
                    attempts_exhausted = int(exhausted_row["generation_attempt_count"]) >= int(
                        batch["maximum_generation_attempts"]
                    )
                    code = (
                        "ANALYSIS_GENERATION_ATTEMPTS_EXHAUSTED"
                        if attempts_exhausted
                        else "ANALYSIS_TIMEOUT"
                    )
                    connection.execute(
                        """
                        UPDATE analysis_batch_items
                        SET state = 'failed', error_code = ?, failure_stage = ?,
                          execution_started_at = NULL, retry_at = NULL, updated_at = ?
                        WHERE item_id = ?
                        """,
                        (
                            code,
                            _failure_stage(exhausted_row),
                            now,
                            str(exhausted_row["item_id"]),
                        ),
                    )
                    self._event_locked(
                        connection,
                        batch_id=batch_id,
                        item_id=str(exhausted_row["item_id"]),
                        event_type="item_terminal",
                        payload={"state": "failed", "error_code": code},
                        occurred_at=now,
                    )
                row = connection.execute(
                    """
                    SELECT * FROM analysis_batch_items
                    WHERE batch_id = ? AND lease_id IS NULL
                      AND (state = 'queued' OR (state = 'waiting_rate_limit'
                        AND (retry_at IS NULL OR retry_at <= ?)))
                    ORDER BY position LIMIT 1
                    """,
                    (batch_id, now),
                ).fetchone()
                if row is None:
                    self._finish_batch_locked(connection, batch_id, now)
                    connection.execute("COMMIT")
                    return None
                changed = connection.execute(
                    """
                    UPDATE analysis_batch_items
                    SET lease_id = ?, state = 'resolving_commit',
                      execution_started_at = COALESCE(execution_started_at, ?), updated_at = ?
                    WHERE item_id = ? AND lease_id IS NULL
                    """,
                    (lease_id, now, now, str(row["item_id"])),
                ).rowcount
                if changed != 1:
                    connection.execute("ROLLBACK")
                    return None
                self._event_locked(
                    connection,
                    batch_id=batch_id,
                    item_id=str(row["item_id"]),
                    event_type="item_stage",
                    payload={"state": "resolving_commit"},
                    occurred_at=now,
                )
                connection.execute("COMMIT")
        except BatchRuntimeError:
            raise
        except sqlite3.Error as exc:
            raise RuntimeDatabaseError("runtime_analysis_batch_failed") from exc
        return ClaimedBatchItem(
            batch_id=batch_id,
            item_id=str(row["item_id"]),
            lease_id=lease_id,
            selection_hash=str(row["selection_hash"]),
            input=_input_from_row(row),
            execution_elapsed_seconds=int(row["execution_elapsed_seconds"]),
            execution_budget_seconds=max(
                0,
                int(row["execution_budget_seconds"]) - int(row["execution_elapsed_seconds"]),
            ),
            generation_attempt_count=int(row["generation_attempt_count"]),
            maximum_generation_attempts=int(batch["maximum_generation_attempts"]),
            analysis_model_pair=_json_object_optional(batch["analysis_model_pair_json"]),
        )

    def advance_item(
        self,
        claimed: ClaimedBatchItem,
        *,
        state: str,
        error_code: str | None = None,
        error_reason: str | None = None,
        retry_at: datetime | None = None,
    ) -> None:
        if state not in ITEM_ACTIVE_STAGES | {"waiting_rate_limit", "waiting_reconnection"}:
            raise BatchRuntimeError("VALIDATION_ERROR")
        self._update_item(
            claimed,
            state=state,
            error_code=error_code,
            error_reason=error_reason,
            retry_at=retry_at,
            result=None,
            terminal=False,
        )

    def exclude_item_wait(self, claimed: ClaimedBatchItem, *, seconds: float) -> None:
        """Move the active clock past a semaphore wait without spending its budget."""

        if isinstance(seconds, bool) or seconds < 0:
            raise BatchRuntimeError("VALIDATION_ERROR")
        if seconds == 0:
            return
        try:
            with self._database.connection() as connection:
                connection.execute("BEGIN IMMEDIATE")
                row = connection.execute(
                    """
                    SELECT execution_started_at FROM analysis_batch_items
                    WHERE item_id = ? AND batch_id = ? AND lease_id = ?
                    """,
                    (claimed.item_id, claimed.batch_id, claimed.lease_id),
                ).fetchone()
                if row is None or row["execution_started_at"] is None:
                    connection.execute("ROLLBACK")
                    raise BatchRuntimeError("ANALYSIS_LEASE_LOST")
                try:
                    started = datetime.fromisoformat(str(row["execution_started_at"]))
                except ValueError:
                    connection.execute("ROLLBACK")
                    raise BatchRuntimeError("VALIDATION_ERROR") from None
                shifted = _timestamp(started + timedelta(seconds=float(seconds)))
                changed = connection.execute(
                    """
                    UPDATE analysis_batch_items SET execution_started_at = ?, updated_at = ?
                    WHERE item_id = ? AND batch_id = ? AND lease_id = ?
                    """,
                    (
                        shifted,
                        _timestamp(_utc(self._now())),
                        claimed.item_id,
                        claimed.batch_id,
                        claimed.lease_id,
                    ),
                ).rowcount
                if changed != 1:
                    connection.execute("ROLLBACK")
                    raise BatchRuntimeError("ANALYSIS_LEASE_LOST")
                connection.execute("COMMIT")
        except BatchRuntimeError:
            raise
        except sqlite3.Error as exc:
            raise RuntimeDatabaseError("runtime_analysis_batch_failed") from exc

    def complete_item(self, claimed: ClaimedBatchItem, *, result: dict[str, object]) -> None:
        self._update_item(
            claimed,
            state="complete",
            error_code=None,
            error_reason=None,
            retry_at=None,
            result=result,
            terminal=True,
        )

    def fail_item(
        self,
        claimed: ClaimedBatchItem,
        *,
        code: str,
        reason: str | None = None,
        retry_confirmation: bool = False,
    ) -> None:
        self._update_item(
            claimed,
            state="needs_retry_confirmation" if retry_confirmation else "failed",
            error_code=code,
            error_reason=reason,
            retry_at=None,
            result=None,
            terminal=True,
        )

    def cancel_item(self, claimed: ClaimedBatchItem) -> None:
        self._update_item(
            claimed,
            state="cancelled",
            error_code=None,
            error_reason=None,
            retry_at=None,
            result=None,
            terminal=True,
        )

    def events_after(
        self, batch_id: str, *, after_event_id: int | None, limit: int = EVENT_REPLAY_LIMIT
    ) -> tuple[BatchEvent, ...]:
        if not 1 <= limit <= EVENT_REPLAY_LIMIT:
            raise BatchRuntimeError("VALIDATION_ERROR")
        cursor = after_event_id or 0
        with self._database.connection() as connection:
            rows = connection.execute(
                """
                SELECT event_id, batch_id, item_id, event_type, payload_json, occurred_at
                FROM analysis_batch_events WHERE batch_id = ? AND event_id > ?
                ORDER BY event_id LIMIT ?
                """,
                (batch_id, cursor, limit),
            ).fetchall()
        return tuple(_event_from_row(row) for row in rows)

    def next_rate_retry_at(self, batch_id: str) -> datetime | None:
        """Return the earliest durable rate retry without polling GitHub.

        The worker uses this value to park until admission can be retried.  A
        reconnect wait deliberately returns ``None``: it needs an owner action,
        never an automatic credential retry.
        """

        with self._database.connection() as connection:
            row = connection.execute(
                """
                SELECT retry_at FROM analysis_batch_items
                WHERE batch_id = ? AND state = 'waiting_rate_limit'
                  AND retry_at IS NOT NULL
                ORDER BY retry_at LIMIT 1
                """,
                (batch_id,),
            ).fetchone()
        if row is None:
            return None
        try:
            parsed = datetime.fromisoformat(str(row["retry_at"]))
        except ValueError as exc:
            raise BatchRuntimeError("VALIDATION_ERROR") from exc
        if parsed.tzinfo is None:
            raise BatchRuntimeError("VALIDATION_ERROR")
        return parsed.astimezone(UTC)

    def recover_after_restart(self) -> tuple[str, ...]:
        """Make non-generation work safe to retry and preserve generation consent."""

        now = _timestamp(_utc(self._now()))
        recovered: list[str] = []
        try:
            with self._database.connection() as connection:
                connection.execute("BEGIN IMMEDIATE")
                rows = connection.execute(
                    """
                    SELECT item_id, batch_id, state, execution_started_at,
                      execution_elapsed_seconds FROM analysis_batch_items
                    WHERE lease_id IS NOT NULL OR state IN (
                      'resolving_commit', 'fetching_source', 'filtering', 'indexing',
                      'embedding', 'generating', 'validating', 'cleaning_up'
                    )
                    """
                ).fetchall()
                affected_batches: set[str] = set()
                for row in rows:
                    state = str(row["state"])
                    elapsed = _elapsed_since(row["execution_started_at"], now)
                    batch_state = connection.execute(
                        "SELECT state FROM analysis_batches WHERE batch_id = ?",
                        (str(row["batch_id"]),),
                    ).fetchone()
                    cancelling = (
                        batch_state is not None and str(batch_state["state"]) == "cancelling"
                    )
                    next_state = (
                        "cancelled"
                        if cancelling
                        else "needs_retry_confirmation"
                        if state
                        in {
                            "generating",
                            "validating",
                        }
                        else "queued"
                    )
                    connection.execute(
                        """
                        UPDATE analysis_batch_items
                        SET state = ?, resume_state = ?, lease_id = NULL,
                          execution_started_at = NULL,
                          execution_elapsed_seconds = execution_elapsed_seconds + ?,
                          failure_stage = CASE
                            WHEN ? = 'needs_retry_confirmation' THEN ?
                            ELSE failure_stage
                          END,
                          updated_at = ?
                        WHERE item_id = ?
                        """,
                        (
                            next_state,
                            state,
                            elapsed,
                            next_state,
                            state if state in ITEM_ACTIVE_STAGES else None,
                            now,
                            str(row["item_id"]),
                        ),
                    )
                    self._event_locked(
                        connection,
                        batch_id=str(row["batch_id"]),
                        item_id=str(row["item_id"]),
                        event_type="item_recovered",
                        payload={"state": next_state},
                        occurred_at=now,
                    )
                    recovered.append(str(row["item_id"]))
                    affected_batches.add(str(row["batch_id"]))
                for affected_batch_id in affected_batches:
                    self._finish_batch_locked(connection, affected_batch_id, now)
                connection.execute("COMMIT")
        except sqlite3.Error as exc:
            raise RuntimeDatabaseError("runtime_analysis_batch_failed") from exc
        return tuple(recovered)

    def put_cache(
        self,
        *,
        cache_key: str,
        cache_kind: str,
        derived_index_key: str,
        metadata: dict[str, object],
        payload: dict[str, object],
        ttl: timedelta = BATCH_TTL,
    ) -> None:
        if (
            not _is_hash(cache_key)
            or not _is_hash(derived_index_key)
            or cache_kind not in {"derived_index", "validated_analysis"}
            or ttl <= timedelta(0)
        ):
            raise BatchRuntimeError("VALIDATION_ERROR")
        raw_metadata = _safe_json(metadata)
        raw_payload = _safe_json(payload)
        entry_digest = _analysis_cache_digest(
            cache_key=cache_key,
            cache_kind=cache_kind,
            derived_index_key=derived_index_key,
            metadata=metadata,
            payload=payload,
        )
        now = _utc(self._now())
        try:
            with self._database.connection() as connection:
                connection.execute(
                    """
                    INSERT INTO analysis_cache_entries(
                      cache_key, cache_kind, derived_index_key, metadata_json, payload_json,
                      payload_sha256, size_bytes, created_at, last_accessed_at, expires_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(cache_key) DO UPDATE SET
                      cache_kind = excluded.cache_kind,
                      derived_index_key = excluded.derived_index_key,
                      metadata_json = excluded.metadata_json,
                      payload_json = excluded.payload_json,
                      payload_sha256 = excluded.payload_sha256,
                      size_bytes = excluded.size_bytes,
                      last_accessed_at = excluded.last_accessed_at,
                      expires_at = excluded.expires_at
                    """,
                    (
                        cache_key,
                        cache_kind,
                        derived_index_key,
                        raw_metadata,
                        raw_payload,
                        entry_digest,
                        len(raw_metadata.encode()) + len(raw_payload.encode()),
                        _timestamp(now),
                        _timestamp(now),
                        _timestamp(now + ttl),
                    ),
                )
        except sqlite3.Error as exc:
            raise RuntimeDatabaseError("runtime_analysis_cache_failed") from exc

    def get_cache(self, cache_key: str) -> CacheEntry | None:
        if not _is_hash(cache_key):
            raise BatchRuntimeError("VALIDATION_ERROR")
        now = _timestamp(_utc(self._now()))
        try:
            with self._database.connection() as connection:
                row = connection.execute(
                    """
                    SELECT * FROM analysis_cache_entries
                    WHERE cache_key = ? AND expires_at > ?
                    """,
                    (cache_key, now),
                ).fetchone()
                if row is None:
                    return None
                try:
                    row_cache_key = str(row["cache_key"])
                    cache_kind = str(row["cache_kind"])
                    derived_index_key = str(row["derived_index_key"])
                    metadata = _json_object(str(row["metadata_json"]))
                    payload = _json_object(str(row["payload_json"]))
                    valid_entry = (
                        row_cache_key == cache_key
                        and cache_kind in {"derived_index", "validated_analysis"}
                        and _is_hash(derived_index_key)
                        and secrets.compare_digest(
                            _analysis_cache_digest(
                                cache_key=row_cache_key,
                                cache_kind=cache_kind,
                                derived_index_key=derived_index_key,
                                metadata=metadata,
                                payload=payload,
                            ),
                            str(row["payload_sha256"]),
                        )
                    )
                except (BatchRuntimeError, ValueError):
                    valid_entry = False
                if not valid_entry:
                    connection.execute(
                        "DELETE FROM analysis_cache_entries WHERE cache_key = ?", (cache_key,)
                    )
                    return None
                connection.execute(
                    "UPDATE analysis_cache_entries SET last_accessed_at = ? WHERE cache_key = ?",
                    (now, cache_key),
                )
        except sqlite3.Error as exc:
            raise RuntimeDatabaseError("runtime_analysis_cache_failed") from exc
        return CacheEntry(
            cache_key=row_cache_key,
            cache_kind=cache_kind,
            derived_index_key=derived_index_key,
            metadata=metadata,
            payload=payload,
        )

    def delete_cache(self, cache_key: str) -> None:
        if not _is_hash(cache_key):
            raise BatchRuntimeError("VALIDATION_ERROR")
        try:
            with self._database.connection() as connection:
                connection.execute(
                    "DELETE FROM analysis_cache_entries WHERE cache_key = ?", (cache_key,)
                )
        except sqlite3.Error as exc:
            raise RuntimeDatabaseError("runtime_analysis_cache_failed") from exc

    def cleanup_expired(self) -> None:
        now = _timestamp(_utc(self._now()))
        try:
            with self._database.connection() as connection:
                connection.execute(
                    "DELETE FROM analysis_cache_entries WHERE expires_at <= ?", (now,)
                )
                connection.execute(
                    """
                    DELETE FROM analysis_batches
                    WHERE expires_at IS NOT NULL AND expires_at <= ?
                      AND state IN ('cancelled', 'completed', 'completed_with_errors', 'failed')
                    """,
                    (now,),
                )
                connection.execute(
                    "DELETE FROM analysis_batch_idempotency_receipts "
                    "WHERE NOT EXISTS (SELECT 1 FROM analysis_batches "
                    "WHERE analysis_batches.batch_id = "
                    "analysis_batch_idempotency_receipts.batch_id)"
                )
        except sqlite3.Error as exc:
            raise RuntimeDatabaseError("runtime_analysis_batch_failed") from exc

    @staticmethod
    def _bind_reanalysis_receipt_locked(
        connection: sqlite3.Connection,
        *,
        idempotency_hash: str,
        request_hash: str,
        batch_id: str,
        created_at: str,
    ) -> None:
        existing = connection.execute(
            "SELECT request_hash, batch_id FROM analysis_batch_idempotency_receipts "
            "WHERE idempotency_key_hash = ?",
            (idempotency_hash,),
        ).fetchone()
        if existing is not None:
            if (
                str(existing["request_hash"]) != request_hash
                or str(existing["batch_id"]) != batch_id
            ):
                raise BatchRuntimeError("ANALYSIS_IDEMPOTENCY_CONFLICT")
            return
        connection.execute(
            "INSERT INTO analysis_batch_idempotency_receipts("
            "idempotency_key_hash, operation, request_hash, batch_id, created_at"
            ") VALUES (?, 'reanalyze', ?, ?, ?)",
            (idempotency_hash, request_hash, batch_id, created_at),
        )

    def _update_item(
        self,
        claimed: ClaimedBatchItem,
        *,
        state: str,
        error_code: str | None,
        error_reason: str | None,
        retry_at: datetime | None,
        result: dict[str, object] | None,
        terminal: bool,
    ) -> None:
        now = _timestamp(_utc(self._now()))
        result_json = _safe_json(result) if result is not None else None
        cancellation_intercepted = False
        try:
            with self._database.connection() as connection:
                connection.execute("BEGIN IMMEDIATE")
                batch = connection.execute(
                    "SELECT state, maximum_generation_attempts FROM analysis_batches "
                    "WHERE batch_id = ?",
                    (claimed.batch_id,),
                ).fetchone()
                if batch is None:
                    connection.execute("ROLLBACK")
                    raise BatchRuntimeError("NOT_FOUND")
                batch_state = str(batch["state"])
                effective_state = "cancelled" if batch_state == "cancelling" else state
                cancellation_intercepted = batch_state == "cancelling" and state != "cancelled"
                generation_increment = 1 if effective_state == "generating" else 0
                item_row = connection.execute(
                    """
                    SELECT state, resume_state, execution_started_at,
                      execution_elapsed_seconds, execution_budget_seconds,
                      generation_attempt_count
                    FROM analysis_batch_items
                    WHERE item_id = ? AND batch_id = ? AND lease_id = ?
                    """,
                    (claimed.item_id, claimed.batch_id, claimed.lease_id),
                ).fetchone()
                if item_row is None:
                    connection.execute("ROLLBACK")
                    raise BatchRuntimeError("ANALYSIS_LEASE_LOST")
                elapsed = _elapsed_since(item_row["execution_started_at"], now)
                total_elapsed = int(item_row["execution_elapsed_seconds"]) + elapsed
                if not terminal and total_elapsed >= int(item_row["execution_budget_seconds"]):
                    connection.execute("ROLLBACK")
                    raise BatchRuntimeError("ANALYSIS_TIMEOUT")
                if effective_state == "generating" and int(
                    item_row["generation_attempt_count"]
                ) >= int(batch["maximum_generation_attempts"]):
                    connection.execute("ROLLBACK")
                    raise BatchRuntimeError("ANALYSIS_GENERATION_ATTEMPTS_EXHAUSTED")
                holds_lease = not (
                    terminal or effective_state in {"waiting_rate_limit", "waiting_reconnection"}
                )
                releases_lease = not holds_lease
                failure_stage = (
                    _failure_stage(item_row)
                    if terminal and effective_state in FAILED_ITEM_STATES
                    else None
                )
                changed = connection.execute(
                    """
                    UPDATE analysis_batch_items
                    SET state = ?, error_code = ?, error_reason = ?, retry_at = ?, result_json = ?,
                      generation_attempt_count = generation_attempt_count + ?,
                      execution_elapsed_seconds = execution_elapsed_seconds + ?,
                      lease_id = CASE WHEN ? THEN NULL ELSE lease_id END,
                      execution_started_at = CASE
                        WHEN ? THEN NULL
                        WHEN ? THEN ?
                        ELSE execution_started_at
                      END,
                      failure_stage = CASE WHEN ? THEN ? ELSE failure_stage END,
                      updated_at = ?
                    WHERE item_id = ? AND batch_id = ? AND lease_id = ?
                    """,
                    (
                        effective_state,
                        error_code,
                        error_reason,
                        _timestamp(retry_at) if retry_at else None,
                        result_json,
                        generation_increment,
                        elapsed,
                        terminal
                        or effective_state in {"waiting_rate_limit", "waiting_reconnection"},
                        releases_lease,
                        holds_lease,
                        now,
                        terminal and effective_state in FAILED_ITEM_STATES,
                        failure_stage,
                        now,
                        claimed.item_id,
                        claimed.batch_id,
                        claimed.lease_id,
                    ),
                ).rowcount
                if changed != 1:
                    connection.execute("ROLLBACK")
                    raise BatchRuntimeError("ANALYSIS_LEASE_LOST")
                event_payload: dict[str, object] = {
                    "state": effective_state,
                    "error_code": error_code,
                }
                if error_reason is not None:
                    event_payload["error_reason"] = error_reason
                self._event_locked(
                    connection,
                    batch_id=claimed.batch_id,
                    item_id=claimed.item_id,
                    event_type="item_terminal" if terminal else "item_stage",
                    payload=event_payload,
                    occurred_at=now,
                )
                self._finish_batch_locked(connection, claimed.batch_id, now)
                connection.execute("COMMIT")
                if cancellation_intercepted:
                    # The durable cancellation has already released the lease.
                    # Tell the runner to stop before it performs work for the
                    # stage whose transition was intercepted.
                    raise BatchRuntimeError("CANCELLED")
        except BatchRuntimeError:
            raise
        except sqlite3.Error as exc:
            raise RuntimeDatabaseError("runtime_analysis_batch_failed") from exc

    @staticmethod
    def _event_locked(
        connection: sqlite3.Connection,
        *,
        batch_id: str,
        item_id: str | None,
        event_type: str,
        payload: dict[str, object],
        occurred_at: str,
    ) -> None:
        connection.execute(
            """
            INSERT INTO analysis_batch_events(
              batch_id, item_id, event_type, payload_json, occurred_at
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (batch_id, item_id, event_type, _safe_json(payload), occurred_at),
        )

    def _finish_batch_locked(self, connection: sqlite3.Connection, batch_id: str, now: str) -> None:
        batch = connection.execute(
            "SELECT state FROM analysis_batches WHERE batch_id = ?", (batch_id,)
        ).fetchone()
        if batch is None:
            return
        state = str(batch["state"])
        rows = connection.execute(
            "SELECT state FROM analysis_batch_items WHERE batch_id = ?", (batch_id,)
        ).fetchall()
        item_states = [str(row["state"]) for row in rows]
        if state == "cancelling" and all(value in ITEM_TERMINAL_STATES for value in item_states):
            next_state = "cancelled"
        elif (
            state in {"queued", "running"}
            and item_states
            and all(value in ITEM_TERMINAL_STATES for value in item_states)
        ):
            if all(value == "complete" for value in item_states):
                next_state = "completed"
            elif any(value == "complete" for value in item_states):
                next_state = "completed_with_errors"
            else:
                next_state = "failed"
        else:
            return
        expires = _timestamp(_utc(self._now()) + BATCH_TTL)
        connection.execute(
            """
            UPDATE analysis_batches
            SET state = ?, completed_at = ?, expires_at = ?, updated_at = ?
            WHERE batch_id = ?
            """,
            (next_state, now, expires, now, batch_id),
        )
        self._event_locked(
            connection,
            batch_id=batch_id,
            item_id=None,
            event_type="batch_terminal",
            payload={"state": next_state},
            occurred_at=now,
        )


def _snapshot(
    batch: sqlite3.Row,
    rows: Sequence[sqlite3.Row],
    *,
    now: str | None = None,
    execution_budget_seconds: int | None = None,
    maximum_generation_attempts: int | None = None,
) -> BatchSnapshot:
    persisted_maximum_attempts = int(batch["maximum_generation_attempts"])
    recovery_maximum_attempts = (
        int(batch["maximum_generation_attempts"])
        if maximum_generation_attempts is None
        else maximum_generation_attempts
    )
    batch_state = str(batch["state"])
    return BatchSnapshot(
        batch_id=str(batch["batch_id"]),
        state=str(batch["state"]),
        plan_id=str(batch["plan_id"]),
        selection_hash=str(batch["selection_hash"]),
        maximum_generation_attempts=persisted_maximum_attempts,
        recovery_maximum_generation_attempts=recovery_maximum_attempts,
        source_batch_id=_optional_text(batch["source_batch_id"]),
        analysis_round=int(batch["analysis_round"]),
        analysis_model_pair=_json_object_optional(batch["analysis_model_pair_json"]),
        created_at=str(batch["created_at"]),
        started_at=_optional_text(batch["started_at"]),
        completed_at=_optional_text(batch["completed_at"]),
        expires_at=_optional_text(batch["expires_at"]),
        error_code=_optional_text(batch["error_code"]),
        items=tuple(
            BatchItemSnapshot(
                item_id=str(row["item_id"]),
                slug=str(row["repository_slug"]),
                requested_ref=_optional_text(row["requested_ref"]),
                commit_sha=_optional_text(row["resolved_commit_sha"]),
                state=str(row["state"]),
                retryable=_retry_eligibility(
                    row,
                    recovery_maximum_attempts,
                    execution_budget_seconds=execution_budget_seconds,
                    batch_state=batch_state,
                )[0],
                reanalyzable=(
                    batch_state in {"failed", "completed_with_errors"}
                    and str(row["state"]) in FAILED_ITEM_STATES
                    and not bool(row["has_successor"])
                    and not _retry_eligibility(
                        row,
                        recovery_maximum_attempts,
                        execution_budget_seconds=execution_budget_seconds,
                        batch_state=batch_state,
                    )[0]
                ),
                retry_blocker=_retry_eligibility(
                    row,
                    recovery_maximum_attempts,
                    execution_budget_seconds=execution_budget_seconds,
                    batch_state=batch_state,
                )[1],
                error_code=_optional_text(row["error_code"]),
                error_reason=_optional_text(row["error_reason"]),
                failure_stage=_optional_text(row["failure_stage"]),
                retry_at=_optional_text(row["retry_at"]),
                execution_elapsed_seconds=int(row["execution_elapsed_seconds"])
                + (
                    _elapsed_since(row["execution_started_at"], now)
                    if now is not None
                    and str(row["state"]) in ITEM_ACTIVE_STAGES
                    and row["lease_id"] is not None
                    else 0
                ),
                execution_budget_seconds=(int(row["execution_budget_seconds"])),
                recovery_execution_budget_seconds=(
                    int(row["execution_budget_seconds"])
                    if execution_budget_seconds is None
                    else execution_budget_seconds
                ),
                generation_attempt_count=int(row["generation_attempt_count"]),
                source_item_id=_optional_text(row["source_item_id"]),
                result=_json_object_optional(row["result_json"]),
            )
            for row in rows
        ),
    )


def _request_matches_existing(
    request: BatchCreateRequest,
    batch: sqlite3.Row,
    rows: Sequence[sqlite3.Row],
) -> bool:
    """Ensure an idempotency key cannot alias a materially different request."""

    if (
        str(batch["plan_id"]) != request.plan_id
        or str(batch["selection_hash"]) != request.selection_hash
        or batch["selected_credential_id"] is not None
        or _optional_text(batch["analysis_model_pair_json"])
        != (
            _safe_json(request.analysis_model_pair)
            if request.analysis_model_pair is not None
            else None
        )
        or int(batch["maximum_generation_attempts"]) != request.maximum_generation_attempts
        or _optional_text(batch["source_batch_id"]) != request.source_batch_id
        or int(batch["analysis_round"]) != request.analysis_round
        or len(rows) != len(request.items)
    ):
        return False
    for row, item in zip(rows, request.items, strict=True):
        if (
            str(row["repository_slug"]) != item.slug
            or _optional_text(row["requested_ref"]) != item.ref
            or _optional_text(row["resolved_commit_sha"]) != item.commit_sha
            or str(row["selection_json"]) != item.policy_json()
            or int(row["execution_budget_seconds"]) != request.execution_budget_seconds
            or _optional_text(row["source_item_id"]) != item.source_item_id
        ):
            return False
    return True


def _retry_eligibility(
    row: sqlite3.Row,
    maximum_attempts: int,
    *,
    execution_budget_seconds: int | None = None,
    batch_state: str | None = None,
) -> tuple[bool, str | None]:
    if batch_state is not None and batch_state not in {"failed", "completed_with_errors"}:
        return False, None
    if str(row["state"]) not in {
        "needs_retry_confirmation",
        "failed",
        "waiting_reconnection",
    }:
        return False, None
    # sqlite3.Row membership checks values, so inspect its named columns explicitly.
    if "has_successor" in set(row.keys()) and bool(row["has_successor"]):
        return False, "SUCCESSOR_EXISTS"
    if int(row["generation_attempt_count"]) >= maximum_attempts:
        return False, "ATTEMPTS_EXHAUSTED"
    effective_budget = (
        int(row["execution_budget_seconds"])
        if execution_budget_seconds is None
        else execution_budget_seconds
    )
    if int(row["execution_elapsed_seconds"]) >= effective_budget:
        return False, "EXECUTION_BUDGET_EXHAUSTED"
    return True, None


def reanalysis_plan_id(
    *,
    source_batch_id: str,
    analysis_round: int,
    model_selection: str,
    confirm_model_change: bool,
    expected_selection_generation: int | None,
) -> str:
    """Persist the complete caller-confirmed successor request identity."""

    identity = _safe_json(
        {
            "source_batch_id": source_batch_id,
            "analysis_round": analysis_round,
            "model_selection": model_selection,
            "confirm_model_change": confirm_model_change,
            "expected_selection_generation": expected_selection_generation,
        }
    )
    return f"reanalyze:{hashlib.sha256(identity.encode()).hexdigest()}"


def reanalysis_request_hash(
    *,
    source_batch_id: str,
    item_ids: Sequence[str],
    model_selection: str,
    confirm_model_change: bool,
    expected_selection_generation: int | None,
) -> str:
    """Hash the full request bound to a reanalysis idempotency key."""

    return _hash(
        _safe_json(
            {
                "source_batch_id": source_batch_id,
                "item_ids": sorted(item_ids),
                "model_selection": model_selection,
                "confirm_model_change": confirm_model_change,
                "expected_selection_generation": expected_selection_generation,
            }
        )
    )


def _failure_stage(row: sqlite3.Row) -> str:
    state = str(row["state"])
    if state in ITEM_ACTIVE_STAGES:
        return state
    resume_state = _optional_text(row["resume_state"])
    if resume_state in ITEM_ACTIVE_STAGES:
        return resume_state
    return "queued"


def _github_resolution_key(kind: str, slug: str, requested_ref: str | None) -> str:
    return hashlib.sha256(
        "\x1f".join((kind, slug, requested_ref or "<default>")).encode()
    ).hexdigest()


def _elapsed_since(started_at: object, now: str) -> int:
    if started_at is None:
        return 0
    try:
        started = datetime.fromisoformat(str(started_at))
        current = datetime.fromisoformat(now)
    except ValueError:
        return 0
    if started.tzinfo is None or current.tzinfo is None:
        return 0
    return max(0, int((current - started).total_seconds()))


def _input_from_row(row: sqlite3.Row) -> BatchItemInput:
    policy = _json_object(str(row["selection_json"]))
    include = policy.get("include", [])
    exclude = policy.get("exclude", [])
    if not isinstance(include, list) or not all(isinstance(value, str) for value in include):
        raise BatchRuntimeError("VALIDATION_ERROR")
    if not isinstance(exclude, list) or not all(isinstance(value, str) for value in exclude):
        raise BatchRuntimeError("VALIDATION_ERROR")
    commit = _optional_text(row["resolved_commit_sha"])
    if commit is None or not _is_commit(commit):
        raise BatchRuntimeError("ANALYSIS_PLAN_STALE")
    return BatchItemInput(
        slug=str(row["repository_slug"]),
        ref=_optional_text(row["requested_ref"]),
        include=tuple(include),
        exclude=tuple(exclude),
        commit_sha=commit,
    )


def _event_from_row(row: sqlite3.Row) -> BatchEvent:
    return BatchEvent(
        event_id=int(row["event_id"]),
        batch_id=str(row["batch_id"]),
        item_id=_optional_text(row["item_id"]),
        event_type=str(row["event_type"]),
        payload=_json_object(str(row["payload_json"])),
        occurred_at=str(row["occurred_at"]),
    )


def _safe_json(value: dict[str, object]) -> str:
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    except (TypeError, ValueError) as exc:
        raise BatchRuntimeError("VALIDATION_ERROR") from exc


def _analysis_cache_digest(
    *,
    cache_key: str,
    cache_kind: str,
    derived_index_key: str,
    metadata: dict[str, object],
    payload: dict[str, object],
) -> str:
    """Bind every logical cache-entry field using canonical JSON."""

    return _hash(
        _safe_json(
            {
                "cache_key": cache_key,
                "cache_kind": cache_kind,
                "derived_index_key": derived_index_key,
                "metadata": metadata,
                "payload": payload,
            }
        )
    )


def _is_analysis_model_pair(value: dict[str, object]) -> bool:
    try:
        from reponpc.admin.analysis_selection import AnalysisModelPair

        AnalysisModelPair.from_safe_dict(value)
    except Exception:
        return False
    return True


def _json_object(value: str) -> dict[str, object]:
    try:
        result = json.loads(value)
    except (TypeError, json.JSONDecodeError) as exc:
        raise ValueError("invalid safe JSON") from exc
    if not isinstance(result, dict):
        raise ValueError("invalid safe JSON")
    return result


def _json_object_optional(value: object) -> dict[str, object] | None:
    if value is None:
        return None
    try:
        return _json_object(str(value))
    except ValueError:
        return None


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _is_hash(value: str) -> bool:
    return len(value) == 64 and all(character in "0123456789abcdef" for character in value)


def _is_commit(value: str) -> bool:
    return len(value) == 40 and all(character in "0123456789abcdef" for character in value)


def _optional_text(value: object) -> str | None:
    return str(value) if value is not None else None


def _optional_int(value: object) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    if not isinstance(value, int) or value < 0:
        return None
    return value


def _parse_optional_timestamp(value: object) -> datetime | None:
    text = _optional_text(value)
    if text is None:
        return None
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    return parsed.astimezone(UTC) if parsed.tzinfo is not None else None


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise ValueError("batch runtime clock must be timezone-aware")
    return value.astimezone(UTC)


def _timestamp(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")
