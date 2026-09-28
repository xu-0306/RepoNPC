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


def compose(
    project_name: str, environment_file: Path, *arguments: str
) -> subprocess.CompletedProcess[str]:
    if DOCKER_EXECUTABLE is None:
        raise RuntimeError("docker executable is unavailable")
    return subprocess.run(
        [
            DOCKER_EXECUTABLE,
            "compose",
            "--env-file",
            str(environment_file),
            "--project-name",
            project_name,
            "--file",
            "compose.yml",
            *arguments,
        ],
        cwd=ROOT,
        env={
            **{
                name: value
                for name, value in os.environ.items()
                if not name.upper().startswith("REPONPC_")
            },
            "PATH": f"{Path(DOCKER_EXECUTABLE).parent}{os.pathsep}{os.environ.get('PATH', '')}",
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


def test_compose_container_health_and_runtime_volume_survive_restart(tmp_path: Path) -> None:
    project_name = f"reponpc-p2-{uuid4().hex[:12]}"
    environment_file = tmp_path / "synthetic.env"
    environment_file.write_text(
        "\n".join(
            (
                "REPONPC_ENV=production",
                "REPONPC_DEPLOYMENT_PROFILE=production",
                "REPONPC_PUBLIC_BASE_URL=http://127.0.0.1:18080",
                "REPONPC_HOST_PORT=18080",
                "REPONPC_TRUSTED_HOSTS=127.0.0.1,localhost",
                "REPONPC_ADMIN_ORIGINS=http://127.0.0.1:18080",
                "REPONPC_CONFIG_REPOSITORY=example/fixture",
                "REPONPC_INDEX_MANIFEST_URL=https://raw.githubusercontent.com/example/fixture/main/disabled.json",
                "REPONPC_GITHUB_TOKEN=",
                "REPONPC_GITHUB_TOKEN_FILE=",
                "REPONPC_CHAT_PROVIDER=",
                "REPONPC_CHAT_MODEL=",
                "REPONPC_CHAT_BASE_URL=",
                "REPONPC_CHAT_API_KEY=",
                "REPONPC_EMBEDDING_PROVIDER=",
                "REPONPC_EMBEDDING_MODEL=",
                "REPONPC_EMBEDDING_BASE_URL=",
                "REPONPC_EMBEDDING_API_KEY=",
            )
        )
        + "\n",
        encoding="utf-8",
    )
    try:
        # The existing local-source marker disables immutable remote discovery.
        # Seed only this test's new volume before starting the normal entrypoint.
        compose(
            project_name,
            environment_file,
            "run",
            "--build",
            "--rm",
            "--no-deps",
            "app",
            "python",
            "-c",
            "from pathlib import Path; "
            "Path('/var/lib/reponpc/local-portfolio/source-local').mkdir(parents=True)",
        )
        compose(project_name, environment_file, "up", "--detach")
        health = wait_for_health()
        assert health.json() == {"status": "alive"}
        status = httpx.get("http://127.0.0.1:18080/api/public/status", timeout=2)
        assert status.status_code == 200
        assert status.json()["status"] == "setup_required"
        marker = uuid4().hex
        marker_path = "/var/lib/reponpc/.p2-smoke-volume-marker"
        compose(
            project_name,
            environment_file,
            "exec",
            "-T",
            "app",
            "python",
            "-c",
            "from pathlib import Path; "
            f"Path({marker_path!r}).write_text({marker!r}, encoding='utf-8')",
        )
        compose(project_name, environment_file, "restart", "app")
        restarted = wait_for_health()
        assert restarted.status_code == 200
        compose(
            project_name,
            environment_file,
            "exec",
            "-T",
            "app",
            "python",
            "-c",
            "from pathlib import Path; "
            f"assert Path({marker_path!r}).read_text(encoding='utf-8') == {marker!r}",
        )
    finally:
        compose(project_name, environment_file, "down", "--volumes", "--remove-orphans")
