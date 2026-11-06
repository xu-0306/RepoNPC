"""Ordered operations and rollback without real CLI calls or listeners."""

from __future__ import annotations

import asyncio
import threading
import time
from copy import deepcopy

import pytest

from reponpc.api.visitor_gateway import VisitorGatewayError
from reponpc.tailscale.runner import (
    TailscaleCommandError,
    funnel_off_command,
    funnel_on_command,
    serve_status_command,
    status_command,
)
from reponpc.tailscale.service import TailscaleFunnelError, TailscaleFunnelService
from tests.support.fake_tailscale import HOST, VISITOR_PORT, FakeTailscaleRunner, add_route

pytestmark = pytest.mark.usefixtures("reponpc_logger")


class Gateway:
    def __init__(self, events=None):
        self.events = events if events is not None else []
        self.value = {
            "revision": 1,
            "gateway_origin": None,
            "pages_origin": None,
            "enabled": False,
            "listener_ready": False,
            "error_code": None,
            "local_ready": True,
            "entry_configured": False,
            "external_verified": False,
            "verified_at": None,
            "verification_method": None,
            "active_bundle_id": "fixture",
            "client_identity_mode": "aggregate",
            "visitor_port": VISITOR_PORT,
            "visitor_port_source": "environment",
        }
        self.failure = None

    def snapshot(self):
        return self.value.copy()

    async def configure(self, *, revision, gateway_origin, pages_origin):
        self.events.append(("configure", revision, gateway_origin, pages_origin))
        assert revision == self.value["revision"]
        if self.failure == "configure":
            raise VisitorGatewayError("GATEWAY_CONFIGURATION_INVALID")
        self.value.update(
            revision=revision + 1, gateway_origin=gateway_origin, pages_origin=pages_origin
        )
        return self.snapshot()

    async def start(self, *, revision):
        self.events.append(("start", revision))
        assert revision == self.value["revision"]
        if self.failure == "start":
            raise VisitorGatewayError("GATEWAY_UNAVAILABLE")
        self.value.update(revision=revision + 1, listener_ready=True, enabled=True)
        return self.snapshot()

    async def stop(self, *, revision):
        self.events.append(("stop", revision))
        assert revision == self.value["revision"]
        if self.failure == "stop":
            raise VisitorGatewayError("GATEWAY_UNAVAILABLE")
        self.value.update(
            revision=revision + int(self.value["enabled"]), listener_ready=False, enabled=False
        )
        return self.snapshot()


def system(
    *,
    profile="loopback_evaluation",
    pages="https://fixture.github.io",
    executable="/fixture/tailscale.exe",
):
    events = []
    runner = FakeTailscaleRunner(events=events)
    gateway = Gateway(events)

    def origin():
        events.append("pages")
        return pages

    service = TailscaleFunnelService(
        profile=profile,
        gateway=gateway,
        pages_origin_supplier=origin,
        runner=runner,
        executable_supplier=lambda: executable,
    )
    return service, runner, gateway, events


def test_start_order_revisions_and_idempotency():
    service, runner, _gateway, events = system()

    async def exercise():
        first = await service.start(1)
        assert first["tailscale"]["state"] == "live"
        assert first["gateway"]["gateway_origin"] == f"https://{HOST}"
        assert first["gateway"]["revision"] == 3
        assert events == [
            "pages",
            status_command(),
            serve_status_command(),
            serve_status_command(),
            funnel_on_command(443, VISITOR_PORT),
            serve_status_command(),
            ("configure", 1, f"https://{HOST}", "https://fixture.github.io"),
            ("start", 2),
        ]
        writes = runner.calls.count(funnel_on_command(443, VISITOR_PORT))
        events.clear()
        second = await service.start(first["gateway"]["revision"])
        third = await service.start(first["gateway"]["revision"])
        assert second == third == first
        assert runner.calls.count(funnel_on_command(443, VISITOR_PORT)) == writes
        assert not any(isinstance(event, tuple) and event[0] == "configure" for event in events)

    asyncio.run(exercise())


@pytest.mark.parametrize("pages", [None, ""])
def test_pages_origin_is_step_zero(pages):
    service, runner, _gateway, events = system(pages=pages)
    with pytest.raises(TailscaleFunnelError) as raised:
        asyncio.run(service.start(1))
    assert raised.value.code == "GATEWAY_CONFIGURATION_INVALID"
    assert events == ["pages"]
    assert runner.calls == []


@pytest.mark.parametrize("failure", ["configure", "start"])
@pytest.mark.parametrize("reused", [False, True])
def test_failure_rolls_back_only_route_created_by_this_call(failure, reused):
    service, runner, gateway, _events = system()
    gateway.failure = failure
    if reused:
        add_route(runner.state["serve"], 443)
    before = deepcopy(runner.state["serve"])
    with pytest.raises(TailscaleFunnelError) as raised:
        asyncio.run(service.start(1))
    assert raised.value.code == (
        "GATEWAY_CONFIGURATION_INVALID" if failure == "configure" else "TAILSCALE_FAILED"
    )
    assert (funnel_off_command(443) in runner.calls) is not reused
    assert runner.state["serve"] == before


