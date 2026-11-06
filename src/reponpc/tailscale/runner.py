"""Fixed CLI arguments and an injectable, bounded subprocess boundary."""

from __future__ import annotations

import ntpath
import os
import posixpath
import subprocess
import sys
from collections.abc import Callable, Mapping
from typing import Protocol

MAX_OUTPUT_BYTES = 1024 * 1024


class TailscaleCommandError(RuntimeError):
    def __init__(self) -> None:
        super().__init__("The Tailscale command could not be completed.")


def locate_executable(
    environment: Mapping[str, str],
    platform: str,
    is_file: Callable[[str], bool],
    *,
    cwd: str | None = None,
) -> str | None:
    """Use explicit absolute search roots; never use shell executable lookup."""
    windows = platform == "win32"
    path = ntpath if windows else posixpath
    values = {key.upper(): value for key, value in environment.items()}
    name = "tailscale.exe" if windows else "tailscale"
    roots = values.get("PATH", "").split(";" if windows else ":")
    candidates = [path.join(root, name) for root in roots if path.isabs(root)]
    program_files = values.get("PROGRAMFILES", "")
    if windows and ntpath.isabs(program_files):
        candidates.append(ntpath.join(program_files, "Tailscale", "tailscale.exe"))
    if not windows:
        candidates.extend(
            (
                "/Applications/Tailscale.app/Contents/MacOS/Tailscale",
                "/usr/bin/tailscale",
                "/usr/local/bin/tailscale",
            )
        )
    for candidate in candidates:
        if windows and (not ntpath.splitdrive(candidate)[0] or not candidate.endswith(".exe")):
            continue
        if cwd is not None and path.normcase(
            path.normpath(path.dirname(candidate))
        ) == path.normcase(path.normpath(cwd)):
            continue
        if is_file(candidate):
            return candidate
    return None


def _port(value: int, minimum: int = 1) -> int:
    if type(value) is not int or not minimum <= value <= 65535:
        raise ValueError("Invalid Tailscale port.")
    return value


def status_command() -> tuple[str, ...]:
    return ("tailscale", "status", "--json")


def serve_status_command() -> tuple[str, ...]:
    return ("tailscale", "serve", "status", "--json")


def funnel_on_command(port: int, visitor_port: int) -> tuple[str, ...]:
    return (
        "tailscale",
        "funnel",
        "--bg",
        f"--https={_port(port)}",
        f"http://127.0.0.1:{_port(visitor_port, 1024)}",
    )


def funnel_off_command(port: int) -> tuple[str, ...]:
    return ("tailscale", "funnel", f"--https={_port(port)}", "off")


def _timeout(command: tuple[str, ...]) -> int:
    if command in (status_command(), serve_status_command()):
        return 10
    try:
        if len(command) == 5:
            port = int(command[3].removeprefix("--https="))
            visitor = int(command[4].removeprefix("http://127.0.0.1:"))
            if command == funnel_on_command(port, visitor):
                return 30
        if len(command) == 4:
            port = int(command[2].removeprefix("--https="))
            if command == funnel_off_command(port):
                return 30
    except ValueError:
        raise TailscaleCommandError() from None
    raise TailscaleCommandError()


class TailscaleRunner(Protocol):
    def run(self, command: tuple[str, ...]) -> bytes: ...


class SubprocessRunner:
    def __init__(
        self,
        executable: str,
        *,
        environment: Mapping[str, str] | None = None,
        platform: str = sys.platform,
    ) -> None:
        self.executable = executable
        self.platform = platform
        # Keep OS/daemon discovery essentials, excluding proxy, CLI and loader overrides.
        allowed = {
            "SYSTEMROOT",
            "WINDIR",
            "TEMP",
            "TMP",
            "HOME",
            "USERPROFILE",
            "HOMEDRIVE",
            "HOMEPATH",
            "LOCALAPPDATA",
            "PROGRAMDATA",
        }
        self.environment = {
            key: value
            for key, value in (os.environ if environment is None else environment).items()
            if key.upper() in allowed
        }

    def run(self, command: tuple[str, ...]) -> bytes:
        timeout = _timeout(command)
        creationflags = subprocess.CREATE_NO_WINDOW if self.platform == "win32" else 0
        try:
            result = subprocess.run(
                [self.executable, *command[1:]],
                shell=False,
                capture_output=True,
                timeout=timeout,
                env=self.environment,
                stdin=subprocess.DEVNULL,
                creationflags=creationflags,
            )
        except OSError, subprocess.TimeoutExpired:
            raise TailscaleCommandError() from None
        if result.returncode != 0 or len(result.stdout) + len(result.stderr) > MAX_OUTPUT_BYTES:
            raise TailscaleCommandError()
        return result.stdout
