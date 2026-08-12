from __future__ import annotations

import base64
import io
import json
from datetime import UTC, datetime
from pathlib import Path

from argon2 import PasswordHasher, Type
from fastapi.testclient import TestClient
from PIL import Image

from reponpc.admin.auth import AdminSessionService
from reponpc.admin.github import GitHubAdminClient, GitHubResponse
from reponpc.admin.operations import AdminOperations
from reponpc.main import create_app
from reponpc.runtime.database import RuntimeDatabase

ORIGIN = "https://portfolio.example.com"
PASSWORD = "correct horse battery staple"
CONFIG = Path("tests/fixtures/phase2/reponpc.yml").read_bytes()


class RecordingTransport:
    def __init__(self) -> None:
        self.requests: list[tuple[str, str, bytes | None]] = []
        self.files = {
            "reponpc.yml": (CONFIG, "a" * 40),
            "assets/character/hero.png": (_sprite(), "e" * 40),
        }

    def request(
        self, *, method: str, url: str, headers: dict[str, str], body: bytes | None
    ) -> GitHubResponse:
        assert headers["Authorization"] == "Bearer server-only-token"
        self.requests.append((method, url, body))
        if method == "GET" and "/commits/" in url:
            return GitHubResponse(200, json.dumps({"sha": "b" * 40}).encode())
        if method == "GET" and "/contents/" in url:
            path = url.split("/contents/", 1)[1].split("?", 1)[0]
            if path not in self.files:
                return GitHubResponse(404, b"{}")
            content, sha = self.files[path]
            return GitHubResponse(
                200,
                json.dumps({"content": base64.b64encode(content).decode(), "sha": sha}).encode(),
            )
        if method == "PUT":
            path = url.split("/contents/", 1)[1].split("?", 1)[0]
            payload = json.loads(body or b"{}")
            content = base64.b64decode(payload["content"])
            self.files[path] = (content, "d" * 40)
            return GitHubResponse(
                200,
                json.dumps({"commit": {"sha": "c" * 40}, "content": {"sha": "d" * 40}}).encode(),
            )
        if method == "POST" and "/dispatches" in url:
            return GitHubResponse(204, b"")
        raise AssertionError((method, url))


def _sprite() -> bytes:
    image = Image.new("RGBA", (128, 224), (0, 0, 0, 0))
    for row in range(7):
        for column in range(4):
            image.putpixel((column * 32 + 4, row * 32 + 4), (20, 30, 40, 255))
    output = io.BytesIO()
    image.save(output, "PNG")
    return output.getvalue()


def _application(tmp_path: Path):
    database = RuntimeDatabase(tmp_path)
    database.initialize()
    auth = AdminSessionService(
        database=database,
        username="admin",
        password_hash=PasswordHasher(type=Type.ID).hash(PASSWORD),
        identity_hmac_key=b"k" * 32,
        now=lambda: datetime(2026, 8, 13, tzinfo=UTC),
    )
    transport = RecordingTransport()
    github = GitHubAdminClient(
        repository="owner/profile",
        branch="main",
        workflow="build-index.yml",
        token="server-only-token",
        transport=transport,
    )
    operations = AdminOperations(github, database, ORIGIN)
    app = create_app(
        admin_session_service=auth,
        admin_origins=(ORIGIN,),
        admin_operations=operations,
    )
    return app, database, transport


def _login(client: TestClient) -> str:
    response = client.post(
        "/api/admin/session",
        headers={"Origin": ORIGIN},
        json={"username": "admin", "password": PASSWORD},
    )
    assert response.status_code == 200
    return str(response.json()["csrf_token"])


def test_validate_and_preview_are_side_effect_free_and_reject_secret_fields(
    tmp_path: Path,
) -> None:
    app, _database, transport = _application(tmp_path)
    with TestClient(app, base_url=ORIGIN) as client:
        _login(client)
        valid = client.post("/api/admin/config/validate", json={"content": CONFIG.decode()})
        preview = client.post("/api/admin/config/preview", json={"content": CONFIG.decode()})
        invalid = client.post(
            "/api/admin/config/validate",
            json={"content": CONFIG.decode() + "\npassword: CANARY-SECRET\n"},
        )

    assert valid.status_code == preview.status_code == 200
    assert set(preview.json()["profile"]) == {"zh-TW", "en"}
    assert len(preview.json()["cards"]) == 4
    assert invalid.status_code == 422
    assert invalid.json()["error"]["code"] == "CONFIG_INVALID"
    assert "CANARY-SECRET" not in invalid.text
    assert transport.requests == []


