"""Cost-before-work public chat limits backed by mutable runtime SQLite."""

from __future__ import annotations

import hashlib
import hmac
import sqlite3
import threading
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum

from reponpc.runtime.database import RuntimeDatabase, RuntimeDatabaseError


class ChatLimitError(RuntimeError):
    """Safe stable rejection raised before retrieval or provider work."""

    def __init__(self, code: str, retry_after_seconds: int | None = None) -> None:
        self.code = code
        self.retry_after_seconds = retry_after_seconds
        super().__init__("chat request limit exceeded")


class ProviderLane(StrEnum):
    """Fair provider-capacity lanes in descending default weight."""

    PUBLIC_CHAT = "public_chat"
    ADMIN_SINGLE = "admin_single"
    ADMIN_BATCH = "admin_batch"


DEFAULT_PROVIDER_LANE_WEIGHTS: Mapping[ProviderLane, int] = {
    ProviderLane.PUBLIC_CHAT: 4,
    ProviderLane.ADMIN_SINGLE: 2,
    ProviderLane.ADMIN_BATCH: 1,
}


@dataclass(slots=True)
class ChatPermit:
    """A concurrency permit that is released on completion or cancellation."""

    _release_callback: Callable[[], None]
    _released: bool = False

    def release(self) -> None:
        if not self._released:
            self._released = True
            self._release_callback()

    def __enter__(self) -> ChatPermit:
        return self

    def __exit__(self, *_args: object) -> None:
        self.release()


@dataclass(slots=True)
class _ProviderWaiter:
    lane: ProviderLane
    granted: bool = False


class _ProviderPermitScheduler:
    """Bounded weighted-round-robin allocator for actual provider calls only."""

    def __init__(self, *, capacity: int, weights: Mapping[ProviderLane, int]) -> None:
        self._condition = threading.Condition()
        self._available = capacity
        self._waiters: list[_ProviderWaiter] = []
        self._weights = dict(weights)
        self._remaining = dict(weights)

    def acquire(self, lane: ProviderLane, *, timeout_seconds: float) -> ChatPermit:
        deadline = time.monotonic() + timeout_seconds
        waiter = _ProviderWaiter(lane=lane)
        with self._condition:
            self._waiters.append(waiter)
            self._grant_available_locked()
            while not waiter.granted:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    self._waiters.remove(waiter)
                    self._grant_available_locked()
                    raise ChatLimitError("CONCURRENCY_LIMIT", 1)
                self._condition.wait(remaining)
            return ChatPermit(self.release)

    def release(self) -> None:
        with self._condition:
            self._available += 1
            self._grant_available_locked()

    def _grant_available_locked(self) -> None:
        while self._available > 0 and self._waiters:
            waiter = self._next_waiter_locked()
            if waiter is None:
                return
            waiter.granted = True
            self._available -= 1
            self._condition.notify_all()

    def _next_waiter_locked(self) -> _ProviderWaiter | None:
        waiter = self._next_waiter_with_credit_locked()
        if waiter is not None:
            return waiter
        self._remaining = dict(self._weights)
        return self._next_waiter_with_credit_locked()

    def _next_waiter_with_credit_locked(self) -> _ProviderWaiter | None:
        for lane in ProviderLane:
            if self._remaining[lane] <= 0:
                continue
            for index, waiter in enumerate(self._waiters):
                if waiter.lane is lane:
                    self._remaining[lane] -= 1
                    return self._waiters.pop(index)
        return None


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
        provider_lane_weights: Mapping[ProviderLane | str, int] | None = None,
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
        self._provider_permits = _ProviderPermitScheduler(
            capacity=global_concurrency,
            weights=_provider_lane_weights(provider_lane_weights),
        )

    def acquire(self, client_ip: str, *, now: datetime | None = None) -> ChatPermit:
        """Legacy public-chat admission plus one provider permit.

        New callers that perform retrieval before a provider call should use
        :meth:`admit_public_chat` at request admission, then acquire a
        ``PUBLIC_CHAT`` provider permit immediately around each embedding or
        generation call.
        """

        if not client_ip:
            raise ChatLimitError("RATE_LIMITED", 60)
        instant = (now or datetime.now(UTC)).astimezone(UTC)
        permit = self.acquire_generation(ProviderLane.PUBLIC_CHAT)
        try:
            self._consume_persistent_limits(client_ip, instant)
        except Exception:
            permit.release()
            raise
        return permit

    def admit_public_chat(self, client_ip: str, *, now: datetime | None = None) -> None:
        """Atomically charge public request limits without reserving provider capacity."""

        if not client_ip:
            raise ChatLimitError("RATE_LIMITED", 60)
        instant = (now or datetime.now(UTC)).astimezone(UTC)
        self._consume_persistent_limits(client_ip, instant)

    def acquire_generation(
        self,
        lane: ProviderLane | str = ProviderLane.ADMIN_SINGLE,
        *,
        timeout_seconds: float = 0,
    ) -> ChatPermit:
        """Acquire one fair provider permit without charging public counters.

        The default remains the historic admin/onboarding behavior. Public
        request admission uses :meth:`acquire` or explicitly passes
        ``ProviderLane.PUBLIC_CHAT``. A zero timeout retains the prior
        non-blocking ``CONCURRENCY_LIMIT`` outcome; batch workers may wait for
        a bounded duration instead of polling or holding permits during local
        archive/index work.
        """

        if isinstance(timeout_seconds, bool) or timeout_seconds < 0:
            raise ValueError("provider permit timeout must be non-negative")
        try:
            selected_lane = ProviderLane(lane)
        except ValueError as exc:
            raise ValueError("provider permit lane is invalid") from exc
        return self._provider_permits.acquire(
            selected_lane,
            timeout_seconds=float(timeout_seconds),
        )

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


def _provider_lane_weights(
    supplied: Mapping[ProviderLane | str, int] | None,
) -> dict[ProviderLane, int]:
    weights = dict(DEFAULT_PROVIDER_LANE_WEIGHTS)
    if supplied is not None:
        for lane, weight in supplied.items():
            try:
                normalized_lane = ProviderLane(lane)
            except ValueError as exc:
                raise ValueError("provider permit lane is invalid") from exc
            weights[normalized_lane] = weight
    if any(
        not isinstance(weight, int) or isinstance(weight, bool) or weight <= 0
        for weight in weights.values()
    ):
        raise ValueError("provider lane weights must be positive integers")
    return weights


def _timestamp(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")
