"""Focused fairness and admission coverage for provider permits."""

from __future__ import annotations

import threading
import time
from datetime import UTC, datetime
from pathlib import Path

import pytest

from reponpc.chat.limits import ChatLimitError, ChatLimits, ProviderLane
from reponpc.runtime.database import RuntimeDatabase


def _limits(tmp_path: Path, *, concurrency: int = 1) -> ChatLimits:
    database = RuntimeDatabase(tmp_path / "runtime")
    database.initialize()
    return ChatLimits(
        database,
        ip_hash_key=b"fixture-key-16bytes",
        requests_per_minute=10,
        daily_budget=10,
        global_concurrency=concurrency,
    )


def _wait_for_waiters(subject: ChatLimits, expected: int) -> None:
    deadline = time.monotonic() + 2
    scheduler = subject._provider_permits
    while time.monotonic() < deadline:
        with scheduler._condition:
            if len(scheduler._waiters) == expected:
                return
        time.sleep(0.005)
    pytest.fail("provider waiters did not queue in time")


def test_weighted_scheduler_grants_public_then_admin_then_batch(tmp_path: Path) -> None:
    subject = _limits(tmp_path)
    held = subject.acquire_generation(ProviderLane.ADMIN_BATCH)
    order: list[ProviderLane] = []
    completed = threading.Event()
    lock = threading.Lock()
    lanes = (
        (ProviderLane.PUBLIC_CHAT,) * 4
        + (ProviderLane.ADMIN_SINGLE,) * 2
        + (ProviderLane.ADMIN_BATCH,)
    )

    def wait_for_permit(lane: ProviderLane) -> None:
        with subject.acquire_generation(lane, timeout_seconds=2), lock:
            order.append(lane)
            if len(order) == len(lanes):
                completed.set()

    workers = [threading.Thread(target=wait_for_permit, args=(lane,)) for lane in lanes]
    for worker in workers:
        worker.start()
    _wait_for_waiters(subject, len(lanes))

    held.release()
    assert completed.wait(2)
    for worker in workers:
        worker.join(timeout=2)
        assert not worker.is_alive()

    assert order == list(lanes)


def test_public_waiter_has_priority_over_earlier_batch_waiter(tmp_path: Path) -> None:
    subject = _limits(tmp_path)
    held = subject.acquire_generation(ProviderLane.ADMIN_SINGLE)
    grants: list[ProviderLane] = []
    granted = threading.Event()
    release = threading.Event()
    lock = threading.Lock()

    def wait_for_permit(lane: ProviderLane) -> None:
        with subject.acquire_generation(lane, timeout_seconds=2):
            with lock:
                grants.append(lane)
                granted.set()
            release.wait(2)

    batch = threading.Thread(target=wait_for_permit, args=(ProviderLane.ADMIN_BATCH,))
    public = threading.Thread(target=wait_for_permit, args=(ProviderLane.PUBLIC_CHAT,))
    batch.start()
    _wait_for_waiters(subject, 1)
    public.start()
    _wait_for_waiters(subject, 2)

    held.release()
    assert granted.wait(2)
    assert grants == [ProviderLane.PUBLIC_CHAT]
    release.set()
    public.join(timeout=2)
    batch.join(timeout=2)
    assert not public.is_alive()
    assert not batch.is_alive()


def test_admission_charges_public_budget_without_reserving_provider_capacity(
    tmp_path: Path,
) -> None:
    database = RuntimeDatabase(tmp_path / "runtime")
    database.initialize()
    subject = ChatLimits(
        database,
        ip_hash_key=b"fixture-key-16bytes",
        requests_per_minute=10,
        daily_budget=10,
        global_concurrency=1,
    )

    subject.admit_public_chat("203.0.113.42", now=datetime(2026, 8, 16, tzinfo=UTC))
    with subject.acquire_generation(ProviderLane.ADMIN_BATCH):
        pass

    with database.connection() as connection:
        accepted = connection.execute(
            "SELECT accepted_count FROM daily_usage WHERE usage_date = '2026-08-16'"
        ).fetchone()
    assert accepted is not None and accepted[0] == 1


def test_nonblocking_rejection_leaves_no_stale_waiter(tmp_path: Path) -> None:
    subject = _limits(tmp_path)
    held = subject.acquire_generation(ProviderLane.ADMIN_SINGLE)

    with pytest.raises(ChatLimitError) as raised:
        subject.acquire_generation(ProviderLane.ADMIN_BATCH)

    assert raised.value.code == "CONCURRENCY_LIMIT"
    held.release()
    with subject.acquire_generation(ProviderLane.PUBLIC_CHAT):
        pass
