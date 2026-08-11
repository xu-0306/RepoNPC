from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from reponpc.main import create_app


def web_dist() -> Path:
    return Path(__file__).resolve().parents[2] / "apps" / "web" / "dist"


def test_same_origin_web_shell_preserves_api_routes_and_safe_headers() -> None:
    application = create_app(web_dist=web_dist())

    with TestClient(application) as client:
        shell = client.get("/")
        setup_status = client.get("/api/public/status")
        traversal = client.get("/%2e%2e/src/reponpc/main.py")

    assert shell.status_code == 200
    assert "RepoNPC" in shell.text
    assert "script-src 'self'" in shell.headers["Content-Security-Policy"]
    assert "style-src 'self'" in shell.headers["Content-Security-Policy"]
    assert "*" not in shell.headers["Content-Security-Policy"]
    assert "access-control-allow-origin" not in shell.headers
    assert setup_status.status_code == 200
    assert setup_status.json()["status"] == "setup_required"
    assert traversal.status_code == 404
    assert str(web_dist()) not in traversal.text


def test_missing_web_build_does_not_break_health_or_expose_filesystem(tmp_path: Path) -> None:
    application = create_app(web_dist=tmp_path / "not-built")

    with TestClient(application) as client:
        health = client.get("/healthz")
        setup_status = client.get("/api/public/status")
        root = client.get("/")

    assert health.status_code == 200
    assert setup_status.status_code == 200
    assert root.status_code == 404
    assert str(tmp_path) not in root.text


def test_built_web_assets_exclude_server_secret_and_private_provider_canaries() -> None:
    bundle = "\n".join(
        asset.read_text(encoding="utf-8") for asset in web_dist().rglob("*") if asset.is_file()
    ).casefold()

    for forbidden in (
        "reponpc_github_token",
        "reponpc_chat_api_key",
        "reponpc_ip_hash_key",
        "ollama:11434",
        "private.example.invalid",
    ):
        assert forbidden not in bundle
