"""Serialize live observations and scoped Funnel changes around the gateway."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from reponpc.api.visitor_gateway import VisitorGateway, VisitorGatewayError
from reponpc.tailscale.runner import (
    MAX_OUTPUT_BYTES,
    SubprocessRunner,
    TailscaleCommandError,
    TailscaleRunner,
    funnel_off_command,
    funnel_on_command,
    locate_executable,
    serve_status_command,
    status_command,
)
from reponpc.tailscale.state import (
    FunnelStatus,
    Serve,
    Status,
    choose_state,
    funnel_ports,
    own_route,
    parse_serve,
    parse_status,
)

_LOGGER = logging.getLogger("reponpc")


class TailscaleFunnelError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__("The Tailscale operation could not be completed.")


def _find_executable() -> str | None:
    return locate_executable(os.environ, sys.platform, os.path.isfile, cwd=os.getcwd())


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate Tailscale JSON field.")
        result[key] = value
    return result


def _invalid_constant(value: str) -> Any:
    raise ValueError("Invalid Tailscale JSON constant.")


@dataclass(frozen=True, slots=True)
class _Observation:
    view: FunnelStatus
    runner: TailscaleRunner | None = None
    status: Status | None = None


class TailscaleFunnelService:
    def __init__(
        self,
        *,
        profile: str,
        gateway: VisitorGateway,
        pages_origin_supplier: Callable[[], str | None],
        runner: TailscaleRunner | None = None,
        executable_supplier: Callable[[], str | None] = _find_executable,
    ) -> None:
        self.profile = profile
        self.gateway = gateway
        self._pages_origin = pages_origin_supplier
        self._runner = runner
        self._executable = executable_supplier
        self._lock = asyncio.Lock()

    async def _run(self, runner: TailscaleRunner, command: tuple[str, ...]) -> bytes:
        # A cancelled request must not release the operation lock while its CLI still runs.
        task = asyncio.create_task(asyncio.to_thread(runner.run, command))
        try:
            output = await asyncio.shield(task)
        except asyncio.CancelledError:
            await task
            raise
        if len(output) > MAX_OUTPUT_BYTES:
            raise TailscaleCommandError()
        return output

    async def _json(self, runner: TailscaleRunner, command: tuple[str, ...]) -> Any:
        output = await self._run(runner, command)
        return json.loads(
            output, object_pairs_hook=_unique_object, parse_constant=_invalid_constant
        )

    def _view(self, status: Status, serve: Serve, visitor_port: int) -> FunnelStatus:
        return choose_state(
            profile=self.profile,
            installed=True,
            status=status,
            serve=serve,
            visitor_port=visitor_port,
        )

    async def _observe(self, visitor_port: int) -> _Observation:
        if self.profile != "loopback_evaluation":
            return _Observation(FunnelStatus("unavailable_profile"))
        status = None
        try:
            executable = self._executable()
            if executable is None:
                return _Observation(FunnelStatus("not_installed"))
            runner = self._runner or SubprocessRunner(executable)
            status = parse_status(await self._json(runner, status_command()))
            serve = parse_serve(await self._json(runner, serve_status_command()))
            return _Observation(self._view(status, serve, visitor_port), runner, status)
        except TailscaleCommandError, OSError, ValueError, UnicodeError, RecursionError:
            return _Observation(FunnelStatus("error", version=status.version if status else None))

    def _event(self, view: FunnelStatus, visitor_port: int) -> None:
        _LOGGER.info(
            "tailscale_state state=%s port=%s visitor_port=%s",
            view.state,
            view.port,
            visitor_port,
            extra={"state": view.state, "port": view.port, "visitor_port": visitor_port},
        )

    async def status(self) -> dict[str, Any]:
        async with self._lock:
            if self.profile != "loopback_evaluation":
                return FunnelStatus("unavailable_profile").payload()
            visitor_port = self.gateway.snapshot()["visitor_port"]
            observation = await self._observe(visitor_port)
            self._event(observation.view, visitor_port)
            return observation.view.payload()

    def _revision(self, revision: int, gateway: dict[str, Any]) -> None:
        if type(revision) is not int or revision != gateway["revision"]:
            raise TailscaleFunnelError("GATEWAY_CONFLICT")

    def _ready(self, observation: _Observation) -> tuple[TailscaleRunner, Status, int]:
        if observation.view.state == "error":
            raise TailscaleFunnelError("TAILSCALE_FAILED")
        if observation.view.state not in {"ready", "live"}:
            raise TailscaleFunnelError("TAILSCALE_NOT_READY")
        assert observation.runner is not None and observation.status is not None
        assert observation.view.port is not None
        return observation.runner, observation.status, observation.view.port

    async def _remove(
        self, runner: TailscaleRunner, status: Status, port: int, visitor_port: int
    ) -> None:
        serve = parse_serve(await self._json(runner, serve_status_command()))
        if port not in funnel_ports(status) or not own_route(
            serve, status.dns_name.removesuffix("."), port, visitor_port
        ):
            return
        await self._run(runner, funnel_off_command(port))
        after = parse_serve(await self._json(runner, serve_status_command()))
        if own_route(after, status.dns_name.removesuffix("."), port, visitor_port):
            raise TailscaleCommandError()

    def _failure(self, exc: BaseException) -> TailscaleFunnelError:
        code = exc.code if isinstance(exc, (VisitorGatewayError, TailscaleFunnelError)) else ""
        if code not in {"GATEWAY_CONFLICT", "GATEWAY_CONFIGURATION_INVALID", "TAILSCALE_NOT_READY"}:
            code = "TAILSCALE_FAILED"
        return TailscaleFunnelError(code)

    async def start(self, revision: int) -> dict[str, Any]:
        async with self._lock:
            if self.profile != "loopback_evaluation":
                raise TailscaleFunnelError("TAILSCALE_NOT_READY")
            # Step zero deliberately precedes executable lookup and every CLI command.
            try:
                pages_origin = await asyncio.to_thread(self._pages_origin)
            except Exception:  # An unavailable saved Pages configuration must fail before CLI work.
                raise TailscaleFunnelError("GATEWAY_CONFIGURATION_INVALID") from None
            if not pages_origin:
                raise TailscaleFunnelError("GATEWAY_CONFIGURATION_INVALID")
            gateway = self.gateway.snapshot()
            self._revision(revision, gateway)
            visitor_port = gateway["visitor_port"]
            observation = await self._observe(visitor_port)
            runner, status, port = self._ready(observation)
            # Re-read immediately before any write, including a route reused by this call.
            serve = parse_serve(await self._json(runner, serve_status_command()))
            observation = _Observation(self._view(status, serve, visitor_port), runner, status)
            runner, status, port = self._ready(observation)
            matches = (
                gateway["gateway_origin"] == observation.view.funnel_url
                and gateway["pages_origin"] == pages_origin
            )
            if gateway["listener_ready"]:
                if not matches:
                    raise TailscaleFunnelError("GATEWAY_CONFIGURATION_INVALID")
                if observation.view.state == "live":
                    return {"tailscale": observation.view.payload(), "gateway": gateway}
            created = observation.view.state != "live"
            try:
                if created:
                    await self._run(runner, funnel_on_command(port, visitor_port))
                    serve = parse_serve(await self._json(runner, serve_status_command()))
                    if not own_route(serve, status.dns_name.removesuffix("."), port, visitor_port):
                        raise TailscaleCommandError()
                if not gateway["listener_ready"]:
                    configured = await self.gateway.configure(
                        revision=revision,
                        gateway_origin=observation.view.funnel_url,
                        pages_origin=pages_origin,
                    )
                    gateway = await self.gateway.start(revision=configured["revision"])
                live = self._view(status, serve, visitor_port)
                self._event(live, visitor_port)
                return {"tailscale": live.payload(), "gateway": gateway}
            except (Exception, asyncio.CancelledError) as exc:
                # Any downstream failure must roll back only this call's still-owned route.
                if created:
                    try:
                        await self._remove(runner, status, port, visitor_port)
                    # Failed ownership verification must never trigger a blind off.
                    except Exception:
                        self._event(FunnelStatus("error", port=port), visitor_port)
                        raise TailscaleFunnelError("TAILSCALE_FAILED") from None
                if isinstance(exc, asyncio.CancelledError):
                    raise
                raise self._failure(exc) from None

    async def stop(self, revision: int) -> dict[str, Any]:
        async with self._lock:
            if self.profile != "loopback_evaluation":
                raise TailscaleFunnelError("TAILSCALE_NOT_READY")
            gateway = self.gateway.snapshot()
            self._revision(revision, gateway)
            visitor_port = gateway["visitor_port"]
            observation = await self._observe(visitor_port)
            try:
                gateway = await self.gateway.stop(revision=revision)
                if observation.view.state == "live":
                    runner, status, port = self._ready(observation)
                    await self._remove(runner, status, port, visitor_port)
                    observation = await self._observe(visitor_port)
                if observation.view.state == "error":
                    raise TailscaleFunnelError("TAILSCALE_FAILED")
                # Owner decision 2026-11-06: off also forgets the saved addresses, so the
                # README step and the next export read "live chat off". Only after the
                # route is confirmed off, so a failed removal can be retried as it was.
                if gateway["gateway_origin"] is not None or gateway["pages_origin"] is not None:
                    gateway = await self.gateway.configure(
                        revision=gateway["revision"], gateway_origin=None, pages_origin=None
                    )
                self._event(observation.view, visitor_port)
                return {"tailscale": observation.view.payload(), "gateway": gateway}
            # Never return upstream or gateway exception text.
            except Exception as exc:
                raise self._failure(exc) from None
