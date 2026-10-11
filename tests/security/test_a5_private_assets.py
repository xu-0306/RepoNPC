"""Main checks real HTTP authority for private character and background previews."""

from __future__ import annotations

import io
import re
import threading
import time
from pathlib import Path

from fastapi.testclient import TestClient
from PIL import Image

from reponpc.admin.scene import SceneServiceError
from reponpc.api.visitor_ingress import create_visitor_gateway_app
from tests.browser.a5_server import FIXTURE_PASSWORD, FIXTURE_USERNAME, build_application

_ORIGIN = "https://fixture.test"


def _login(client: TestClient) -> dict[str, str]:
    response = client.post(
        "/api/admin/session",
        headers={"Origin": _ORIGIN},
        json={"username": FIXTURE_USERNAME, "password": FIXTURE_PASSWORD},
    )
    assert response.status_code == 200
    client.headers["Referer"] = f"{_ORIGIN}/admin"
    return {"Origin": _ORIGIN, "X-CSRF-Token": response.json()["csrf_token"]}


def _background(color: str) -> bytes:
    output = io.BytesIO()
    Image.new("RGBA", (640, 360), color).save(output, "PNG")
    return output.getvalue()


def test_real_private_asset_routes_require_the_creating_live_session(tmp_path: Path) -> None:
    app = build_application(tmp_path / "runtime", tmp_path / "web", _ORIGIN)
    with TestClient(app, base_url=_ORIGIN) as owner:
        # Share the running ASGI app without entering a second application lifespan.
        other = TestClient(app, base_url=_ORIGIN)
        other.headers["Referer"] = f"{_ORIGIN}/admin"
        try:
            writes = _login(owner)
            with app.application.state.scene_supplier().published_profile() as snapshot:
                sprite = snapshot.sprite_content
            character = owner.post(
                "/api/admin/assets/character/validate",
                headers=writes,
                files={"file": ("character.png", sprite, "image/png")},
            )
            assert character.status_code == 200
            preview_url = character.json()["png_url"]

            def upload(color: str) -> str:
                response = owner.post(
                    "/api/admin/assets/scene/background-drafts",
                    headers=writes,
                    files={"file": ("background.png", _background(color), "image/png")},
                )
                assert response.status_code == 200
                return f"/api/admin/assets/scene/background-drafts/{response.json()['draft_id']}"

            first = upload("black")
            for url in (preview_url, first):
                response = owner.get(url)
                assert response.status_code == 200
                assert response.headers["cache-control"] == "no-store"
                assert response.headers["x-content-type-options"] == "nosniff"
                assert other.get(url).status_code == 401

            other_writes = _login(other)
            for url in (preview_url, first):
                assert other.get(url).status_code == 404
                assert owner.get(url).status_code == 200
            assert other.delete(first, headers=other_writes).status_code == 204
            assert owner.get(first).status_code == 200

            replacement = upload("white")
            assert owner.get(first).status_code == 404
            assert owner.get(replacement).status_code == 200
            assert owner.delete(replacement).status_code == 403
            assert owner.get(replacement).status_code == 200
            assert owner.delete(replacement, headers=writes).status_code == 204
            assert owner.get(replacement).status_code == 404

            expiring = upload("black")
            database = app.application.state.runtime_database
            with database.connection() as connection:
                connection.execute(
                    "UPDATE scene_background_drafts SET expires_at='2000-01-01T00:00:00Z'"
                )
            assert owner.get(expiring).status_code == 404

            logout = owner.delete("/api/admin/session", headers=writes)
            assert logout.status_code == 204
            assert owner.get(preview_url).status_code == 401
            assert other.get(preview_url).status_code == 404
        finally:
            other.close()
    assert app.chat.calls == 2


def test_running_host_removes_expired_draft_bytes_and_retries_cleanup(
    tmp_path: Path, monkeypatch
) -> None:
    app = build_application(tmp_path / "runtime", tmp_path / "web", _ORIGIN)
    app.application.state.analysis_cleanup_seconds = 0.01
    service = app.application.state.scene_supplier()
    original_cleanup = service.cleanup_expired_background_drafts
    fail_next = [False]
    observed_failure = threading.Event()

    def cleanup() -> None:
        if fail_next[0]:
            fail_next[0] = False
            observed_failure.set()
            raise SceneServiceError("SCENE_ASSET_WRITE_FAILED")
        original_cleanup()

    monkeypatch.setattr(service, "cleanup_expired_background_drafts", cleanup)
    with TestClient(app, base_url=_ORIGIN) as owner:
        writes = _login(owner)
        uploaded = owner.post(
            "/api/admin/assets/scene/background-drafts",
            headers=writes,
            files={"file": ("background.png", _background("black"), "image/png")},
        )
        assert uploaded.status_code == 200
        assert tuple(service.draft_root.glob("*.png"))
        fail_next[0] = True
        with service.database.connection() as connection:
            connection.execute(
                "UPDATE scene_background_drafts SET expires_at='2000-01-01T00:00:00Z'"
            )
        assert observed_failure.wait(3)
        deadline = time.monotonic() + 3
        while tuple(service.draft_root.glob("*.png")) and time.monotonic() < deadline:
            time.sleep(0.01)
        assert not tuple(service.draft_root.glob("*.png"))
        with service.database.connection() as connection:
            count = connection.execute("SELECT count(*) FROM scene_background_drafts").fetchone()[0]
        assert count == 0
        assert owner.get("/api/admin/portfolio/status").status_code == 200
    assert app.chat.calls == 2


