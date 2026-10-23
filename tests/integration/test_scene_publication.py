"""Authenticated appearance publication through the production HTTP routes."""

from __future__ import annotations

import base64
import hashlib
import io
import json
import secrets
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import cast

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from reponpc.admin.local_portfolio import LocalPortfolioError
from reponpc.admin.scene import (
    AdminSceneService,
    PublishedProfileSnapshot,
    SceneServiceError,
    _json_text,
    _sha,
    _state_pointer_digest,
)
from reponpc.bundles.manager import BundleManager
from reponpc.cards.assets import validate_sprite
from reponpc.config.models import parse_public_config_bytes
from reponpc.indexing.public_profile import BilingualPublicProfile
from reponpc.scene.images import validate_scene_image
from reponpc.scene.registry import contrast_ratio, default_scene_registry
from reponpc.scene.resolve import resolve_scene
from tests.browser.a5_server import FIXTURE_PASSWORD, FIXTURE_USERNAME, build_application

_ORIGIN = "https://fixture.test"


def _scene_image() -> bytes:
    output = io.BytesIO()
    Image.new("RGBA", (640, 360), (32, 48, 64, 255)).save(output, "PNG")
    return output.getvalue()


def _canonical_sheet() -> bytes:
    image = Image.new("RGBA", (256, 448), (0, 0, 0, 0))
    for row in range(7):
        for column in range(4):
            image.putpixel((column * 64 + 12, row * 64 + 12), (40, 80, 120, 255))
    output = io.BytesIO()
    image.save(output, "PNG", optimize=False, compress_level=9)
    return validate_sprite(output.getvalue()).content


def _bright_edge_sheet() -> bytes:
    image = Image.new("RGBA", (256, 448), (0, 0, 0, 0))
    for row in range(7):
        for column in range(4):
            left, top = column * 64, row * 64
            for offset in range(64):
                image.putpixel((left + offset, top), (245, 245, 245, 255))
                image.putpixel((left + offset, top + 63), (245, 245, 245, 255))
                image.putpixel((left, top + offset), (245, 245, 245, 255))
                image.putpixel((left + 63, top + offset), (245, 245, 245, 255))
    output = io.BytesIO()
    image.save(output, "PNG", optimize=False, compress_level=9)
    return validate_sprite(output.getvalue()).content


def test_scene_status_gallery_resolves_every_scheme_for_all_sheet_edges(tmp_path: Path) -> None:
    registry = default_scene_registry()
    sprite = _bright_edge_sheet()
    service = AdminSceneService(
        manager=cast(BundleManager, object()),
        database=None,
        data_directory=tmp_path,
        registry=registry,
    )
    base_scene = resolve_scene(
        {"color_scheme": "neutral"},
        sprite_content=sprite,
        revision=0,
        registry=registry,
    ).public
    snapshot = PublishedProfileSnapshot(
        document=cast(BilingualPublicProfile, object()),
        bundle_id="fixture-bundle",
        public_directory=tmp_path,
        sprite_content=sprite,
        sprite_sha256=hashlib.sha256(sprite).hexdigest(),
        source_character_revision=0,
        character_revision=0,
        appearance_revision=None,
        background_content=None,
        settings=None,
        issued_revision=0,
    )

    payload = service._scene_state_payload(
        snapshot=snapshot,
        scene=base_scene,
        settings=None,
        character_revision=0,
        appearance_revision=0,
        draft_revision=None,
        issued_revision=0,
    )

    gallery = cast(list[dict[str, object]], payload["schemes"])
    assert len(gallery) == 4
    assert {str(item["id"]) for item in gallery} == set(registry.schemes)
    for item in gallery:
        scheme = registry.schemes[str(item["id"])]
        themes = cast(dict[str, dict[str, str]], item["themes"])
        assert item["npc_plate"]["light"] is True
        if contrast_ratio("#f5f5f5", scheme.light["stage"]) >= 3.0:
            assert themes["light"]["stage"] == scheme.light["stage"]
        else:
            assert themes["light"]["stage"] != scheme.light["stage"]
        assert contrast_ratio("#f5f5f5", themes["light"]["stage"]) >= 3.0
        assert themes["light"]["stage"] != themes["light"]["surface"]


