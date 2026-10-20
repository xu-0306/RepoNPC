"""Retained local admin validation, preview and character conversion coverage."""

from __future__ import annotations

import base64
import io
import json
import zipfile
from datetime import UTC, datetime
from pathlib import Path

from argon2 import PasswordHasher, Type
from fastapi.testclient import TestClient
from PIL import Image

from reponpc.admin.auth import AdminSessionService
from reponpc.admin.operations import AdminOperations
from reponpc.cards.assets import FRAME_COLUMNS, FRAME_ROWS, FRAME_SIZE, HEIGHT, WIDTH
from reponpc.main import create_app
from reponpc.runtime.database import RuntimeDatabase

ORIGIN = "https://portfolio.example.com"
PASSWORD = "correct horse battery staple"
CONFIG = Path("tests/fixtures/phase2/reponpc.yml").read_bytes()
CUSTOM_CONFIG = (
    CONFIG.decode()
    .replace("\r\n", "\n")
    .replace(
        """  mode: builtin
  revision: 0
  builtin:
    pack_id: core/humanoid
    pack_version: 1
    options:
      tone: medium
      hairstyle: short
      attire: engineer
      hair_color: '#2b1d14'
      primary_color: '#6d5dfc'
      secondary_color: '#f2c14e'
      accessory: glasses
""",
        """  mode: custom
  revision: 0
  custom:
    sprite_path: assets/character/hero.png
""",
    )
    .replace("\n", "\r\n")
)


def _sprite() -> bytes:
    image = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    for row in range(FRAME_ROWS):
        for column in range(FRAME_COLUMNS):
            image.putpixel(
                (column * FRAME_SIZE + 4, row * FRAME_SIZE + 4),
                (20, 30, 40, 255),
            )
    output = io.BytesIO()
    image.save(output, "PNG")
    return output.getvalue()


def _source_grid(cell_size: int = 73) -> bytes:
    image = Image.new(
        "RGBA",
        (FRAME_COLUMNS * cell_size, FRAME_ROWS * cell_size),
        (0, 0, 0, 0),
    )
    for row in range(FRAME_ROWS):
        for column in range(FRAME_COLUMNS):
            image.putpixel(
                (column * cell_size + 8, row * cell_size + 8),
                (20 + row, 30 + column, 40, 255),
            )
    output = io.BytesIO()
    image.save(output, "PNG")
    return output.getvalue()


