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


def test_ci_uses_least_privilege_pinned_actions_and_locked_gates() -> None:
    workflow = read(".github/workflows/ci.yml")

    assert "contents: read" in workflow
    assert "write-all" not in workflow
    action_references = re.findall(r"uses: [^@\s]+@([^\s#]+)", workflow)
    assert action_references
    assert all(re.fullmatch(r"[0-9a-f]{40}", revision) for revision in action_references)
    for command in (
        "uv sync --locked --all-groups",
        "uv run ruff format --check src tests",
        "uv run ruff check src tests",
        "uv run mypy src/reponpc",
        "uv run pytest -q",
        "uv build",
        "pnpm install --frozen-lockfile",
        "pnpm run web:check",
        "docker compose -f compose.yml config --quiet",
        "docker build --tag reponpc:ci .",
    ):
        assert command in workflow


def test_index_workflow_installs_indexer_extra_and_keeps_manifest_publication_last() -> None:
    workflow = read(".github/workflows/build-index.yml")

    assert "uv sync --locked --extra indexer" in workflow
    commands = [
        "uv run reponpc config validate reponpc.yml",
        "uv run reponpc index build --config reponpc.yml --output dist",
        "uv run reponpc index publish --bundle-dir dist",
        "uv run reponpc index publish-manifest --bundle-dir dist",
    ]
    positions = [workflow.index(command) for command in commands]
    assert positions == sorted(positions)
    assert workflow.rstrip().endswith("uv run reponpc index publish-manifest --bundle-dir dist")