def test_publication_status_without_active_bundle_keeps_preparation_status(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from reponpc.bundles.manager import BundleStatus

    app = build_application(tmp_path / "runtime", tmp_path / "web", _ORIGIN)
    with TestClient(app, base_url=_ORIGIN) as client:
        login = client.post(
            "/api/admin/session",
            headers={"Origin": _ORIGIN},
            json={"username": FIXTURE_USERNAME, "password": FIXTURE_PASSWORD},
        )
        assert login.status_code == 200
        client.headers["Referer"] = f"{_ORIGIN}/admin"
        service = app.application.state.scene_supplier()
        monkeypatch.setattr(service.manager, "status", lambda: BundleStatus(None, None, None))

        def unavailable_scene() -> dict[str, object]:
            raise SceneServiceError("PUBLIC_SCENE_UNAVAILABLE")

        monkeypatch.setattr(service, "scene_state", unavailable_scene)
        response = client.get("/api/admin/portfolio/status")
        assert response.status_code == 200
        assert response.json()["scene_state"] is None
        assert "state" in response.json()

        monkeypatch.undo()
        monkeypatch.setattr(service, "scene_state", unavailable_scene)
        response = client.get("/api/admin/portfolio/status")
        assert response.status_code == 503
        assert response.json()["error"]["code"] == "PUBLIC_SCENE_UNAVAILABLE"


def _expected_state(state: dict[str, object]) -> dict[str, object]:
    return {
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


def _proposal(state: dict[str, object], *, background: str) -> dict[str, object]:
    return {
        "color_scheme": state["scene"]["scheme"]["id"],  # type: ignore[index]
        "color_mode": "system",
        "visitor_mode_toggle": True,
        "visitor_scheme_choice": True,
        "accent": None,
        "background": background,
        "focus": {"x": 50, "y": 50},
        "dim": "auto",
        "scaling": "smooth",
    }


def test_scene_scheme_choice_preview_apply_reset_and_strict_bool(tmp_path: Path) -> None:
    app = build_application(tmp_path / "runtime", tmp_path / "web", _ORIGIN)
    with TestClient(app, base_url=_ORIGIN) as client:
        login = client.post(
            "/api/admin/session",
            headers={"Origin": _ORIGIN},
            json={"username": FIXTURE_USERNAME, "password": FIXTURE_PASSWORD},
        )
        assert login.status_code == 200
        client.headers["Referer"] = f"{_ORIGIN}/admin"
        headers = {"Origin": _ORIGIN, "X-CSRF-Token": login.json()["csrf_token"]}
        state = client.get("/api/admin/portfolio/status").json()["scene_state"]
        defaults = state["defaults"]
        assert defaults["color_scheme"] == "meadow"
        assert defaults["color_mode"] == "system"
        assert defaults["visitor_mode_toggle"] is True
        assert defaults["visitor_scheme_choice"] is True
        assert defaults["accent"] is None
        proposal = {
            **defaults,
            "color_scheme": "sunset",
            "color_mode": "dark",
            "visitor_mode_toggle": False,
            "visitor_scheme_choice": False,
            "accent": "#333399",
        }
        for value in (0, 1, "false", None):
            invalid = {**proposal, "visitor_scheme_choice": value}
            assert (
                client.post("/api/admin/scene/preview", headers=headers, json=invalid).status_code
                == 400
            )
            assert (
                client.put(
                    "/api/admin/scene",
                    headers=headers,
                    json={"proposal": invalid, "expected": _expected_state(state)},
                ).status_code
                == 400
            )
        preview = client.post("/api/admin/scene/preview", headers=headers, json=proposal)
        assert preview.status_code == 200
        assert preview.json()["scene"]["visitor_scheme_choice"] is False
        applied = client.put(
            "/api/admin/scene",
            headers=headers,
            json={"proposal": proposal, "expected": _expected_state(state)},
        )
        assert applied.status_code == 200
        assert applied.json()["scene"] == preview.json()["scene"]
        current = applied.json()["scene_state"]
        assert current["settings"]["visitor_scheme_choice"] is False
        assert (
            client.get("/api/public/profile?locale=en").json()["character"]["scene"]
            == applied.json()["scene"]
        )
        reset = client.put(
            "/api/admin/scene",
            headers=headers,
            json={"proposal": defaults, "expected": _expected_state(current)},
        )
        assert reset.status_code == 200
        assert reset.json()["scene_state"]["settings"] == defaults
        assert reset.json()["scene"]["scheme"] == {"id": "meadow", "version": 1}
        assert reset.json()["scene"]["visitor_scheme_choice"] is True
        config = parse_public_config_bytes(
            client.get("/api/admin/portfolio").json()["content"].encode()
        )
        assert config.character.scene.visitor_scheme_choice is True


def test_http_scene_draft_preview_apply_and_revision_binding(tmp_path: Path) -> None:
    app = build_application(tmp_path / "runtime", tmp_path / "web", _ORIGIN)
    with TestClient(app, base_url=_ORIGIN) as client:
        login = client.post(
            "/api/admin/session",
            headers={"Origin": _ORIGIN},
            json={"username": FIXTURE_USERNAME, "password": FIXTURE_PASSWORD},
        )
        assert login.status_code == 200
        csrf = login.json()["csrf_token"]
        client.headers["Referer"] = f"{_ORIGIN}/admin"
        write_headers = {"Origin": _ORIGIN, "X-CSRF-Token": csrf}

        initial_status = client.get("/api/admin/portfolio/status")
        assert initial_status.status_code == 200
        initial = initial_status.json()["scene_state"]
        assert initial["defaults"]["background"] == "none"
        assert initial["schemes"]
        assert "background_path" not in initial["settings"]

        upload = {"file": ("visitor.png", _scene_image(), "image/png")}
        missing_csrf = client.post("/api/admin/assets/scene/background-drafts", files=upload)
        assert missing_csrf.status_code == 403

        created = client.post(
            "/api/admin/assets/scene/background-drafts",
            headers=write_headers,
            files=upload,
        )
        assert created.status_code == 200
        draft_id = created.json()["draft_id"]
        draft = client.get(f"/api/admin/assets/scene/background-drafts/{draft_id}")
        assert draft.status_code == 200
        assert draft.headers["cache-control"] == "no-store"
        assert draft.headers["x-content-type-options"] == "nosniff"
        assert draft.headers["content-type"].startswith("image/png")
        canonical_image = validate_scene_image(draft.content, filename="draft.png")
        assert canonical_image.content == draft.content

        old_draft = client.get("/api/admin/portfolio").json()
        proposal = _proposal(initial, background=f"draft:{draft_id}")
        preview = client.post("/api/admin/scene/preview", headers=write_headers, json=proposal)
        assert preview.status_code == 200
        assert preview.json()["scene"]["background_dim"] in {"none", "low", "medium", "high"}

        applied = client.put(
            "/api/admin/scene",
            headers=write_headers,
            json={"proposal": proposal, "expected": _expected_state(initial)},
        )
        assert applied.status_code == 200, applied.text
        first = applied.json()["scene_state"]
        first_revision = first["character_revision"]
        public_profile = client.get("/api/public/profile?locale=en")
        assert public_profile.status_code == 200
        character = public_profile.json()["character"]
        assert character["revision"] == first_revision
        assert character["scene"]["revision"] == first_revision
        background = client.get(character["scene"]["background_url"])
        assert background.status_code == 200
        assert background.content == canonical_image.content
        assert background.headers["cache-control"] == "no-store"
        assert background.headers["x-content-type-options"] == "nosniff"

        changed_config = parse_public_config_bytes(
            client.get("/api/admin/portfolio").json()["content"].encode("utf-8")
        )
        original_config = parse_public_config_bytes(old_draft["content"].encode("utf-8"))
        expected_config = original_config.model_copy(
            update={
                "character": original_config.character.model_copy(
                    update={
                        "revision": first_revision,
                        "scene": changed_config.character.scene,
                    }
                )
            }
        )
        assert changed_config == expected_config

        cleared = client.put(
            "/api/admin/scene",
            headers=write_headers,
            json={
                "proposal": _proposal(first, background="none"),
                "expected": _expected_state(first),
            },
        )
        assert cleared.status_code == 200, cleared.text
        second = cleared.json()["scene_state"]
        assert second["character_revision"] > first_revision
        assert client.get(character["scene"]["background_url"]).status_code == 404

        validated = client.post(
            "/api/admin/assets/character/validate",
            headers=write_headers,
            files={"file": ("character.png", _canonical_sheet(), "image/png")},
        )
        assert validated.status_code == 200
        preview_url = validated.json()["png_url"]
        protected_preview = client.get(preview_url)
        assert protected_preview.status_code == 200
        assert protected_preview.headers["cache-control"] == "no-store"
        assert protected_preview.headers["x-content-type-options"] == "nosniff"
        assert protected_preview.content == base64.b64decode(
            validated.json()["png_base64"], validate=True
        )

    assert app.chat.calls == 2


def test_scene_apply_failure_boundaries_preserve_or_commit_complete_pairs(
    tmp_path: Path, monkeypatch
) -> None:
    app = build_application(tmp_path / "runtime", tmp_path / "web", _ORIGIN)
    with TestClient(app, base_url=_ORIGIN) as client:
        login = client.post(
            "/api/admin/session",
            headers={"Origin": _ORIGIN},
            json={"username": FIXTURE_USERNAME, "password": FIXTURE_PASSWORD},
        )
        assert login.status_code == 200
        csrf = login.json()["csrf_token"]
        headers = {"Origin": _ORIGIN, "X-CSRF-Token": csrf}
        client.headers["Referer"] = f"{_ORIGIN}/admin"

        service = app.application.state.scene_supplier()
        assert isinstance(service, AdminSceneService)
        state = service.scene_state()
        expected = _expected_state(state)
        proposal = _proposal(state, background="none")
        portfolio = service.portfolio
        assert portfolio is not None
        original_raw = portfolio._draft_path.read_bytes()

        original_backup = service._write_recovery_backup

        def fail_backup(_backup_id: str, _old_raw: bytes | None) -> None:
            raise SceneServiceError("SCENE_ASSET_WRITE_FAILED")

        monkeypatch.setattr(service, "_write_recovery_backup", fail_backup)
        backup_failure = client.put(
            "/api/admin/scene", headers=headers, json={"proposal": proposal, "expected": expected}
        )
        assert backup_failure.status_code == 503
        assert portfolio._draft_path.read_bytes() == original_raw
        monkeypatch.setattr(service, "_write_recovery_backup", original_backup)

        image_response = client.post(
            "/api/admin/assets/scene/background-drafts",
            headers=headers,
            files={"file": ("background.png", _scene_image(), "image/png")},
        )
        assert image_response.status_code == 200
        image_draft = image_response.json()
        candidate_proposal = _proposal(state, background=f"draft:{image_draft['draft_id']}")
        original_atomic_content_addressed = service._atomic_content_addressed

        def fail_candidate(root: Path, digest: str, extension: str, content: bytes) -> Path:
            if root == service.asset_root:
                raise SceneServiceError("SCENE_ASSET_WRITE_FAILED")
            return original_atomic_content_addressed(root, digest, extension, content)

        monkeypatch.setattr(service, "_atomic_content_addressed", fail_candidate)
        candidate_failure = client.put(
            "/api/admin/scene",
            headers=headers,
            json={"proposal": candidate_proposal, "expected": expected},
        )
        assert candidate_failure.status_code == 503
        assert portfolio._draft_path.read_bytes() == original_raw
        monkeypatch.setattr(service, "_atomic_content_addressed", original_atomic_content_addressed)

        database = service.database
        assert database is not None
        background_image = validate_scene_image(_scene_image(), filename="background.png")
        background_path = service.draft_root / f"{background_image.sha256}.png"
        assert background_path.is_file()
        draft_id_hash = hashlib.sha256(str(image_draft["draft_id"]).encode("ascii")).hexdigest()
        with database.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                "UPDATE scene_background_drafts SET expires_at=? WHERE draft_id_hash=?",
                ("2000-01-01T00:00:00Z", draft_id_hash),
            )
            connection.execute("COMMIT")
        assert service.cleanup_expired_background_drafts() == 1
        assert not background_path.exists()

        original_connection = database.connection

        class BeforeJournalCommit:
            def __init__(self, connection) -> None:
                self.connection = connection
                self.journal_pending = False

            def execute(self, statement: str, parameters=()):
                if statement.lstrip().startswith("UPDATE scene_appearance_state SET journal_json"):
                    result = self.connection.execute(statement, parameters)
                    self.journal_pending = True
                    return result
                if statement.strip().upper() == "COMMIT" and self.journal_pending:
                    self.journal_pending = False
                    raise sqlite3.OperationalError("injected before journal commit")
                return self.connection.execute(statement, parameters)

        @contextmanager
        def fail_journal_commit():
            with original_connection() as connection:
                yield BeforeJournalCommit(connection)

        monkeypatch.setattr(database, "connection", fail_journal_commit)
        journal_failure = client.put(
            "/api/admin/scene", headers=headers, json={"proposal": proposal, "expected": expected}
        )
        assert journal_failure.status_code == 503
        monkeypatch.setattr(database, "connection", original_connection)
        assert portfolio._draft_path.read_bytes() == original_raw
        with database.connection() as connection:
            row = connection.execute(
                "SELECT journal_json, issued_revision FROM scene_appearance_state WHERE singleton=1"
            ).fetchone()
        assert row["journal_json"] is None
        assert row["issued_revision"] == state["issued_revision"]

        original_write_draft = portfolio.write_draft_locked

        def fail_after_draft_replace(draft) -> None:
            original_write_draft(draft)
            raise LocalPortfolioError("PORTFOLIO_WRITE_FAILED")

        monkeypatch.setattr(portfolio, "write_draft_locked", fail_after_draft_replace)
        draft_failure = client.put(
            "/api/admin/scene", headers=headers, json={"proposal": proposal, "expected": expected}
        )
        assert draft_failure.status_code == 503
        monkeypatch.setattr(portfolio, "write_draft_locked", original_write_draft)
        assert portfolio._draft_path.read_bytes() == original_raw
        with database.connection() as connection:
            row = connection.execute(
                "SELECT journal_json, issued_revision FROM scene_appearance_state WHERE singleton=1"
            ).fetchone()
        assert row["journal_json"] is None
        assert row["issued_revision"] == state["issued_revision"]

        commit_faults: list[str] = []

        class AppearanceCommitBoundary:
            def __init__(self, connection, *, after_commit: bool) -> None:
                self.connection = connection
                self.appearance_updated = False
                self.after_commit = after_commit

            def execute(self, statement: str, parameters=()):
                normalized = " ".join(statement.split())
                if normalized.startswith("UPDATE scene_appearance_state SET issued_revision"):
                    result = self.connection.execute(statement, parameters)
                    self.appearance_updated = True
                    return result
                if statement.strip().upper() == "COMMIT" and self.appearance_updated:
                    self.appearance_updated = False
                    if not self.after_commit:
                        commit_faults.append("before")
                        raise sqlite3.OperationalError("injected before appearance commit")
                    self.connection.execute(statement, parameters)
                    commit_faults.append("after")
                    raise sqlite3.OperationalError("injected after appearance commit")
                return self.connection.execute(statement, parameters)

        @contextmanager
        def appearance_commit_failure(*, after_commit: bool):
            with original_connection() as connection:
                yield AppearanceCommitBoundary(connection, after_commit=after_commit)

        @contextmanager
        def fail_before_appearance_commit():
            with appearance_commit_failure(after_commit=False) as connection:
                yield connection

        monkeypatch.setattr(database, "connection", fail_before_appearance_commit)
        appearance_rollback = client.put(
            "/api/admin/scene", headers=headers, json={"proposal": proposal, "expected": expected}
        )
        monkeypatch.setattr(database, "connection", original_connection)
        assert appearance_rollback.status_code == 503
        assert portfolio._draft_path.read_bytes() == original_raw
        with database.connection() as connection:
            row = connection.execute(
                "SELECT journal_json, issued_revision FROM scene_appearance_state WHERE singleton=1"
            ).fetchone()
        assert row["journal_json"] is None
        assert row["issued_revision"] == state["issued_revision"]
        assert commit_faults == ["before"]

        @contextmanager
        def fail_after_appearance_commit():
            with appearance_commit_failure(after_commit=True) as connection:
                yield connection

        monkeypatch.setattr(database, "connection", fail_after_appearance_commit)
        committed = client.put(
            "/api/admin/scene", headers=headers, json={"proposal": proposal, "expected": expected}
        )
        monkeypatch.setattr(database, "connection", original_connection)
        assert committed.status_code == 200, committed.text
        published = committed.json()["scene_state"]
        assert published["appearance_revision"] > state["appearance_revision"]
        assert published["character_revision"] == published["appearance_revision"]
        assert portfolio.read() is not None
        assert portfolio.read().revision != state["draft_revision"]
        with database.connection() as connection:
            row = connection.execute(
                "SELECT journal_json, appearance_revision "
                "FROM scene_appearance_state WHERE singleton=1"
            ).fetchone()
        assert row["journal_json"] is None
        assert row["appearance_revision"] == published["appearance_revision"]
        assert commit_faults == ["before", "after"]


def test_appearance_apply_full_build_apply_full_build_preserves_revision_and_settings(
    tmp_path: Path,
) -> None:
    app = build_application(tmp_path / "runtime", tmp_path / "web", _ORIGIN)
    with TestClient(app, base_url=_ORIGIN) as client:
        login = client.post(
            "/api/admin/session",
            headers={"Origin": _ORIGIN},
            json={"username": FIXTURE_USERNAME, "password": FIXTURE_PASSWORD},
        )
        assert login.status_code == 200
        headers = {"Origin": _ORIGIN, "X-CSRF-Token": login.json()["csrf_token"]}
        client.headers["Referer"] = f"{_ORIGIN}/admin"

        def upload_background(name: str, color: tuple[int, int, int, int]) -> str:
            output = io.BytesIO()
            Image.new("RGBA", (960, 540), color).save(output, "PNG")
            response = client.post(
                "/api/admin/assets/scene/background-drafts",
                headers=headers,
                files={"file": (name, output.getvalue(), "image/png")},
            )
            assert response.status_code == 200, response.text
            return str(response.json()["draft_id"])

        def publish_and_rebuild(state: dict[str, object], background: str, accent: str):
            proposal = _proposal(state, background=background)
            proposal["accent"] = accent
            applied = client.put(
                "/api/admin/scene",
                headers=headers,
                json={"proposal": proposal, "expected": _expected_state(state)},
            )
            assert applied.status_code == 200, applied.text
            applied_state = applied.json()["scene_state"]
            operations = app.application.state.admin_operations
            publication = operations.local_publication
            store = operations.local_portfolio
            assert publication is not None and store is not None
            saved_draft = store.read()
            assert saved_draft is not None
            job = publication.status()
            result = publication.prepare(
                expected_revision=saved_draft.revision,
                embedding_profile_id=job["profile_id"],
                chat_profile_id=job["chat_profile_id"],
            )
            coordinator = app.application.state.embedding_reindex_coordinator
            completed = coordinator.wait(str(job["profile_id"]), timeout=60)
            assert completed.active, result
            rebuilt = app.application.state.scene_supplier().scene_state()
            profile = client.get("/api/public/profile?locale=en")
            assert profile.status_code == 200
            character = profile.json()["character"]
            assert character["revision"] == applied_state["character_revision"]
            assert character["scene"]["revision"] == applied_state["character_revision"]
            image = client.get(character["scene"]["background_url"])
            assert image.status_code == 200
            return applied_state, rebuilt, image.content

        first_image_id = upload_background("first.png", (28, 58, 90, 255))
        initial = client.get("/api/admin/portfolio/status").json()["scene_state"]
        first, first_rebuilt, first_background = publish_and_rebuild(
            initial, f"draft:{first_image_id}", "#3b82f6"
        )
        assert first_rebuilt["settings"]["accent"] == "#3b82f6"
        assert first_rebuilt["settings"]["dim"] == "auto"
        assert first_rebuilt["settings"]["background"] == "current"
        assert first_rebuilt["scene"]["background_dim"] == first["scene"]["background_dim"]

        second_image_id = upload_background("second.png", (120, 54, 33, 255))
        second, second_rebuilt, second_background = publish_and_rebuild(
            first_rebuilt, f"draft:{second_image_id}", "#8b5cf6"
        )
        assert second["character_revision"] > first["character_revision"]
        assert second_rebuilt["character_revision"] == second["character_revision"]
        assert second_rebuilt["settings"]["accent"] == "#8b5cf6"
        assert second_rebuilt["settings"]["dim"] == "auto"
        assert second_rebuilt["settings"]["background"] == "current"
        assert second_rebuilt["scene"]["background_dim"] == second["scene"]["background_dim"]
        assert second_background != first_background


def _seed_pending_appearance_recovery(service: AdminSceneService) -> tuple[bytes, str]:
    portfolio = service.portfolio
    assert portfolio is not None
    with service._portfolio_lock():
        old_draft = portfolio._read_unlocked()
        assert old_draft is not None
        old_raw = portfolio.read_raw_locked()
        assert old_raw is not None
        state = service._state_row()
        config = parse_public_config_bytes(old_draft.content.encode("utf-8"))
        new_draft = portfolio.build_scene_draft_locked(
            config.character.scene.model_dump(mode="json"),
            None,
            config.character.revision + 1,
        )
        assert new_draft is not None
        backup_id = secrets.token_hex(24)
        backup_sha256 = _sha(old_raw)
        service._write_recovery_backup(backup_id, old_raw)
        journal = {
            "backup_id": backup_id,
            "backup_sha256": backup_sha256,
            "old_draft_present": True,
            "old_draft_revision": old_draft.revision,
            "new_draft_revision": new_draft.revision,
            "old_scene_sha256": _sha(str(state["scene_json"] or "").encode()),
            "old_pointer_sha256": _state_pointer_digest(state),
            "new_scene_sha256": hashlib.sha256(b"pending-scene").hexdigest(),
            "new_background_sha256": None,
        }
        with service.database.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                "UPDATE scene_appearance_state SET journal_json=? WHERE singleton=1",
                (_json_text(journal),),
            )
            connection.execute("COMMIT")
        portfolio.write_draft_locked(new_draft)
        return old_raw, new_draft.revision


