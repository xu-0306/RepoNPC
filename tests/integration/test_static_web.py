from __future__ import annotations

import io
import json
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from reponpc.main import create_app
from tests.browser.a5_server import FIXTURE_PASSWORD, FIXTURE_USERNAME, build_application
from tests.integration.test_scene_publication import _expected_state, _proposal
from tests.security.test_a5_sharing_review import _visitor_build


def web_dist() -> Path:
    return Path(__file__).resolve().parents[2] / "apps" / "web" / "dist"


def test_same_origin_web_shell_preserves_api_routes_and_safe_headers() -> None:
    application = create_app(web_dist=web_dist())

    with TestClient(application) as client:
        shell = client.get("/")
        admin_shell = client.get("/admin")
        setup_status = client.get("/api/public/status")
        missing_api = client.get("/api/missing")
        missing_asset = client.get("/assets/missing.js")
        traversal = client.get("/%2e%2e/src/reponpc/main.py")

    assert shell.status_code == 200
    assert "RepoNPC" in shell.text
    assert "script-src 'self'" in shell.headers["Content-Security-Policy"]
    assert "style-src 'self'" in shell.headers["Content-Security-Policy"]
    assert "img-src 'self'" in shell.headers["Content-Security-Policy"]
    assert "img-src 'self' data:" not in shell.headers["Content-Security-Policy"]
    assert "*" not in shell.headers["Content-Security-Policy"]
    assert "access-control-allow-origin" not in shell.headers
    assert admin_shell.status_code == 200
    assert "RepoNPC" in admin_shell.text
    assert setup_status.status_code == 200
    assert setup_status.json()["status"] == "setup_required"
    assert missing_api.status_code == 404
    assert missing_asset.status_code == 404
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

    for forbidden in ("ollama:11434", "private.example.invalid"):
        assert forbidden not in bundle
    for direct_secret_name in (
        "reponpc_github_token",
        "reponpc_chat_api_key",
        "reponpc_ip_hash_key",
    ):
        assert re.search(rf"{direct_secret_name}(?!_file)", bundle) is None


@pytest.mark.parametrize("corruption", ["missing-image", "wrapper", "journal"])
def test_admin_entrance_and_session_survive_unreadable_published_appearance(
    tmp_path: Path, corruption: str
) -> None:
    origin = "https://fixture.test"
    web = _visitor_build(tmp_path)
    # A legacy admin build with visitor markers must remain recoverable, too.
    (web / "index.html").write_bytes((web / "visitor.html").read_bytes())
    app = build_application(tmp_path / "runtime", web, origin)
    app.application.state.deployment_profile = "production"
    with TestClient(app, base_url=origin) as client:
        login = client.post(
            "/api/admin/session",
            headers={"Origin": origin},
            json={"username": FIXTURE_USERNAME, "password": FIXTURE_PASSWORD},
        )
        assert login.status_code == 200
        client.headers["Referer"] = origin + "/admin"
        writes = {"Origin": origin, "X-CSRF-Token": login.json()["csrf_token"]}
        state = client.get("/api/admin/portfolio/status").json()["scene_state"]
        encoded = io.BytesIO()
        Image.new("RGB", (640, 360), "navy").save(encoded, "PNG")
        draft = client.post(
            "/api/admin/assets/scene/background-drafts",
            headers=writes,
            files={"file": ("background.png", encoded.getvalue(), "image/png")},
        )
        assert draft.status_code == 200
        applied = client.put(
            "/api/admin/scene",
            headers=writes,
            json={
                "proposal": _proposal(state, background="draft:" + draft.json()["draft_id"]),
                "expected": _expected_state(state),
            },
        )
        assert applied.status_code == 200
        service = app.application.state.scene_supplier()
        bundle_id = service.manager.status().active_bundle_id
        row = service._state_row()
        if corruption == "missing-image":
            image = service.asset_root / f"{row['background_sha256']}.{row['background_extension']}"
            image.unlink()
        else:
            with service.database.connection() as connection:
                if corruption == "wrapper":
                    wrapper = json.loads(row["scene_json"])
                    wrapper["settings"]["color_mode"] = "invalid"
                    connection.execute(
                        "UPDATE scene_appearance_state SET scene_json=? WHERE singleton=1",
                        (json.dumps(wrapper),),
                    )
                else:
                    connection.execute(
                        "UPDATE scene_appearance_state SET journal_json='{}' WHERE singleton=1"
                    )
        for path in ("/admin", "/admin/recovery"):
            response = client.get(path)
            assert response.status_code == 200
            assert "unsafe-inline" not in response.headers["content-security-policy"]
            assert client.head(path).status_code == 200
        assert (
            client.post("/api/admin/session/resume", headers={"Origin": origin}).status_code == 200
        )
        failure = client.get("/api/admin/portfolio/status")
        assert failure.status_code == 503
        assert failure.json()["error"]["code"] == (
            "SCENE_RECOVERY_FAILED" if corruption == "journal" else "PUBLIC_SCENE_UNAVAILABLE"
        )
        assert str(tmp_path) not in failure.text and "background_sha256" not in failure.text
        assert client.get("/").status_code == 503
        assert client.get("/api/public/profile").status_code == 503
        assert client.get("/admin", headers={"Host": "public.example.test"}).status_code == 404
        assert service.manager.status().active_bundle_id == bundle_id
        assert app.chat.calls == 2