def test_confirmation_failure_does_not_blindly_remove_a_route():
    service, runner, _gateway, _events = system()
    runner.state["ignore_on"] = True
    with pytest.raises(TailscaleFunnelError) as raised:
        asyncio.run(service.start(1))
    assert raised.value.code == "TAILSCALE_FAILED"
    assert funnel_off_command(443) not in runner.calls


@pytest.mark.parametrize("action", ["start", "stop"])
def test_revision_conflict_has_no_commands(action):
    service, runner, _gateway, _events = system()
    with pytest.raises(TailscaleFunnelError) as raised:
        asyncio.run(getattr(service, action)(2))
    assert raised.value.code == "GATEWAY_CONFLICT"
    assert runner.calls == []


def test_running_different_configuration_leaves_routes_unchanged():
    service, runner, gateway, _events = system()
    gateway.value.update(listener_ready=True, enabled=True, gateway_origin="https://other.ts.net")
    with pytest.raises(TailscaleFunnelError) as raised:
        asyncio.run(service.start(1))
    assert raised.value.code == "GATEWAY_CONFIGURATION_INVALID"
    assert all(command[1] != "funnel" for command in runner.calls)


def test_every_port_foreign_is_not_ready_and_stop_does_not_touch_routes():
    service, runner, _gateway, _events = system()
    for port in (443, 8443, 10000):
        add_route(runner.state["serve"], port, visitor_port=8883)
    before = deepcopy(runner.state["serve"])
    with pytest.raises(TailscaleFunnelError) as raised:
        asyncio.run(service.start(1))
    assert raised.value.code == "TAILSCALE_NOT_READY"
    result = asyncio.run(service.stop(1))
    assert result["tailscale"]["state"] == "no_free_port"
    assert runner.state["serve"] == before
    assert all(command[1] != "funnel" for command in runner.calls)


def test_stop_gateway_before_scoped_off_and_preserve_foreign_routes():
    service, runner, _gateway, events = system()
    add_route(runner.state["serve"], 443, visitor_port=8883)
    add_route(runner.state["serve"], 8443)
    foreign = deepcopy(runner.state["serve"]["Web"][f"{HOST}:443"])
    result = asyncio.run(service.stop(1))
    assert result["tailscale"]["state"] == "ready"
    assert result["tailscale"]["port"] == 8443
    assert events.index(("stop", 1)) < events.index(funnel_off_command(8443))
    assert runner.state["serve"]["Web"][f"{HOST}:443"] == foreign
    assert funnel_off_command(443) not in runner.calls


def test_stop_clears_saved_addresses_only_after_the_scoped_off():
    service, runner, gateway, events = system()

    async def exercise():
        started = await service.start(1)
        assert started["gateway"]["gateway_origin"] == f"https://{HOST}"
        events.clear()
        stopped = await service.stop(started["gateway"]["revision"])
        # Start left revision 3 (configure 1->2, start 2->3); stop bumps to 4; clear bumps to 5.
        assert events.index(("stop", 3)) < events.index(funnel_off_command(443))
        assert events.index(funnel_off_command(443)) < events.index(("configure", 4, None, None))
        assert stopped["tailscale"]["state"] == "ready"
        assert stopped["gateway"]["gateway_origin"] is None
        assert stopped["gateway"]["pages_origin"] is None
        assert stopped["gateway"]["enabled"] is False
        assert stopped["gateway"]["revision"] == 5

    asyncio.run(exercise())
    assert gateway.value["gateway_origin"] is None
    assert gateway.value["pages_origin"] is None
    assert f"{HOST}:443" not in runner.state["serve"]["Web"]


def test_stop_with_nothing_live_still_clears_saved_addresses_and_runs_no_off():
    service, runner, gateway, events = system()
    gateway.value.update(gateway_origin=f"https://{HOST}", pages_origin="https://fixture.github.io")
    result = asyncio.run(service.stop(1))
    assert ("configure", 1, None, None) in events
    assert result["gateway"]["gateway_origin"] is None
    assert result["gateway"]["pages_origin"] is None
    assert all(command[1] != "funnel" for command in runner.calls)


def test_stop_without_saved_addresses_does_not_reconfigure():
    service, _runner, _gateway, events = system()
    asyncio.run(service.stop(1))
    assert not any(isinstance(event, tuple) and event[0] == "configure" for event in events)


def test_failed_scoped_off_keeps_saved_addresses_so_stop_can_be_retried():
    service, runner, gateway, events = system()
    asyncio.run(service.start(1))
    original = runner.run

    def refuse_off(command):
        if command == funnel_off_command(443):
            raise TailscaleCommandError()
        return original(command)

    runner.run = refuse_off
    events.clear()
    with pytest.raises(TailscaleFunnelError) as raised:
        asyncio.run(service.stop(3))
    assert raised.value.code == "TAILSCALE_FAILED"
    assert not any(isinstance(event, tuple) and event[0] == "configure" for event in events)
    assert gateway.value["gateway_origin"] == f"https://{HOST}"
    assert gateway.value["pages_origin"] == "https://fixture.github.io"