def test_scene_recovery_restart_and_invalid_journal_identity_fail_closed(
    tmp_path: Path, monkeypatch, request: pytest.FixtureRequest
) -> None:
    app = build_application(tmp_path / "runtime", tmp_path / "web", _ORIGIN)
    manager = app.application.state.bundle_manager
    coordinator = app.application.state.embedding_reindex_coordinator

    def cleanup() -> None:
        coordinator.shutdown()
        with manager.acquire() as index:
            index.close()

    request.addfinalizer(cleanup)
    service = app.application.state.scene_supplier()
    assert isinstance(service, AdminSceneService)
    old_raw, candidate_revision = _seed_pending_appearance_recovery(service)
    restarted = AdminSceneService(
        manager=service.manager,
        database=service.database,
        data_directory=service.data_directory,
        portfolio=service.portfolio,
        registry=service.registry,
    )
    with restarted._portfolio_lock():
        restarted._recover_unlocked()
    assert restarted.portfolio is not None
    assert restarted.portfolio._draft_path.read_bytes() == old_raw
    assert restarted.portfolio.read().revision != candidate_revision
    with restarted.database.connection() as connection:
        row = connection.execute(
            "SELECT journal_json FROM scene_appearance_state WHERE singleton=1"
        ).fetchone()
    assert row["journal_json"] is None

    for corruption in ("extra-key", "old-revision", "pointer", "oversized"):
        old_raw, candidate_revision = _seed_pending_appearance_recovery(restarted)
        with restarted.database.connection() as connection:
            state_row = connection.execute(
                "SELECT journal_json FROM scene_appearance_state WHERE singleton=1"
            ).fetchone()
            journal = json.loads(state_row["journal_json"])
        if corruption == "extra-key":
            journal["requester_path"] = "C:/untrusted/path"
            with restarted.database.connection() as connection:
                connection.execute("BEGIN IMMEDIATE")
                connection.execute(
                    "UPDATE scene_appearance_state SET journal_json=? WHERE singleton=1",
                    (_json_text(journal),),
                )
                connection.execute("COMMIT")
        elif corruption == "old-revision":
            journal["old_draft_revision"] = "f" * 64
            with restarted.database.connection() as connection:
                connection.execute("BEGIN IMMEDIATE")
                connection.execute(
                    "UPDATE scene_appearance_state SET journal_json=? WHERE singleton=1",
                    (_json_text(journal),),
                )
                connection.execute("COMMIT")
        elif corruption == "pointer":
            with restarted.database.connection() as connection:
                connection.execute("BEGIN IMMEDIATE")
                connection.execute(
                    "UPDATE scene_appearance_state SET issued_revision=issued_revision+1 "
                    "WHERE singleton=1"
                )
                connection.execute("COMMIT")
        else:
            import reponpc.admin.scene as scene_module

            backup = restarted.recovery_root / f"{journal['backup_id']}.json"
            backup.write_bytes(b"oversized")
            monkeypatch.setattr(scene_module, "_JSON_MAX_BYTES", 4)
            journal["backup_sha256"] = _sha(b"oversized")
            with restarted.database.connection() as connection:
                connection.execute("BEGIN IMMEDIATE")
                connection.execute(
                    "UPDATE scene_appearance_state SET journal_json=? WHERE singleton=1",
                    (_json_text(journal),),
                )
                connection.execute("COMMIT")
        with restarted._portfolio_lock(), pytest.raises(SceneServiceError) as error:
            restarted._recover_unlocked()
        assert error.value.code == "SCENE_RECOVERY_FAILED"
        assert restarted.portfolio is not None
        assert restarted.portfolio.read().revision == candidate_revision
        with restarted.database.connection() as connection:
            still_pending = connection.execute(
                "SELECT journal_json FROM scene_appearance_state WHERE singleton=1"
            ).fetchone()
        assert still_pending["journal_json"] is not None
        if corruption == "oversized":
            monkeypatch.undo()
