"""Persistent chat limits reject before callers can invoke providers."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from reponpc.chat.limits import ChatLimitError, ChatLimits
from reponpc.runtime.database import RuntimeDatabase

NOW = datetime(2026, 8, 12, 12, 0, tzinfo=UTC)


def limits(tmp_path: Path, **overrides: int) -> tuple[RuntimeDatabase, ChatLimits]:
    database = RuntimeDatabase(tmp_path / "runtime")
    database.initialize()
    values = {
        "requests_per_minute": 2,
        "daily_budget": 3,
        "global_concurrency": 1,
        **overrides,
    }
    return database, ChatLimits(database, ip_hash_key=b"fixture-key-16bytes", **values)


def test_ip_bucket_stores_only_hmac_and_rejects_before_next_work(tmp_path: Path) -> None:
    database, subject = limits(tmp_path)
    provider_calls = 0

    for _ in range(2):
        with subject.acquire("203.0.113.10", now=NOW):
            provider_calls += 1
    with pytest.raises(ChatLimitError) as raised:
        subject.acquire("203.0.113.10", now=NOW)

    assert raised.value.code == "RATE_LIMITED"
    assert provider_calls == 2
    with database.connection() as connection:
        row = connection.execute("SELECT ip_hmac FROM rate_buckets").fetchone()
    assert row is not None
    assert row[0] != "203.0.113.10"
    assert len(row[0]) == 64


def test_daily_budget_is_global_across_ip_addresses(tmp_path: Path) -> None:
    _database, subject = limits(tmp_path, requests_per_minute=10, daily_budget=2)

    with subject.acquire("203.0.113.1", now=NOW):
        pass
    with subject.acquire("203.0.113.2", now=NOW):
        pass
    with pytest.raises(ChatLimitError) as raised:
        subject.acquire("203.0.113.3", now=NOW)

    assert raised.value.code == "DAILY_BUDGET_EXHAUSTED"


def test_daily_and_ip_limits_are_shared_across_independent_owners(tmp_path: Path) -> None:
    database, first = limits(tmp_path, requests_per_minute=2, daily_budget=2)
    second = ChatLimits(
        database,
        ip_hash_key=b"fixture-key-16bytes",
        requests_per_minute=2,
        daily_budget=2,
        global_concurrency=1,
    )

    with first.acquire("203.0.113.8", now=NOW):
        pass
    with second.acquire("203.0.113.8", now=NOW):
        pass
    with pytest.raises(ChatLimitError) as raised:
        first.acquire("203.0.113.9", now=NOW)

    assert raised.value.code == "DAILY_BUDGET_EXHAUSTED"
    with database.connection() as connection:
        accepted = connection.execute(
            "SELECT accepted_count FROM daily_usage WHERE usage_date = ?", ("2026-08-12",)
        ).fetchone()[0]
        bucket = connection.execute(
            "SELECT remaining_tokens FROM rate_buckets ORDER BY rowid LIMIT 1"
        ).fetchone()[0]
    assert accepted == 2
    assert bucket == 0


def test_concurrency_rejection_does_not_consume_persistent_budget(tmp_path: Path) -> None:
    database, subject = limits(tmp_path)
    first = subject.acquire("203.0.113.1", now=NOW)

    with pytest.raises(ChatLimitError) as raised:
        subject.acquire("203.0.113.2", now=NOW)
    first.release()

    assert raised.value.code == "CONCURRENCY_LIMIT"
    with database.connection() as connection:
        accepted = connection.execute(
            "SELECT accepted_count FROM daily_usage WHERE usage_date = ?", ("2026-08-12",)
        ).fetchone()[0]
    assert accepted == 1


def test_permit_release_is_idempotent_for_cancellation_cleanup(tmp_path: Path) -> None:
    _database, subject = limits(tmp_path)
    permit = subject.acquire("203.0.113.1", now=NOW)
    permit.release()
    permit.release()

    with subject.acquire("203.0.113.2", now=NOW):
        pass
