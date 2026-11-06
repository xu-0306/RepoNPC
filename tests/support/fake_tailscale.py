"""Synthetic CLI state, reloaded for every call; never invokes a process."""

from __future__ import annotations

import json
import threading
from copy import deepcopy
from pathlib import Path
from typing import Any

from reponpc.tailscale.runner import (
    TailscaleCommandError,
    funnel_off_command,
    funnel_on_command,
    serve_status_command,
    status_command,
)

FIXTURE = Path(__file__).parents[1] / "fixtures" / "tailscale" / "ready.json"
HOST = "fixture-host.tailnet-fixture.ts.net"
VISITOR_PORT = 8882


def fixture_state() -> dict[str, Any]:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def add_route(
    serve: dict[str, Any],
    port: int,
    *,
    visitor_port: int = VISITOR_PORT,
    host: str = HOST,
    funnel: bool = True,
) -> None:
    serve["TCP"][str(port)] = {"HTTPS": True}
    serve["Web"][f"{host}:{port}"] = {
        "Handlers": {"/": {"Proxy": f"http://127.0.0.1:{visitor_port}"}}
    }
    serve["AllowFunnel"][f"{host}:{port}"] = funnel


class FakeTailscaleRunner:
    def __init__(
        self,
        state: dict[str, Any] | None = None,
        *,
        state_file: Path | None = None,
        events: list[Any] | None = None,
    ) -> None:
        self.state = deepcopy(state) if state is not None else fixture_state()
        self.state_file = state_file
        self.calls: list[tuple[str, ...]] = []
        self.events = events if events is not None else []
        self._lock = threading.Lock()

    def run(self, command: tuple[str, ...]) -> bytes:
        with self._lock:
            if self.state_file is not None:
                self.state = json.loads(self.state_file.read_text(encoding="utf-8"))
            self.calls.append(command)
            self.events.append(command)
            failure = self.state.get("failure")
            if failure == "timeout":
                raise TailscaleCommandError()
            if failure == "invalid_json":
                return b"CANARY-CLI-PRIVATE"
            if failure == "oversize":
                return b"CANARY-CLI-PRIVATE" + b"x" * (1024 * 1024)
            if command == status_command():
                return json.dumps(self.state["status"]).encode()
            if command == serve_status_command():
                return json.dumps(self.state["serve"]).encode()
            serve = self.state["serve"]
            if len(command) == 5:
                port = int(command[3].removeprefix("--https="))
                visitor = int(command[4].removeprefix("http://127.0.0.1:"))
                assert command == funnel_on_command(port, visitor)
                if not self.state.get("ignore_on"):
                    add_route(serve, port, visitor_port=visitor)
            elif len(command) == 4:
                port = int(command[2].removeprefix("--https="))
                assert command == funnel_off_command(port)
                serve["TCP"].pop(str(port), None)
                serve["Web"].pop(f"{HOST}:{port}", None)
                serve["AllowFunnel"].pop(f"{HOST}:{port}", None)
            else:
                raise AssertionError(f"Unexpected synthetic command: {command!r}")
            if self.state_file is not None:
                self.state_file.write_text(json.dumps(self.state), encoding="utf-8", newline="\n")
            return b"CANARY-CLI-PRIVATE"
