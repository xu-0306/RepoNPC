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

from reponpc.admin.batch_resolver import GitHubRateResource, RateBudget
from reponpc.runtime.database import RuntimeDatabase, RuntimeDatabaseError

BATCH_TTL: Final = timedelta(hours=24)
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


class BatchRuntimeError(RuntimeError):
    """A stable, safe batch-state failure."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__("analysis batch operation failed")


@dataclass(frozen=True, slots=True)
class BatchItemInput:
    """Safe persisted policy and immutable source identity for one item."""

    slug: str
    ref: str | None
    include: tuple[str, ...]
    exclude: tuple[str, ...]
    commit_sha: str

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
    selected_credential_id: int | None
    maximum_generation_attempts: int = 1


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
    error_code: str | None
    retry_at: str | None
    result: dict[str, object] | None


@dataclass(frozen=True, slots=True)
class BatchSnapshot:
    batch_id: str
    state: str
    plan_id: str
    selection_hash: str
    maximum_generation_attempts: int
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

    def load(self) -> tuple[RateBudget, RateBudget, datetime | None]:
        values = {
            GitHubRateResource.GRAPHQL: RateBudget(GitHubRateResource.GRAPHQL, None, None, None),
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
            elif resource in {GitHubRateResource.GRAPHQL, GitHubRateResource.CORE}:
                parsed_resource = GitHubRateResource(resource)
                values[parsed_resource] = RateBudget(
                    resource=parsed_resource,
                    limit=_optional_int(row["limit_value"]),
                    remaining=_optional_int(row["remaining"]),
                    reset_at=_parse_optional_timestamp(row["reset_at"]),
                )
        return values[GitHubRateResource.GRAPHQL], values[GitHubRateResource.CORE], secondary

    def save(
        self,
        *,
        graphql: RateBudget,
        core: RateBudget,
        secondary_retry_at: datetime | None,
    ) -> None:
        now = _timestamp(_utc(self._now()))
        rows = (
            (
                GitHubRateResource.GRAPHQL,
                graphql.remaining,
                graphql.limit,
                _timestamp(graphql.reset_at) if graphql.reset_at is not None else None,
                None,
                now,
            ),
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

        if (
            not request.plan_id
            or not _is_hash(request.selection_hash)
            or request.selected_credential_id is None
            or request.selected_credential_id <= 0
        ):
            raise BatchRuntimeError("ANALYSIS_PLAN_STALE")
        if not request.idempotency_key or len(request.idempotency_key) > 512:
            raise BatchRuntimeError("VALIDATION_ERROR")
        if not request.items or len(request.items) > 50:
            raise BatchRuntimeError("VALIDATION_ERROR")
        if not 1 <= request.maximum_generation_attempts <= 10:
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
                now,
                now,
            )
            for position, item in enumerate(request.items)
        ]
        try:
            with self._database.connection() as connection:
                connection.execute("BEGIN IMMEDIATE")
                existing = connection.execute(
                    "SELECT * FROM analysis_batches WHERE idempotency_key_hash = ?",
                    (idempotency_hash,),
                ).fetchone()
                if existing is not None:
                    existing_items = connection.execute(
                        "SELECT * FROM analysis_batch_items WHERE batch_id = ? ORDER BY position",
                        (str(existing["batch_id"]),),
                    ).fetchall()
                    connection.execute("COMMIT")
                    if not _request_matches_existing(request, existing, existing_items):
                        raise BatchRuntimeError("VALIDATION_ERROR")
                    return self.get_batch(str(existing["batch_id"])), False
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
                      idempotency_key_hash, selected_credential_id, state,
                      maximum_generation_attempts,
                      created_at, updated_at
                    ) VALUES (?, 'singleton', ?, ?, ?, ?, 'queued', ?, ?, ?)
                    """,
                    (
                        batch_id,
                        request.plan_id,
                        request.selection_hash,
                        idempotency_hash,
                        request.selected_credential_id,
                        request.maximum_generation_attempts,
                        now,
                        now,
                    ),
                )
                connection.executemany(
                    """
                    INSERT INTO analysis_batch_items(
                      item_id, batch_id, position, repository_slug, requested_ref,
                      selection_hash, resolved_commit_sha, selection_json, state,
                      created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    item_rows,
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

    def get_batch(self, batch_id: str) -> BatchSnapshot:
        with self._database.connection() as connection:
            batch = connection.execute(
                "SELECT * FROM analysis_batches WHERE batch_id = ?", (batch_id,)
            ).fetchone()
            if batch is None:
                raise BatchRuntimeError("NOT_FOUND")
            rows = connection.execute(
                "SELECT * FROM analysis_batch_items WHERE batch_id = ? ORDER BY position",
                (batch_id,),
            ).fetchall()
        return _snapshot(batch, rows)

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

    def selected_credential_id(self, batch_id: str) -> int:
        """Return the one immutable credential selected at batch creation."""

        with self._database.connection() as connection:
            row = connection.execute(
                "SELECT selected_credential_id FROM analysis_batches WHERE batch_id = ?",
                (batch_id,),
            ).fetchone()
        if row is None or row["selected_credential_id"] is None:
            raise BatchRuntimeError("NOT_FOUND")
        credential_id = int(row["selected_credential_id"])
        if credential_id <= 0:
            raise BatchRuntimeError("ANALYSIS_PLAN_STALE")
        return credential_id

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
                    "SELECT state FROM analysis_batches WHERE batch_id = ?", (batch_id,)
                ).fetchone()
                if row is None:
                    connection.execute("ROLLBACK")
                    raise BatchRuntimeError("NOT_FOUND")
                state = str(row["state"])
                if state in {"cancelled", "completed", "completed_with_errors", "failed"}:
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

    def retry_items(self, batch_id: str) -> BatchSnapshot:
        """Explicitly requeue only terminal retryable items."""

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
                changed = connection.execute(
                    """
                    UPDATE analysis_batch_items
                    SET state = 'queued', error_code = NULL, retry_at = NULL,
                        lease_id = NULL, execution_started_at = NULL, updated_at = ?
                    WHERE batch_id = ?
                      AND state IN ('needs_retry_confirmation', 'failed', 'waiting_reconnection')
                      AND generation_attempt_count < (
                        SELECT maximum_generation_attempts FROM analysis_batches
                        WHERE batch_id = ?
                      )
                    """,
                    (now, batch_id, batch_id),
                ).rowcount
                if not changed:
                    connection.execute("ROLLBACK")
                    raise BatchRuntimeError("VALIDATION_ERROR")
                connection.execute(
                    """
                    UPDATE analysis_batches SET state = 'running', error_code = NULL,
                      completed_at = NULL, expires_at = NULL, updated_at = ?
                    WHERE batch_id = ?
                    """,
                    (now, batch_id),
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
                    "SELECT state FROM analysis_batches WHERE batch_id = ?", (batch_id,)
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
        )

    def advance_item(
        self,
        claimed: ClaimedBatchItem,
        *,
        state: str,
        error_code: str | None = None,
        retry_at: datetime | None = None,
    ) -> None:
        if state not in ITEM_ACTIVE_STAGES | {"waiting_rate_limit", "waiting_reconnection"}:
            raise BatchRuntimeError("VALIDATION_ERROR")
        self._update_item(
            claimed,
            state=state,
            error_code=error_code,
            retry_at=retry_at,
            result=None,
            terminal=False,
        )

    def complete_item(self, claimed: ClaimedBatchItem, *, result: dict[str, object]) -> None:
        self._update_item(
            claimed,
            state="complete",
            error_code=None,
            retry_at=None,
            result=result,
            terminal=True,
        )

    def fail_item(
        self,
        claimed: ClaimedBatchItem,
        *,
        code: str,
        retry_confirmation: bool = False,
    ) -> None:
        self._update_item(
            claimed,
            state="needs_retry_confirmation" if retry_confirmation else "failed",
            error_code=code,
            retry_at=None,
            result=None,
            terminal=True,
        )

    def cancel_item(self, claimed: ClaimedBatchItem) -> None:
        self._update_item(
            claimed,
            state="cancelled",
            error_code=None,
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
                          execution_elapsed_seconds = execution_elapsed_seconds + ?, updated_at = ?
                        WHERE item_id = ?
                        """,
                        (next_state, state, elapsed, now, str(row["item_id"])),
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
                cancelling_batches = connection.execute(
                    "SELECT batch_id FROM analysis_batches WHERE state = 'cancelling'"
                ).fetchall()
                for batch_row in cancelling_batches:
                    self._finish_batch_locked(connection, str(batch_row["batch_id"]), now)
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
        raw_payload = _safe_json(payload)
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
                        _safe_json(metadata),
                        raw_payload,
                        hashlib.sha256(raw_payload.encode()).hexdigest(),
                        len(raw_payload.encode()),
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
                payload = str(row["payload_json"])
                if hashlib.sha256(payload.encode()).hexdigest() != str(row["payload_sha256"]):
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
        try:
            return CacheEntry(
                cache_key=str(row["cache_key"]),
                cache_kind=str(row["cache_kind"]),
                derived_index_key=str(row["derived_index_key"]),
                metadata=_json_object(str(row["metadata_json"])),
                payload=_json_object(payload),
            )
        except ValueError:
            return None

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
        except sqlite3.Error as exc:
            raise RuntimeDatabaseError("runtime_analysis_batch_failed") from exc

    def _update_item(
        self,
        claimed: ClaimedBatchItem,
        *,
        state: str,
        error_code: str | None,
        retry_at: datetime | None,
        result: dict[str, object] | None,
        terminal: bool,
    ) -> None:
        now = _timestamp(_utc(self._now()))
        result_json = _safe_json(result) if result is not None else None
        try:
            with self._database.connection() as connection:
                connection.execute("BEGIN IMMEDIATE")
                batch = connection.execute(
                    "SELECT state FROM analysis_batches WHERE batch_id = ?", (claimed.batch_id,)
                ).fetchone()
                if batch is None:
                    connection.execute("ROLLBACK")
                    raise BatchRuntimeError("NOT_FOUND")
                batch_state = str(batch["state"])
                effective_state = "cancelled" if batch_state == "cancelling" else state
                generation_increment = 1 if effective_state == "generating" else 0
                item_row = connection.execute(
                    """
                    SELECT execution_started_at, execution_elapsed_seconds
                    FROM analysis_batch_items
                    WHERE item_id = ? AND batch_id = ? AND lease_id = ?
                    """,
                    (claimed.item_id, claimed.batch_id, claimed.lease_id),
                ).fetchone()
                if item_row is None:
                    connection.execute("ROLLBACK")
                    raise BatchRuntimeError("ANALYSIS_LEASE_LOST")
                elapsed = _elapsed_since(item_row["execution_started_at"], now)
                holds_lease = not (
                    terminal or effective_state in {"waiting_rate_limit", "waiting_reconnection"}
                )
                changed = connection.execute(
                    """
                    UPDATE analysis_batch_items
                    SET state = ?, error_code = ?, retry_at = ?, result_json = ?,
                      generation_attempt_count = generation_attempt_count + ?,
                      execution_elapsed_seconds = execution_elapsed_seconds + ?,
                      lease_id = CASE WHEN ? THEN NULL ELSE lease_id END,
                      execution_started_at = CASE WHEN ? THEN ? ELSE execution_started_at END,
                      updated_at = ?
                    WHERE item_id = ? AND batch_id = ? AND lease_id = ?
                    """,
                    (
                        effective_state,
                        error_code,
                        _timestamp(retry_at) if retry_at else None,
                        result_json,
                        generation_increment,
                        elapsed,
                        terminal
                        or effective_state in {"waiting_rate_limit", "waiting_reconnection"},
                        holds_lease,
                        now,
                        now,
                        claimed.item_id,
                        claimed.batch_id,
                        claimed.lease_id,
                    ),
                ).rowcount
                if changed != 1:
                    connection.execute("ROLLBACK")
                    raise BatchRuntimeError("ANALYSIS_LEASE_LOST")
                self._event_locked(
                    connection,
                    batch_id=claimed.batch_id,
                    item_id=claimed.item_id,
                    event_type="item_terminal" if terminal else "item_stage",
                    payload={"state": effective_state, "error_code": error_code},
                    occurred_at=now,
                )
                self._finish_batch_locked(connection, claimed.batch_id, now)
                connection.execute("COMMIT")
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


def _snapshot(batch: sqlite3.Row, rows: Sequence[sqlite3.Row]) -> BatchSnapshot:
    return BatchSnapshot(
        batch_id=str(batch["batch_id"]),
        state=str(batch["state"]),
        plan_id=str(batch["plan_id"]),
        selection_hash=str(batch["selection_hash"]),
        maximum_generation_attempts=int(batch["maximum_generation_attempts"]),
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
                retryable=str(row["state"])
                in {"needs_retry_confirmation", "failed", "waiting_reconnection"},
                error_code=_optional_text(row["error_code"]),
                retry_at=_optional_text(row["retry_at"]),
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
        or int(batch["selected_credential_id"] or 0) != request.selected_credential_id
        or int(batch["maximum_generation_attempts"]) != request.maximum_generation_attempts
        or len(rows) != len(request.items)
    ):
        return False
    for row, item in zip(rows, request.items, strict=True):
        if (
            str(row["repository_slug"]) != item.slug
            or _optional_text(row["requested_ref"]) != item.ref
            or _optional_text(row["resolved_commit_sha"]) != item.commit_sha
            or str(row["selection_json"]) != item.policy_json()
        ):
            return False
    return True


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
