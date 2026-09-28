from __future__ import annotations

import asyncio
import socket
from collections.abc import Callable, Coroutine
from functools import wraps
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from reponpc.api.visitor_gateway import VisitorGateway, VisitorGatewayError
from reponpc.config.environment import load_environment
from reponpc.runtime.database import RuntimeDatabase


class BundleManager:
    def __init__(self, bundle_id: str | None = "active-bundle") -> None:
        self.bundle_id = bundle_id
        self.fail = False

    def status(self) -> SimpleNamespace:
        if self.fail:
            raise RuntimeError("private bundle manager failure")
        return SimpleNamespace(active_bundle_id=self.bundle_id)


def run_async(function: Callable[..., Coroutine[Any, Any, None]]) -> Callable[..., None]:
    @wraps(function)
    def wrapped(*args: Any, **kwargs: Any) -> None:
        asyncio.run(function(*args, **kwargs))

    return wrapped


def free_port() -> int:
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


def make_gateway(
    tmp_path: Path,
    *,
    port: int | None = None,
    state: SimpleNamespace | None = None,
    manager: BundleManager | None = None,
    database: RuntimeDatabase | None = None,
) -> tuple[VisitorGateway, RuntimeDatabase, int, SimpleNamespace, BundleManager]:
    actual_port = port if port is not None else free_port()
    actual_state = state or SimpleNamespace(ready=True, index_version="stale-state-bundle")
    actual_manager = manager or BundleManager()
    environment = load_environment(
        {
            "REPONPC_PUBLIC_BASE_URL": "https://private.example.com",
            "REPONPC_ADMIN_ORIGINS": "https://private.example.com",
            "REPONPC_CONFIG_REPOSITORY": "example/fixture",
            "REPONPC_INDEX_MANIFEST_URL": "http://127.0.0.1:9/disabled",
            "REPONPC_VISITOR_GATEWAY_PORT": str(actual_port),
            "REPONPC_SHUTDOWN_GRACE_SECONDS": "1",
        },
        secret_roots=(tmp_path,),
    )
    actual_database = database or RuntimeDatabase(tmp_path / "runtime")
    actual_database.initialize()
    gateway = VisitorGateway(
        database=actual_database,
        environment=environment,
        state_supplier=lambda: actual_state,
        bundle_manager_supplier=lambda: actual_manager,
        chat_service_supplier=lambda: None,
        faq_supplier=lambda: None,
        web_dist=tmp_path / "missing-web",
    )
    return gateway, actual_database, actual_port, actual_state, actual_manager


async def configure_and_start(gateway: VisitorGateway) -> dict[str, Any]:
    configured = await gateway.configure(
        revision=1,
        gateway_origin="https://fixture.ts.net",
        pages_origin="https://fixture.github.io",
    )
    return await gateway.start(revision=configured["revision"])


@run_async
async def test_enabled_intent_resumes_listener_without_restoring_external_proof(
    tmp_path: Path,
) -> None:
    gateway, database, _port, _state, _manager = make_gateway(tmp_path)
    started = await configure_and_start(gateway)
    verified = await gateway.verify(
        revision=started["revision"],
        gateway_origin="https://fixture.ts.net",
        pages_origin="https://fixture.github.io",
        bundle_id="active-bundle",
        external_checks_confirmed=True,
    )
    assert verified["external_verified"]
    await gateway.shutdown()

    restored_data_dir = tmp_path / "restored-backup"
    restored_data_dir.mkdir()
    restored_database_path = restored_data_dir / "runtime.sqlite"
    database.backup_to(restored_database_path)
    resumed, _database, _port, _state, _manager = make_gateway(
        restored_data_dir,
        port=gateway._environment.visitor_gateway_port,
        database=RuntimeDatabase(restored_data_dir),
    )
    try:
        snapshot = await resumed.resume()
        assert snapshot["enabled"] and snapshot["listener_ready"]
        assert not snapshot["external_verified"]
        assert snapshot["verified_at"] == verified["verified_at"]
        stopped = await resumed.stop(revision=snapshot["revision"])
        assert not stopped["enabled"] and not stopped["listener_ready"]
    finally:
        await resumed.shutdown()