def test_config_and_asset_writes_validate_before_exact_mutation_and_audit(
    tmp_path: Path,
) -> None:
    app, database, transport = _application(tmp_path)
    with TestClient(app, base_url=ORIGIN) as client:
        csrf = _login(client)
        invalid_config = client.put(
            "/api/admin/config",
            headers={"Origin": ORIGIN, "X-CSRF-Token": csrf},
            json={
                "content": "schema_version: 1\npassword: CANARY\n",
                "expected_blob_sha": "a" * 40,
                "commit_message": "save",
            },
        )
        invalid_asset = client.put(
            "/api/admin/assets/character/hero.png",
            headers={"Origin": ORIGIN, "X-CSRF-Token": csrf},
            files={"file": ("hero.png", b"not-png", "image/png")},
            data={"expected_blob_sha": "e" * 40, "commit_message": "save asset"},
        )
        assert transport.requests == []
        saved = client.put(
            "/api/admin/config",
            headers={"Origin": ORIGIN, "X-CSRF-Token": csrf},
            json={
                "content": CONFIG.decode(),
                "expected_blob_sha": "a" * 40,
                "commit_message": "save config",
            },
        )
        asset = client.put(
            "/api/admin/assets/character/hero.png",
            headers={"Origin": ORIGIN, "X-CSRF-Token": csrf},
            files={"file": ("hero.png", _sprite(), "image/png")},
            data={"expected_blob_sha": "e" * 40, "commit_message": "save asset"},
        )

    assert invalid_config.status_code == invalid_asset.status_code == 422
    assert saved.status_code == asset.status_code == 200
    put_urls = [url for method, url, _body in transport.requests if method == "PUT"]
    assert len(put_urls) == 2
    assert any("/contents/reponpc.yml" in url for url in put_urls)
    assert any("/contents/assets/character/hero.png" in url for url in put_urls)
    with database.connection() as connection:
        audit = connection.execute(
            "SELECT action, target_path, outcome FROM admin_audit ORDER BY audit_id"
        ).fetchall()
    assert [tuple(row) for row in audit] == [
        ("config.write", "reponpc.yml", "succeeded"),
        ("asset.write", "assets/character/hero.png", "succeeded"),
    ]


def test_snippet_dispatch_and_status_use_fixed_server_configuration(tmp_path: Path) -> None:
    app, database, transport = _application(tmp_path)
    with TestClient(app, base_url=ORIGIN) as client:
        csrf = _login(client)
        snippet = client.get(
            "/api/admin/readme-snippet",
            params={"locale": "zh-TW", "theme": "dark", "extension": "svg", "revision": 3},
        )
        dispatched = client.post(
            "/api/admin/index/dispatch",
            headers={"Origin": ORIGIN, "X-CSRF-Token": csrf},
        )
        status = client.get("/api/admin/index/status")

    assert snippet.status_code == 200
    assert snippet.json()["asset_url"] == (
        f"{ORIGIN}/api/public/card.svg?theme=dark&locale=zh-TW&rev=3"
    )
    assert snippet.json()["target_url"] == ORIGIN
    assert dispatched.status_code == 202
    assert status.status_code == 200 and status.json()["active_bundle_id"] is None
    post_urls = [url for method, url, _body in transport.requests if method == "POST"]
    assert post_urls == [
        "https://api.github.com/repos/owner/profile/actions/workflows/build-index.yml/dispatches"
    ]
    with database.connection() as connection:
        outcome = connection.execute(
            "SELECT action, outcome FROM admin_audit ORDER BY audit_id DESC LIMIT 1"
        ).fetchone()
    assert tuple(outcome) == ("index.dispatch", "succeeded")
