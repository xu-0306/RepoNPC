"""Cost-before-work public chat limits backed by mutable runtime SQLite."""

from __future__ import annotations

import hashlib
import hmac
import sqlite3
import threading
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from reponpc.runtime.database import RuntimeDatabase, RuntimeDatabaseError


class ChatLimitError(RuntimeError):
    """Safe stable rejection raised before retrieval or provider work."""

    def __init__(self, code: str, retry_after_seconds: int | None = None) -> None:
        self.code = code
        self.retry_after_seconds = retry_after_seconds
        super().__init__("chat request limit exceeded")


@dataclass(slots=True)
class ChatPermit:
    """A concurrency permit that is released on completion or cancellation."""

    _semaphore: threading.BoundedSemaphore
    _released: bool = False

    def release(self) -> None:
        if not self._released:
            self._released = True
            self._semaphore.release()

    def __enter__(self) -> ChatPermit:
        return self

    def __exit__(self, *_args: object) -> None:
        self.release()


class ChatLimits:
    """Atomically consume IP/daily capacity before granting global concurrency."""

    def __init__(
        self,
        database: RuntimeDatabase,
        *,
        ip_hash_key: bytes,
        requests_per_minute: int,
        daily_budget: int,
        global_concurrency: int,
    ) -> None:
        if len(ip_hash_key) < 16:
            raise ValueError("IP hash key must contain at least 128 bits")
        for value in (requests_per_minute, daily_budget, global_concurrency):
            if isinstance(value, bool) or value <= 0:
                raise ValueError("chat limits must be positive integers")
        self._database = database
        self._key = bytes(ip_hash_key)
        self._rate = requests_per_minute
        self._daily = daily_budget
        self._concurrency = threading.BoundedSemaphore(global_concurrency)

    def acquire(self, client_ip: str, *, now: datetime | None = None) -> ChatPermit:
        """Reject exhausted limits before returning a model-generation permit."""

        if not client_ip:
            raise ChatLimitError("RATE_LIMITED", 60)
        instant = (now or datetime.now(UTC)).astimezone(UTC)
        if not self._concurrency.acquire(blocking=False):
            raise ChatLimitError("CONCURRENCY_LIMIT", 1)
        permit = ChatPermit(self._concurrency)
        try:
            self._consume_persistent_limits(client_ip, instant)
        except Exception:
            permit.release()
            raise
        return permit

    def _consume_persistent_limits(self, client_ip: str, instant: datetime) -> None:
        ip_hmac = hmac.new(self._key, client_ip.encode(), hashlib.sha256).hexdigest()
        bucket_start = instant.replace(second=0, microsecond=0)
        bucket_end = bucket_start + timedelta(minutes=1)
        usage_date = instant.date().isoformat()
        with self._database.connection() as connection:
            try:
                connection.execute("BEGIN IMMEDIATE")
                rate_row = connection.execute(
                    "SELECT remaining_tokens FROM rate_buckets "
                    "WHERE ip_hmac = ? AND bucket_started_at = ?",
                    (ip_hmac, _timestamp(bucket_start)),
                ).fetchone()
                remaining = self._rate if rate_row is None else int(rate_row[0])
                if remaining <= 0:
                    raise ChatLimitError(
                        "RATE_LIMITED", max(1, int((bucket_end - instant).total_seconds()))
                    )
                usage_row = connection.execute(
                    "SELECT accepted_count FROM daily_usage WHERE usage_date = ?",
                    (usage_date,),
                ).fetchone()
                accepted = 0 if usage_row is None else int(usage_row[0])
                if accepted >= self._daily:
                    tomorrow = (instant + timedelta(days=1)).replace(
                        hour=0, minute=0, second=0, microsecond=0
                    )
                    raise ChatLimitError(
                        "DAILY_BUDGET_EXHAUSTED",
                        max(1, int((tomorrow - instant).total_seconds())),
                    )
                connection.execute(
                    """
                    INSERT INTO rate_buckets(
                      ip_hmac, bucket_started_at, capacity, remaining_tokens, expires_at
                    ) VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(ip_hmac, bucket_started_at) DO UPDATE SET
                      remaining_tokens = excluded.remaining_tokens,
                      expires_at = excluded.expires_at
                    """,
                    (
                        ip_hmac,
                        _timestamp(bucket_start),
                        self._rate,
                        remaining - 1,
                        _timestamp(bucket_end),
                    ),
                )
                connection.execute(
                    """
                    INSERT INTO daily_usage(
                      usage_date, accepted_count, input_token_count,
                      output_token_count, estimated_cost_micros
                    ) VALUES (?, 1, NULL, NULL, NULL)
                    ON CONFLICT(usage_date) DO UPDATE SET
                      accepted_count = accepted_count + 1
                    """,
                    (usage_date,),
                )
                connection.execute("COMMIT")
            except ChatLimitError:
                if connection.in_transaction:
                    connection.execute("ROLLBACK")
                raise
            except sqlite3.Error as exc:
                if connection.in_transaction:
                    connection.execute("ROLLBACK")
                raise RuntimeDatabaseError("runtime_chat_limit_failed") from exc


def _timestamp(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")