def test_public_background_headers_bind_the_applied_revision(tmp_path: Path) -> None:
    app = build_application(tmp_path / "runtime", tmp_path / "web", _ORIGIN)
    with TestClient(app, base_url=_ORIGIN) as owner:
        writes = _login(owner)
        created = owner.post(
            "/api/admin/assets/scene/background-drafts",
            headers=writes,
            files={"file": ("background.png", _background("white"), "image/png")},
        )
        assert created.status_code == 200

        def apply(background: str) -> str:
            state = owner.get("/api/admin/portfolio/status").json()["scene_state"]
            expected = {
                key: state[key]
                for key in (
                    "source_bundle_id",
                    "source_character_revision",
                    "character_revision",
                    "appearance_revision",
                    "draft_revision",
                    "sprite_sha256",
                )
            }
            response = owner.put(
                "/api/admin/scene",
                headers=writes,
                json={
                    "proposal": {**state["defaults"], "background": background},
                    "expected": expected,
                },
            )
            assert response.status_code == 200
            return response.json()["scene"]["background_url"]

        first_url = apply(f"draft:{created.json()['draft_id']}")
        first = owner.get(first_url)
        assert first.status_code == 200
        assert first.headers["cache-control"] == "no-store"
        assert first.headers["x-content-type-options"] == "nosniff"
        assert re.fullmatch(r'"[0-9a-f]{64}"', first.headers["etag"])
        assert owner.get(first_url).headers["etag"] == first.headers["etag"]
        head = owner.head(first_url)
        assert head.status_code == 200 and head.content == b""
        for header in ("etag", "content-length", "content-type", "cache-control"):
            assert head.headers[header] == first.headers[header]

        gateway = create_visitor_gateway_app(
            state_supplier=lambda: app.application.state.reponpc,
            bundle_manager_supplier=lambda: app.application.state.bundle_manager,
            chat_service_supplier=lambda: None,
            faq_supplier=lambda: None,
            scene_supplier=app.application.state.scene_supplier,
            gateway_origin="https://fixture.ts.net",
            pages_origin="https://fixture.github.io",
            listener_ready_supplier=lambda: True,
            web_dist=None,
            gateway_port=8001,
            trusted_proxy_cidrs=(),
            max_message_characters=2000,
            max_history_messages=6,
            max_history_characters=6000,
            global_concurrency=1,
            keepalive_seconds=1,
        )
        with TestClient(gateway, base_url="https://fixture.ts.net") as visitor:
            headers = {"Origin": "https://fixture.github.io"}
            image = visitor.get(first_url, headers=headers)
            assert image.status_code == 200 and image.content == first.content
            assert image.headers["etag"] == first.headers["etag"]
            assert image.headers["access-control-allow-origin"] == headers["Origin"]
            assert "access-control-allow-credentials" not in image.headers
            image_head = visitor.head(first_url, headers=headers)
            assert image_head.status_code == 200 and not image_head.content
            assert image_head.headers["content-length"] == image.headers["content-length"]
            preflight = visitor.options(
                first_url,
                headers={**headers, "Access-Control-Request-Method": "GET"},
            )
            assert preflight.status_code == 204
            assert preflight.headers["access-control-allow-origin"] == headers["Origin"]
            assert visitor.get(first_url, headers={"Cookie": "forged=1"}).status_code == 404
            private = "/api/admin/assets/scene/background-drafts/" + created.json()["draft_id"]
            assert visitor.get(private, headers=headers).status_code == 404

        second_url = apply("current")
        assert second_url != first_url
        assert owner.get(first_url).status_code == 404
        second = owner.get(second_url)
        assert second.status_code == 200 and second.content == first.content
        assert second.headers["etag"] != first.headers["etag"]
    assert app.chat.calls == 2