def _source_grid_with_edge_spill(cell_size: int = 73) -> bytes:
    image = Image.open(io.BytesIO(_source_grid(cell_size))).convert("RGBA")
    for x in range(cell_size // 3, cell_size // 2):
        image.putpixel((x, cell_size - 1), (90, 45, 25, 160))
        image.putpixel((x, cell_size), (90, 45, 25, 160))
    output = io.BytesIO()
    image.save(output, "PNG")
    return output.getvalue()


def _discovery_zip() -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("unknown/readme.txt", "fixture")
        archive.writestr("unknown/first.png", _source_grid(73))
        archive.writestr("unknown/second.png", _source_grid(91))
    return output.getvalue()


def local_admin_application(tmp_path: Path):
    database = RuntimeDatabase(tmp_path)
    database.initialize()
    auth = AdminSessionService(
        database=database,
        username="admin",
        password_hash=PasswordHasher(type=Type.ID).hash(PASSWORD),
        identity_hmac_key=b"k" * 32,
        now=lambda: datetime(2026, 8, 13, tzinfo=UTC),
    )
    operations = AdminOperations(database, ORIGIN)
    return create_app(
        admin_session_service=auth,
        admin_origins=(ORIGIN,),
        admin_operations=operations,
    )


def _login(client: TestClient) -> str:
    response = client.post(
        "/api/admin/session",
        headers={"Origin": ORIGIN},
        json={"username": "admin", "password": PASSWORD},
    )
    assert response.status_code == 200
    client.headers["Referer"] = ORIGIN + "/admin"
    return str(response.json()["csrf_token"])


def test_validate_and_preview_are_side_effect_free_and_reject_secret_fields(
    tmp_path: Path,
) -> None:
    app = local_admin_application(tmp_path)
    with TestClient(app, base_url=ORIGIN) as client:
        csrf = _login(client)
        valid = client.post("/api/admin/config/validate", json={"content": CONFIG.decode()})
        preview = client.post(
            "/api/admin/config/preview",
            headers={"X-CSRF-Token": csrf},
            json={"content": CONFIG.decode()},
        )
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


def test_snippet_and_status_use_fixed_server_configuration(tmp_path: Path) -> None:
    app = local_admin_application(tmp_path)
    with TestClient(app, base_url=ORIGIN) as client:
        _login(client)
        snippet = client.get(
            "/api/admin/readme-snippet",
            params={"locale": "zh-TW", "theme": "dark", "extension": "svg", "revision": 3},
        )
        status = client.get("/api/admin/index/status")

    assert snippet.status_code == 200
    assert snippet.json()["asset_url"] == (
        f"{ORIGIN}/api/public/card.svg?theme=dark&locale=zh-TW&rev=3"
    )
    assert snippet.json()["target_url"] == ORIGIN
    assert status.status_code == 200 and status.json()["active_bundle_id"] is None


def test_local_admin_tools_work_without_write_credentials(tmp_path: Path) -> None:
    app = local_admin_application(tmp_path)
    with TestClient(app, base_url=ORIGIN) as client:
        csrf = _login(client)
        local_responses = {
            "validate": client.post(
                "/api/admin/config/validate", json={"content": CONFIG.decode()}
            ),
            "preview": client.post(
                "/api/admin/config/preview",
                headers={"Origin": ORIGIN, "X-CSRF-Token": csrf},
                json={"content": CONFIG.decode()},
            ),
            "asset_validate": client.post(
                "/api/admin/assets/character/validate",
                headers={"Origin": ORIGIN, "X-CSRF-Token": csrf},
                files={"file": ("hero.png", _sprite(), "image/png")},
            ),
            "asset_convert": client.post(
                "/api/admin/assets/character/convert",
                headers={"Origin": ORIGIN, "X-CSRF-Token": csrf},
                files={"file": ("source.png", _source_grid(), "image/png")},
                data={"strategy": "pixelize"},
            ),
            "snippet": client.get(
                "/api/admin/readme-snippet",
                params={
                    "locale": "en",
                    "theme": "light",
                    "extension": "svg",
                    "revision": 0,
                },
            ),
            "status": client.get("/api/admin/index/status"),
        }
        custom_preview = client.post(
            "/api/admin/config/preview",
            headers={"Origin": ORIGIN, "X-CSRF-Token": csrf},
            json={"content": CUSTOM_CONFIG},
        )

    assert {name: response.status_code for name, response in local_responses.items()} == {
        "validate": 200,
        "preview": 200,
        "asset_validate": 200,
        "asset_convert": 200,
        "snippet": 200,
        "status": 200,
    }
    converted = local_responses["asset_convert"].json()
    assert converted["asset"]["width"] == WIDTH
    assert converted["asset"]["height"] == HEIGHT
    assert converted["conversion"]["source_kind"] == "grid"
    assert converted["edge_cleanup"] is None
    assert custom_preview.status_code == 422
    assert custom_preview.json()["error"]["code"] == "CONFIG_INVALID"
    assert [field["code"] for field in custom_preview.json()["error"]["details"]["fields"]] == [
        "custom_sprite_preview_needs_upload"
    ]


def test_character_convert_returns_an_optional_validated_cleanup_without_writing(
    tmp_path: Path,
) -> None:
    app = local_admin_application(tmp_path)
    with TestClient(app, base_url=ORIGIN) as client:
        csrf = _login(client)
        response = client.post(
            "/api/admin/assets/character/convert",
            headers={"Origin": ORIGIN, "X-CSRF-Token": csrf},
            files={"file": ("unfamiliar.png", _source_grid_with_edge_spill(), "image/png")},
            data={"strategy": "pixelize"},
        )

    assert response.status_code == 200
    body = response.json()
    cleanup = body["edge_cleanup"]
    assert cleanup is not None
    assert cleanup["affected_frames"] == [{"state": "walk", "frame": 0}]
    assert cleanup["removed_source_pixels"] > 0
    assert cleanup["asset"]["sha256"] != body["asset"]["sha256"]
    with Image.open(io.BytesIO(base64.b64decode(body["asset"]["png_base64"]))) as original:
        assert original.getpixel((FRAME_SIZE // 3, FRAME_SIZE))[3] > 0
    with Image.open(io.BytesIO(base64.b64decode(cleanup["asset"]["png_base64"]))) as cleaned:
        assert cleaned.getpixel((FRAME_SIZE // 3, FRAME_SIZE))[3] == 0


def test_material_bundle_api_discovers_zip_and_folder_candidates_without_github(
    tmp_path: Path,
) -> None:
    app = local_admin_application(tmp_path)
    archive = _discovery_zip()
    with TestClient(app, base_url=ORIGIN) as client:
        csrf = _login(client)
        discovery = client.post(
            "/api/admin/assets/character/convert",
            headers={"Origin": ORIGIN, "X-CSRF-Token": csrf},
            files={"file": ("anything.zip", archive, "application/zip")},
            data={"strategy": "pixelize"},
        )
        assert discovery.status_code == 200
        discovered = discovery.json()
        assert discovered["status"] == "selection_required"
        assert discovered["discovery"]["ignored_count"] == 1
        candidates = discovered["discovery"]["candidates"]
        assert len(candidates) == 2

        selected = client.post(
            "/api/admin/assets/character/convert",
            headers={"Origin": ORIGIN, "X-CSRF-Token": csrf},
            files={"file": ("anything.zip", archive, "application/zip")},
            data={
                "strategy": "pixelize",
                "candidate_id": candidates[1]["candidate_id"],
            },
        )
        folder = client.post(
            "/api/admin/assets/character/convert",
            headers={"Origin": ORIGIN, "X-CSRF-Token": csrf},
            files=[
                ("files", ("first.png", _source_grid(79), "image/png")),
                ("files", ("second.png", _source_grid(97), "image/png")),
                ("files", ("notes.txt", b"notes", "text/plain")),
            ],
            data={
                "strategy": "pixelize",
                "paths_json": json.dumps(
                    ["custom/first.png", "custom/second.png", "custom/notes.txt"]
                ),
            },
        )

    assert selected.status_code == 200
    assert selected.json()["status"] == "converted"
    assert selected.json()["conversion"]["source_kind"] == "bundle"
    assert selected.json()["conversion"]["source_path"] == "unknown/second.png"
    assert folder.status_code == 200
    assert folder.json()["status"] == "selection_required"
    assert len(folder.json()["discovery"]["candidates"]) == 2
