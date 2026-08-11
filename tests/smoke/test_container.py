from __future__ import annotations

import os
import shutil
import subprocess
import time
from pathlib import Path
from uuid import uuid4

import httpx
import pytest

ROOT = Path(__file__).resolve().parents[2]


def find_docker_executable() -> str | None:
    """Find Docker Desktop when the test runner intentionally sanitizes PATH."""

    candidates = [os.environ.get("REPONPC_DOCKER_EXECUTABLE"), shutil.which("docker")]
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        candidates.append(
            str(Path(local_app_data) / "Programs/DockerDesktop/resources/bin/docker.exe")
        )
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return candidate
    return None


DOCKER_EXECUTABLE = find_docker_executable()
pytestmark = pytest.mark.skipif(
    DOCKER_EXECUTABLE is None, reason="docker executable is unavailable"
)


def compose(project_name: str, *arguments: str) -> subprocess.CompletedProcess[str]:
    if DOCKER_EXECUTABLE is None:
        raise RuntimeError("docker executable is unavailable")
    return subprocess.run(
        [
            DOCKER_EXECUTABLE,
            "compose",
            "--project-name",
            project_name,
            "--file",
            "compose.yml",
            *arguments,
        ],
        cwd=ROOT,
        env={
            **os.environ,
            "PATH": f"{Path(DOCKER_EXECUTABLE).parent}{os.pathsep}{os.environ.get('PATH', '')}",
            "REPONPC_HOST_PORT": "18080",
        },
        check=True,
        text=True,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
    )


def wait_for_health() -> httpx.Response:
    deadline = time.monotonic() + 90
    while time.monotonic() < deadline:
        try:
            health = httpx.get("http://127.0.0.1:18080/healthz", timeout=2)
        except httpx.HTTPError:
            time.sleep(1)
            continue
        if health.status_code == 200:
            return health
        time.sleep(1)
    pytest.fail("container did not become healthy")


def test_compose_container_health_and_runtime_volume_survive_restart() -> None:
    project_name = f"reponpc-p2-{uuid4().hex[:12]}"
    try:
        compose(project_name, "up", "--build", "--detach")
        health = wait_for_health()
        assert health.json() == {"status": "alive"}
        status = httpx.get("http://127.0.0.1:18080/api/public/status", timeout=2)
        assert status.status_code == 200
        assert status.json()["status"] == "setup_required"
        marker = uuid4().hex
        marker_path = "/var/lib/reponpc/.p2-smoke-volume-marker"
        compose(
            project_name,
            "exec",
            "-T",
            "app",
            "python",
            "-c",
            "from pathlib import Path; "
            f"Path({marker_path!r}).write_text({marker!r}, encoding='utf-8')",
        )
        compose(project_name, "restart", "app")
        restarted = wait_for_health()
        assert restarted.status_code == 200
        compose(
            project_name,
            "exec",
            "-T",
            "app",
            "python",
            "-c",
            "from pathlib import Path; "
            f"assert Path({marker_path!r}).read_text(encoding='utf-8') == {marker!r}",
        )
    finally:
        compose(project_name, "down", "--volumes", "--remove-orphans")
