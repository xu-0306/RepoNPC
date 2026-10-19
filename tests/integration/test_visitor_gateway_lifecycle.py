from __future__ import annotations

import asyncio
import socket
import sqlite3
from collections.abc import Callable, Coroutine
from functools import wraps
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from reponpc.api.visitor_gateway import VisitorGateway, VisitorGatewayError
from reponpc.config.environment import load_environment
from reponpc.runtime.database import MIGRATIONS, RuntimeDatabase


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
        assert snapshot["verified_at"] is None
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
async def test_dated_report_survives_bundle_and_local_readiness_changes(tmp_path: Path) -> None:
    gateway, database, _port, state, manager = make_gateway(tmp_path)
    started = await configure_and_start(gateway)
    try:
        verified = await gateway.verify(
            revision=started["revision"], external_checks_confirmed=True
        )
        state.ready = False
        manager.bundle_id = "next-bundle"
        observed = gateway.snapshot()
        assert not observed["local_ready"] and observed["external_verified"]
        assert observed["active_bundle_id"] == "next-bundle"
        assert observed["verified_at"] == verified["verified_at"]
        stopped = await gateway.stop(revision=verified["revision"])
        assert not stopped["external_verified"] and stopped["verified_at"] is None
        with database.connection() as connection:
            row = connection.execute(
                "SELECT verification_gateway_origin, verification_pages_origin, "
                "verification_bundle_id, verified_at, verification_method "
                "FROM visitor_gateway_settings WHERE id=1"
            ).fetchone()
            assert tuple(row) == (None,) * 5
        restarted = await gateway.start(revision=stopped["revision"])
        assert restarted["verified_at"] is None
        verified = await gateway.verify(
            revision=restarted["revision"], external_checks_confirmed=True
        )
        started_again = await gateway.start(revision=verified["revision"])
        assert started_again["verified_at"] is None and started_again["listener_ready"]
    finally:
        await gateway.shutdown()


@run_async
async def test_verify_rejects_unavailable_listener_and_stale_revision(tmp_path: Path) -> None:
    gateway, _database, _port, _state, _manager = make_gateway(tmp_path)
    configured = await gateway.configure(
        revision=1,
        gateway_origin="https://fixture.ts.net",
        pages_origin="https://fixture.github.io",
    )
    try:
        with pytest.raises(VisitorGatewayError) as unavailable:
            await gateway.verify(revision=configured["revision"], external_checks_confirmed=True)
        assert unavailable.value.code == "GATEWAY_UNAVAILABLE"
        with pytest.raises(VisitorGatewayError) as conflict:
            await gateway.verify(revision=1, external_checks_confirmed=True)
        assert conflict.value.code == "GATEWAY_CONFLICT"
        assert gateway.snapshot()["verified_at"] is None
    finally:
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


def test_visitor_port_migration_adds_nullable_bounded_column(tmp_path: Path) -> None:
    database = RuntimeDatabase(tmp_path / "runtime")
    database.initialize(migrations=tuple(m for m in MIGRATIONS if m.version <= 35))
    with database.connection() as connection:
        connection.execute(
            "UPDATE visitor_gateway_settings SET gateway_origin = 'https://fixture.ts.net', "
            "pages_origin = 'https://fixture.github.io' WHERE id = 1"
        )
    database.initialize()

    assert database.schema_version() == 37
    with database.connection() as connection:
        row = connection.execute(
            "SELECT gateway_origin, visitor_port FROM visitor_gateway_settings WHERE id = 1"
        ).fetchone()
        assert tuple(row) == ("https://fixture.ts.net", None)
        connection.execute("UPDATE visitor_gateway_settings SET visitor_port = 1024 WHERE id = 1")
        connection.execute("UPDATE visitor_gateway_settings SET visitor_port = 65535 WHERE id = 1")
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "UPDATE visitor_gateway_settings SET visitor_port = 1023 WHERE id = 1"
            )


@run_async
async def test_owner_visitor_port_overrides_environment_only_while_stopped(
    tmp_path: Path,
) -> None:
    gateway, _database, environment_port, _state, _manager = make_gateway(tmp_path)
    try:
        initial = gateway.snapshot()
        assert initial["visitor_port"] == environment_port
        assert initial["visitor_port_source"] == "environment"

        owner_port = free_port()
        configured = await gateway.configure(
            revision=1,
            gateway_origin="https://fixture.ts.net",
            pages_origin="https://fixture.github.io",
            visitor_port=owner_port,
        )
        assert configured["visitor_port"] == owner_port
        assert configured["visitor_port_source"] == "owner"

        started = await gateway.start(revision=configured["revision"])
        assert started["listener_ready"] and started["visitor_port"] == owner_port
        with socket.create_connection(("127.0.0.1", owner_port), timeout=2):
            pass

        with pytest.raises(VisitorGatewayError) as running:
            await gateway.configure(
                revision=started["revision"],
                gateway_origin="https://fixture.ts.net",
                pages_origin="https://fixture.github.io",
                visitor_port=free_port(),
            )
        assert running.value.code == "GATEWAY_CONFIGURATION_INVALID"

        stopped = await gateway.stop(revision=started["revision"])
        cleared = await gateway.configure(
            revision=stopped["revision"],
            gateway_origin="https://fixture.ts.net",
            pages_origin="https://fixture.github.io",
            visitor_port=None,
        )
        assert cleared["visitor_port"] == environment_port
        assert cleared["visitor_port_source"] == "environment"
    finally:
        await gateway.shutdown()


@run_async
async def test_owner_visitor_port_rejects_out_of_range_and_app_port(tmp_path: Path) -> None:
    gateway, _database, _port, _state, _manager = make_gateway(tmp_path)
    app_port = gateway._environment.port
    try:
        for invalid in (1023, 65536, app_port):
            with pytest.raises(VisitorGatewayError) as raised:
                await gateway.configure(
                    revision=1,
                    gateway_origin="https://fixture.ts.net",
                    pages_origin="https://fixture.github.io",
                    visitor_port=invalid,
                )
            assert raised.value.code == "GATEWAY_CONFIGURATION_INVALID"
        assert gateway.snapshot()["revision"] == 1
        assert gateway.snapshot()["visitor_port_source"] == "environment"
    finally:
        await gateway.shutdown()


@run_async
async def test_changing_visitor_port_clears_external_proof(tmp_path: Path) -> None:
    gateway, database, _port, _state, _manager = make_gateway(tmp_path)
    configured = await gateway.configure(
        revision=1,
        gateway_origin="https://fixture.ts.net",
        pages_origin="https://fixture.github.io",
    )
    with database.connection() as connection:
        connection.execute(
            "UPDATE visitor_gateway_settings SET verification_gateway_origin = "
            "'https://fixture.ts.net', verification_pages_origin = 'https://fixture.github.io', "
            "verification_bundle_id = 'active-bundle', verified_at = '2026-10-18T00:00:00Z', "
            "verification_method = 'owner_reported' WHERE id = 1"
        )
    changed = await gateway.configure(
        revision=configured["revision"],
        gateway_origin="https://fixture.ts.net",
        pages_origin="https://fixture.github.io",
        visitor_port=free_port(),
    )
    assert changed["verified_at"] is None
    assert changed["external_verified"] is False
    assert changed["visitor_port_source"] == "owner"
