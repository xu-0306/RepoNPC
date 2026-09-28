"""Isolated Linux host-network Compose and real image visitor-ingress smoke."""

from __future__ import annotations

import json
import os
import subprocess
from uuid import uuid4

import pytest

from scripts.funnel_compose_preflight import supported
from tests.smoke.test_container import DOCKER_EXECUTABLE, ROOT


@pytest.mark.skipif(DOCKER_EXECUTABLE is None, reason="docker executable is unavailable")
def test_funnel_compose_and_image_gateway_use_closed_loopback_ingress(tmp_path):
    project = "reponpc-a1-" + uuid4().hex[:12]
    values = {
        name: value for name, value in os.environ.items() if not name.upper().startswith("REPONPC_")
    }
    environment_file = tmp_path / "synthetic.env"
    environment_file.write_text(
        "REPONPC_ADMIN_ORIGINS=https://private.example.com\n", encoding="utf-8"
    )

    def docker(*arguments):
        return subprocess.run(
            [DOCKER_EXECUTABLE, *arguments],
            cwd=ROOT,
            env=values,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=True,
        )

    version = docker("compose", "version", "--short").stdout.strip()
    assert supported(version), "Funnel override requires stable Compose 2.24.4 or later"
    command = (
        "compose",
        "--env-file",
        str(environment_file),
        "--project-name",
        project,
        "--file",
        "compose.yml",
        "--file",
        "compose.funnel.yml",
    )
    resolved = json.loads(docker(*command, "config", "--format", "json").stdout)
    app = resolved["services"]["app"]
    assert app["network_mode"] == "host" and not app.get("ports")
    assert app["environment"]["REPONPC_HOST"] == "127.0.0.1"
    assert app["environment"]["REPONPC_ADMIN_ORIGINS"] == "https://private.example.com"
    try:
        docker(*command, "build", "app")
        result = docker(
            *command,
            "run",
            "--rm",
            "--no-deps",
            "--volume",
            f"{ROOT / 'tests/smoke/visitor_gateway_probe.py'}:/tmp/visitor_gateway_probe.py:ro",
            "app",
            "python",
            "/tmp/visitor_gateway_probe.py",
        )
        assert "private-path denial and stop passed" in result.stdout
    finally:
        docker(*command, "down", "--volumes", "--remove-orphans")