@pytest.mark.parametrize("profile", ["production", "unknown"])
def test_unavailable_profile_never_even_looks_for_executable(profile):
    service, runner, _gateway, events = system(profile=profile)

    def forbidden():
        pytest.fail("Unavailable profile looked for a CLI executable")

    service._executable = forbidden
    assert asyncio.run(service.status())["state"] == "unavailable_profile"
    for action in (service.start, service.stop):
        with pytest.raises(TailscaleFunnelError) as raised:
            asyncio.run(action(1))
        assert raised.value.code == "TAILSCALE_NOT_READY"
    assert runner.calls == events == []


@pytest.mark.parametrize("failure", ["timeout", "invalid_json", "oversize"])
def test_command_failures_become_error_status_and_failed_start(failure):
    service, runner, _gateway, _events = system()
    runner.state["failure"] = failure
    assert asyncio.run(service.status())["state"] == "error"
    with pytest.raises(TailscaleFunnelError) as raised:
        asyncio.run(service.start(1))
    assert raised.value.code == "TAILSCALE_FAILED"


def test_start_rechecks_ports_before_writing():
    service, runner, _gateway, _events = system()
    original = runner.run
    reads = 0

    def changed(command):
        nonlocal reads
        if command == serve_status_command():
            reads += 1
            if reads == 2:
                add_route(runner.state["serve"], 443, visitor_port=8883)
        return original(command)

    runner.run = changed
    result = asyncio.run(service.start(1))
    assert result["tailscale"]["port"] == 8443
    assert funnel_on_command(443, VISITOR_PORT) not in runner.calls
    assert funnel_on_command(8443, VISITOR_PORT) in runner.calls
    assert (
        runner.state["serve"]["Web"][f"{HOST}:443"]["Handlers"]["/"]["Proxy"]
        == "http://127.0.0.1:8883"
    )


@pytest.mark.parametrize("phase", ["rollback", "stop"])
def test_route_changed_before_off_is_never_removed(phase):
    service, runner, gateway, _events = system()
    add_route(runner.state["serve"], 443)

    async def change(**kwargs):
        add_route(runner.state["serve"], 443, visitor_port=8883)
        if phase == "rollback":
            raise VisitorGatewayError("GATEWAY_UNAVAILABLE")
        return gateway.snapshot()

    if phase == "rollback":
        runner.state["serve"] = {"TCP": {}, "Web": {}, "AllowFunnel": {}}
        gateway.start = change
        with pytest.raises(TailscaleFunnelError) as raised:
            asyncio.run(service.start(1))
        assert raised.value.code == "TAILSCALE_FAILED"
    else:
        gateway.stop = change
        asyncio.run(service.stop(1))
    assert funnel_off_command(443) not in runner.calls
    assert (
        runner.state["serve"]["Web"][f"{HOST}:443"]["Handlers"]["/"]["Proxy"]
        == "http://127.0.0.1:8883"
    )


def test_operations_are_serialized_and_runner_is_off_event_loop():
    service, runner, _gateway, _events = system()
    original = runner.run
    threads = []

    def observed(command):
        threads.append(threading.get_ident())
        time.sleep(0.001)
        return original(command)

    runner.run = observed

    async def exercise():
        results = await asyncio.gather(service.status(), service.status(), service.stop(1))
        assert results[0]["state"] == results[1]["state"] == "ready"
        assert results[2]["tailscale"]["state"] == "ready"

    asyncio.run(exercise())
    assert threads and all(thread != threading.get_ident() for thread in threads)
    assert runner.calls == [status_command(), serve_status_command()] * 3


def test_cancelled_start_waits_for_cli_then_rolls_back_before_unlocking():
    service, runner, _gateway, _events = system()
    original = runner.run
    entered, release = threading.Event(), threading.Event()

    def blocked(command):
        if command == funnel_on_command(443, VISITOR_PORT):
            entered.set()
            assert release.wait(5), "Test did not release the scripted Funnel command"
        return original(command)

    runner.run = blocked

    async def exercise():
        start = asyncio.create_task(service.start(1))
        try:
            assert await asyncio.to_thread(entered.wait, 5)
            start.cancel()
            status = asyncio.create_task(service.status())
            await asyncio.sleep(0)
            assert not status.done()
            release.set()
            with pytest.raises(asyncio.CancelledError):
                await start
            assert (await status)["state"] == "ready"
        finally:
            release.set()

    asyncio.run(exercise())
    assert runner.state["serve"] == {"TCP": {}, "Web": {}, "AllowFunnel": {}}
    assert runner.calls.index(funnel_off_command(443)) < len(runner.calls) - 2


@pytest.mark.parametrize(
    "output",
    [
        b'{"Version":"1.104.4","Version":"1.104.5"}',
        b'{"Self":NaN}',
        b"[" * 2000 + b"]" * 2000,
        b"\xff",
    ],
)
def test_malformed_json_is_error_without_exception_text(output):
    service, runner, _gateway, _events = system()
    runner.run = lambda _command: output
    result = asyncio.run(service.status())
    assert result == {"state": "error", "funnel_url": None, "port": None, "version": None}
