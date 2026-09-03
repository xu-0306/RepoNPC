from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_container_contract_is_non_root_single_service_and_locked() -> None:
    dockerfile = read("Dockerfile")
    compose = read("compose.yml")
    dockerignore = read(".dockerignore")

    assert "FROM node:24.14.0-bookworm-slim AS web-build" in dockerfile
    assert "FROM python:3.14.7-slim-bookworm AS runtime" in dockerfile
    assert "pnpm install --frozen-lockfile" in dockerfile
    assert "uv sync --locked" in dockerfile
    assert "USER reponpc:reponpc" in dockerfile
    assert 'VOLUME ["/var/lib/reponpc"]' in dockerfile
    assert "HEALTHCHECK" in dockerfile
    assert ":latest" not in dockerfile
    assert "services:\n  app:" in compose
    assert "read_only: true" in compose
    assert "reponpc-data:/var/lib/reponpc" in compose
    assert "./secrets:/run/secrets:ro" in compose
    assert "127.0.0.1:${REPONPC_HOST_PORT:-8000}:8000" in compose
    assert "postgres" not in compose.casefold()
    assert "redis" not in compose.casefold()
    assert "vector" not in compose.casefold()
    assert "\n  ollama:" not in compose.casefold()
    assert {".env", "secrets/", ".venv/", "node_modules/"} <= set(dockerignore.splitlines())


def test_compose_forwards_the_documented_application_environment() -> None:
    compose = read("compose.yml")
    documented = {
        match.group(1)
        for match in re.finditer(r"^(REPONPC_[A-Z0-9_]+)=", read(".env.example"), re.MULTILINE)
    }
    forwarded = {
        match.group(1)
        for match in re.finditer(r"^      (REPONPC_[A-Z0-9_]+):", compose, re.MULTILINE)
    }

    assert forwarded == documented
    assert "REPONPC_HOST_PORT" not in forwarded
    assert "replace-with-an-argon2id-phc-hash" not in compose
    assert "REPONPC_ADMIN_USERNAME: ${REPONPC_ADMIN_USERNAME:-}" in compose
    assert "REPONPC_ADMIN_USERNAME:-admin" not in compose