@run_async
async def test_busy_loopback_port_keeps_private_service_available_and_intent_visible(
    tmp_path: Path,
) -> None:
    with socket.socket() as occupied:
        occupied.bind(("127.0.0.1", 0))
        occupied.listen(1)
        port = int(occupied.getsockname()[1])
        gateway, _database, _port, _state, _manager = make_gateway(tmp_path, port=port)
        configured = await gateway.configure(
            revision=1,
            gateway_origin="https://fixture.ts.net",
            pages_origin="https://fixture.github.io",
        )
        with pytest.raises(VisitorGatewayError) as raised:
            await gateway.start(revision=configured["revision"])
        assert raised.value.code == "GATEWAY_UNAVAILABLE"
        snapshot = gateway.snapshot()
        assert snapshot["enabled"] and not snapshot["listener_ready"]
        stopped = await gateway.stop(revision=snapshot["revision"])
        assert not stopped["enabled"]
        await gateway.shutdown()


@run_async
async def test_observed_readiness_and_bundle_changes_invalidate_owner_report(
    tmp_path: Path,
) -> None:
    gateway, _database, _port, state, manager = make_gateway(tmp_path)
    started = await configure_and_start(gateway)
    verified = await gateway.verify(
        revision=started["revision"],
        gateway_origin="https://fixture.ts.net",
        pages_origin="https://fixture.github.io",
        bundle_id="active-bundle",
        external_checks_confirmed=True,
    )
    assert verified["external_verified"]

    state.ready = False
    gateway.observe_state()
    state.ready = True
    gateway.observe_state()
    after_recovery = gateway.snapshot()
    assert not after_recovery["external_verified"]
    assert after_recovery["verified_at"] == verified["verified_at"]

    verified_again = await gateway.verify(
        revision=after_recovery["revision"],
        gateway_origin="https://fixture.ts.net",
        pages_origin="https://fixture.github.io",
        bundle_id="active-bundle",
        external_checks_confirmed=True,
    )
    assert verified_again["external_verified"]
    manager.bundle_id = "next-bundle"
    gateway.observe_state()
    assert not gateway.snapshot()["external_verified"]
    await gateway.shutdown()


@run_async
async def test_readiness_change_during_report_save_leaves_report_unverified(
    tmp_path: Path,
) -> None:
    gateway, _database, _port, state, _manager = make_gateway(tmp_path)
    started = await configure_and_start(gateway)
    original_verify = gateway._store.verify

    def save_while_readiness_changes(**values: Any) -> Any:
        result = original_verify(**values)
        state.ready = False
        gateway.observe_state()
        state.ready = True
        gateway.observe_state()
        return result

    gateway._store.verify = save_while_readiness_changes  # type: ignore[method-assign]
    with pytest.raises(VisitorGatewayError) as raised:
        await gateway.verify(
            revision=started["revision"],
            gateway_origin="https://fixture.ts.net",
            pages_origin="https://fixture.github.io",
            bundle_id="active-bundle",
            external_checks_confirmed=True,
        )
    assert raised.value.code == "GATEWAY_VERIFICATION_STALE"
    snapshot = gateway.snapshot()
    assert not snapshot["external_verified"]
    assert snapshot["verified_at"] is not None
    await gateway.shutdown()


def test_bundle_manager_failure_does_not_fall_back_to_stale_setup_state(
    tmp_path: Path,
) -> None:
    manager = BundleManager()
    manager.fail = True
    gateway, _database, _port, _state, _manager = make_gateway(
        tmp_path,
        state=SimpleNamespace(ready=True, index_version="stale-state-bundle"),
        manager=manager,
    )

    snapshot = gateway.snapshot()

    assert snapshot["local_ready"] is False
    assert snapshot["active_bundle_id"] is None
