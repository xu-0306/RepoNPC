"""Owner-scoped scene drafts and lease-bound published appearance snapshots."""

from __future__ import annotations

import contextlib
import hashlib
import io
import json
import os
import re
import secrets
import sqlite3
import tempfile
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from PIL import Image
from pydantic import ValidationError

from reponpc.admin.local_portfolio import (
    _JSON_MAX_BYTES,
    LocalPortfolioDraft,
    LocalPortfolioError,
    LocalPortfolioStore,
    _decode_draft,
)
from reponpc.bundles.archive import BundleError
from reponpc.bundles.manager import BundleActivationError, BundleManager
from reponpc.bundles.manifest import ManifestError, parse_bundle_manifest
from reponpc.cards.assets import SpriteValidationError, validate_sprite
from reponpc.config.models import SceneConfig
from reponpc.indexing.public_profile import (
    BilingualPublicProfile,
    PublicProfileError,
    normalize_public_profile_scene,
    parse_public_profile_bytes,
    validate_public_profile_metadata,
)
from reponpc.runtime.database import RuntimeDatabase, RuntimeDatabaseError
from reponpc.scene.images import CanonicalSceneImage, SceneImageError, validate_scene_image
from reponpc.scene.registry import DEFAULT_SCHEME_ID, SceneRegistry, default_scene_registry
from reponpc.scene.resolve import (
    PublicScene,
    SceneNotice,
    SceneResolutionError,
    _average_edge_color,
    resolve_scene,
    validate_npc_separation,
)

_HASH_RE = re.compile(r"^[0-9a-f]{64}$")
_DRAFT_ID_RE = re.compile(r"^[A-Za-z0-9_-]{32,64}$")


class SceneServiceError(ValueError):
    """Safe stable appearance failure code for the HTTP boundary."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__("scene operation failed")


@dataclass(frozen=True, slots=True)
class SceneBackgroundDraft:
    draft_id: str
    image: CanonicalSceneImage
    expires_at: str


@dataclass(frozen=True, slots=True)
class PublishedProfileSnapshot:
    """One profile and its assets, captured while one immutable bundle is leased."""

    document: BilingualPublicProfile
    bundle_id: str
    public_directory: Path
    sprite_content: bytes
    sprite_sha256: str
    source_character_revision: int
    character_revision: int
    appearance_revision: int | None
    background_content: bytes | None
    settings: dict[str, object] | None
    issued_revision: int


class AdminSceneService:
    """Coordinate saved appearance state with one bundle and one draft store."""

    def __init__(
        self,
        *,
        manager: BundleManager,
        database: RuntimeDatabase | None,
        data_directory: Path,
        portfolio: LocalPortfolioStore | None = None,
        registry: SceneRegistry | None = None,
    ) -> None:
        self.manager = manager
        self.database = database
        self.data_directory = Path(data_directory)
        self.portfolio = portfolio
        self.registry = registry or default_scene_registry()
        self.draft_root = self.data_directory / "scene-background-drafts"
        self.appearance_root = self.data_directory / "scene-appearance"
        self.asset_root = self.appearance_root / "assets"
        self.recovery_root = self.appearance_root / "recovery"

    @contextlib.contextmanager
    def published_profile(self) -> Iterator[PublishedProfileSnapshot]:
        """Read the full public profile and overlay under one bundle lease."""
        try:
            with self.manager.acquire_snapshot() as (_index, bundle_id, public_directory):
                snapshot = self._snapshot_from_lease(bundle_id, public_directory)
                yield snapshot
        except BundleActivationError as exc:
            raise SceneServiceError("PUBLIC_SCENE_UNAVAILABLE") from exc

    def scene_state(self) -> dict[str, object]:
        with self.published_profile() as snapshot, self._portfolio_lock():
            self._recover_unlocked()
            state = self._state_row()
            if int(state["issued_revision"]) != snapshot.issued_revision:
                raise SceneServiceError("SCENE_CONFLICT")
            draft = self.portfolio._read_unlocked() if self.portfolio else None
            scene = snapshot.document.character.scene
            if scene is None:
                raise SceneServiceError("PUBLIC_SCENE_UNAVAILABLE")
            return self._scene_state_payload(
                snapshot=snapshot,
                scene=scene,
                settings=snapshot.settings,
                character_revision=snapshot.character_revision,
                appearance_revision=snapshot.appearance_revision or 0,
                draft_revision=draft.revision if draft else None,
                issued_revision=snapshot.issued_revision,
            )

    def _scene_state_payload(
        self,
        *,
        snapshot: PublishedProfileSnapshot,
        scene: PublicScene,
        settings: dict[str, object] | None,
        character_revision: int,
        appearance_revision: int,
        draft_revision: str | None,
        issued_revision: int,
    ) -> dict[str, object]:
        return {
            "source_bundle_id": snapshot.bundle_id,
            "source_character_revision": snapshot.source_character_revision,
            "character_revision": character_revision,
            "appearance_revision": appearance_revision,
            "sprite_sha256": snapshot.sprite_sha256,
            "draft_revision": draft_revision,
            "issued_revision": issued_revision,
            "scene": scene.model_dump(mode="json"),
            "settings": settings,
            "defaults": _default_settings_payload(),
            "schemes": self._resolved_scheme_catalog(snapshot),
        }

    def _resolved_scheme_catalog(
        self, snapshot: PublishedProfileSnapshot
    ) -> list[dict[str, object]]:
        """Resolve gallery themes against the same leased canonical sprite."""
        settings = SceneConfig.model_validate(
            {"color_scheme": next(iter(self.registry.schemes))},
            context={"scene_registry": self.registry},
        )
        public = self._resolve(
            settings, snapshot.sprite_content, snapshot.character_revision
        ).public
        return [
            {
                "id": scheme.id,
                "version": scheme.version,
                "labels": dict(scheme.label),
                "themes": scheme.themes.model_dump(mode="json"),
                "npc_plate": scheme.npc_plate.model_dump(mode="json"),
            }
            for scheme in public.schemes
        ]

    def create_background_draft(
        self, *, session_hash: str, content: bytes, filename: str
    ) -> dict[str, object]:
        try:
            image = validate_scene_image(content, filename=filename)
        except SceneImageError as exc:
            raise SceneServiceError(exc.code) from None
        now = datetime.now(UTC)
        expires = now + timedelta(hours=24)
        draft_id = secrets.token_urlsafe(32)
        draft_hash = hashlib.sha256(draft_id.encode("ascii")).hexdigest()
        with self._portfolio_lock():
            self._atomic_content_addressed(
                self.draft_root, image.sha256, image.format, image.content
            )
            try:
                with self._database().connection() as connection:
                    connection.execute("BEGIN IMMEDIATE")
                    connection.execute(
                        "DELETE FROM scene_background_drafts WHERE expires_at <= ?",
                        (_timestamp(now),),
                    )
                    connection.execute(
                        """INSERT INTO scene_background_drafts(
                               draft_id_hash, session_hash, content_sha256, extension,
                               created_at, expires_at
                           ) VALUES (?, ?, ?, ?, ?, ?)
                           ON CONFLICT(session_hash) DO UPDATE SET
                               draft_id_hash=excluded.draft_id_hash,
                               content_sha256=excluded.content_sha256,
                               extension=excluded.extension,
                               created_at=excluded.created_at,
                               expires_at=excluded.expires_at""",
                        (
                            draft_hash,
                            session_hash,
                            image.sha256,
                            image.format,
                            _timestamp(now),
                            _timestamp(expires),
                        ),
                    )
                    connection.execute("COMMIT")
            except sqlite3.Error as exc:
                self._collect_draft_files()
                raise SceneServiceError("SCENE_DRAFT_WRITE_FAILED") from exc
            self._collect_draft_files()
        return {
            "draft_id": draft_id,
            "width": image.width,
            "height": image.height,
            "format": image.format,
            "notices": [],
        }

    def get_background_draft(self, *, session_hash: str, draft_id: str) -> SceneBackgroundDraft:
        with self._portfolio_lock():
            row = self._draft_row(session_hash=session_hash, draft_id=draft_id)
            image = self._read_draft_image(str(row["content_sha256"]), str(row["extension"]))
            return SceneBackgroundDraft(
                draft_id=draft_id, image=image, expires_at=str(row["expires_at"])
            )

    def cleanup_expired_background_drafts(self) -> int:
        """Delete expired draft rows and collect their unreferenced image bytes."""

        with self._portfolio_lock():
            now = _timestamp(datetime.now(UTC))
            try:
                with self._database().connection() as connection:
                    cursor = connection.execute(
                        "DELETE FROM scene_background_drafts WHERE expires_at <= ?", (now,)
                    )
                    deleted = max(cursor.rowcount, 0)
            except sqlite3.Error as exc:
                raise SceneServiceError("SCENE_DRAFT_WRITE_FAILED") from exc
            self._collect_draft_files()
            return deleted

    def delete_background_draft(self, *, session_hash: str, draft_id: str) -> None:
        if not _DRAFT_ID_RE.fullmatch(draft_id):
            raise SceneServiceError("NOT_FOUND")
        digest = hashlib.sha256(draft_id.encode("ascii")).hexdigest()
        with self._portfolio_lock():
            with self._database().connection() as connection:
                connection.execute(
                    "DELETE FROM scene_background_drafts WHERE draft_id_hash=? AND session_hash=?",
                    (digest, session_hash),
                )
            self._collect_draft_files()

    def preview(self, *, session_hash: str, proposal: dict[str, object]) -> dict[str, object]:
        with self.published_profile() as snapshot:
            background, _selected_ref = self._background_for_proposal(
                session_hash=session_hash, proposal=proposal, snapshot=snapshot
            )
            settings = _scene_settings(
                proposal, background_present=background is not None, registry=self.registry
            )
            revision = self._next_revision(snapshot)
            resolution = self._resolve(
                settings, snapshot.sprite_content, revision, background_content=background
            )
            notices = [_notice_dict(item) for item in resolution.notices]
            notices.extend(_image_notices(background, proposal))
            return {"scene": resolution.public.model_dump(mode="json"), "notices": notices}

    def apply(
        self,
        *,
        session_hash: str,
        proposal: dict[str, object],
        expected: dict[str, object],
    ) -> dict[str, object]:
        with self.manager.acquire_snapshot() as (_index, bundle_id, public_directory):
            snapshot = self._snapshot_from_lease(bundle_id, public_directory)
            with self._portfolio_lock():
                self._recover_unlocked()
                state = self._state_row()
                draft = self.portfolio._read_unlocked() if self.portfolio else None
                if not self._expected_matches(
                    expected, snapshot=snapshot, state=state, draft=draft
                ):
                    raise SceneServiceError("SCENE_CONFLICT")
                if self.manager.status().active_bundle_id != bundle_id:
                    raise SceneServiceError("SCENE_CONFLICT")
                background, _ref = self._background_for_proposal(
                    session_hash=session_hash, proposal=proposal, snapshot=snapshot
                )
                settings = _scene_settings(
                    proposal, background_present=background is not None, registry=self.registry
                )
                new_revision = (
                    max(
                        int(state["issued_revision"]),
                        snapshot.source_character_revision,
                        _draft_character_revision(draft),
                    )
                    + 1
                )
                resolution = self._resolve(
                    settings,
                    snapshot.sprite_content,
                    new_revision,
                    background_content=background,
                )
                self._validate_scene_stage(resolution.public, snapshot.sprite_content)
                new_public = resolution.public
                old_raw = self._read_draft_raw_locked() if self.portfolio else None
                backup_id = secrets.token_hex(24)
                backup_digest = _sha(old_raw or b"")
                self._write_recovery_backup(backup_id, old_raw)
                background_hash: str | None
                background_extension: str | None
                if background is not None:
                    extension = "webp" if background.startswith(b"RIFF") else "png"
                    image = validate_scene_image(background, filename=f"applied.{extension}")
                    self._atomic_content_addressed(
                        self.asset_root, image.sha256, image.format, image.content
                    )
                    background_hash, background_extension = image.sha256, image.format
                else:
                    background_hash = background_extension = None
                new_draft = (
                    self.portfolio.build_scene_draft_locked(
                        settings.model_dump(mode="json"), background, new_revision
                    )
                    if self.portfolio
                    else None
                )
                old_state_digest = _sha(str(state["scene_json"] or "").encode())
                journal = {
                    "backup_id": backup_id,
                    "backup_sha256": backup_digest,
                    "old_draft_present": old_raw is not None,
                    "old_draft_revision": draft.revision if draft else None,
                    "new_draft_revision": new_draft.revision if new_draft else None,
                    "old_scene_sha256": old_state_digest,
                    "old_pointer_sha256": _state_pointer_digest(state),
                    "new_scene_sha256": _sha(_json_bytes(new_public.model_dump(mode="json"))),
                    "new_background_sha256": background_hash,
                }
                try:
                    with self._database().connection() as connection:
                        connection.execute("BEGIN IMMEDIATE")
                        connection.execute(
                            "UPDATE scene_appearance_state SET journal_json=? WHERE singleton=1",
                            (_json_text(journal),),
                        )
                        connection.execute("COMMIT")
                except sqlite3.Error as exc:
                    if self.portfolio:
                        self.portfolio.restore_raw_locked(old_raw)
                    raise SceneServiceError("SCENE_PUBLISH_FAILED") from exc
                try:
                    # Keep bundle activation out until the draft and pointer commit together.
                    # The manager guard is entered before SQLite's write transaction.
                    with self.manager.guard_active_bundle(bundle_id):
                        if self.portfolio and new_draft is not None:
                            self.portfolio.write_draft_locked(new_draft)
                        with self._database().connection() as connection:
                            connection.execute("BEGIN IMMEDIATE")
                            connection.execute(
                                """UPDATE scene_appearance_state SET
                                       issued_revision=?, source_bundle_id=?, sprite_sha256=?,
                                       character_revision=?, appearance_revision=?, scene_json=?,
                                       background_sha256=?, background_extension=?,
                                       journal_json=NULL
                                   WHERE singleton=1""",
                                (
                                    new_revision,
                                    bundle_id,
                                    snapshot.sprite_sha256,
                                    snapshot.source_character_revision,
                                    new_revision,
                                    _json_text(
                                        {
                                            "public": new_public.model_dump(mode="json"),
                                            "settings": settings.model_dump(mode="json"),
                                        }
                                    ),
                                    background_hash,
                                    background_extension,
                                ),
                            )
                            connection.execute("COMMIT")
                except (
                    BundleActivationError,
                    SceneServiceError,
                    sqlite3.Error,
                    LocalPortfolioError,
                    RuntimeDatabaseError,
                ) as exc:
                    self._recover_unlocked()
                    if not self._new_publication_is_committed(
                        bundle_id=bundle_id,
                        snapshot=snapshot,
                        revision=new_revision,
                        scene=new_public,
                        settings=settings,
                        background_sha256=background_hash,
                        background_extension=background_extension,
                        draft=new_draft,
                    ):
                        if isinstance(exc, BundleActivationError):
                            raise SceneServiceError("SCENE_CONFLICT") from exc
                        if isinstance(exc, SceneServiceError):
                            raise
                        raise SceneServiceError("SCENE_PUBLISH_FAILED") from exc
                self._remove_backup(backup_id)
                return {
                    "scene": new_public.model_dump(mode="json"),
                    "notices": [_notice_dict(item) for item in resolution.notices]
                    + _image_notices(background, proposal),
                    "scene_state": self._scene_state_payload(
                        snapshot=snapshot,
                        scene=new_public,
                        settings=_settings_payload(settings, new_public),
                        character_revision=new_revision,
                        appearance_revision=new_revision,
                        draft_revision=new_draft.revision if new_draft else None,
                        issued_revision=new_revision,
                    ),
                }

    def background_for_revision(self, revision: int) -> tuple[bytes, str, str] | None:
        with self.published_profile() as snapshot:
            if snapshot.character_revision != revision or snapshot.background_content is None:
                return None
            extension = "webp" if snapshot.background_content.startswith(b"RIFF") else "png"
            return snapshot.background_content, extension, snapshot.bundle_id

    def _snapshot_from_lease(
        self, bundle_id: str, public_directory: Path
    ) -> PublishedProfileSnapshot:
        """Build the single normalized profile view while the caller holds its lease."""
        try:
            manifest = parse_bundle_manifest(
                (public_directory.parent / "manifest.json").read_bytes()
            )
            if manifest.bundle_id != bundle_id:
                raise SceneServiceError("PUBLIC_SCENE_UNAVAILABLE")
            sprite_content = (public_directory / "character.png").read_bytes()
            canonical = validate_sprite(sprite_content)
            if canonical.content != sprite_content:
                raise ValueError("public sprite is not canonical")
            profile = parse_public_profile_bytes((public_directory / "profile.json").read_bytes())
            validate_public_profile_metadata(
                profile,
                index_version=bundle_id,
                built_at=manifest.built_at,
                repository_count=dict(manifest.statistics)["repositories"],
            )
            had_scene = profile.character.scene is not None
            profile = normalize_public_profile_scene(profile, sprite_content=sprite_content)
            source_revision = profile.character.revision
        except SceneServiceError:
            raise
        except (
            OSError,
            KeyError,
            BundleError,
            ManifestError,
            PublicProfileError,
            SpriteValidationError,
            SceneResolutionError,
            ValueError,
        ) as exc:
            raise SceneServiceError("PUBLIC_SCENE_UNAVAILABLE") from exc
        self._validate_scene_stage(profile.character.scene, sprite_content)
        try:
            if self.database is None:
                state = None
                scene = profile.character.scene
                background = self._bundle_background(
                    public_directory=public_directory,
                    bundle_id=bundle_id,
                    scene=scene,
                )
                settings = _settings_from_public(scene) if not had_scene else None
                appearance_revision = None
                issued_revision = 0
            else:
                with self._portfolio_lock():
                    self._recover_unlocked()
                    state = self._state_row()
                    if _binding_matches(
                        state,
                        bundle_id=bundle_id,
                        sprite_sha256=canonical.sha256,
                        character_revision=source_revision,
                    ):
                        wrapper = json.loads(
                            str(state["scene_json"]), object_pairs_hook=_json_unique
                        )
                        if not isinstance(wrapper, dict) or set(wrapper) != {"public", "settings"}:
                            raise ValueError
                        scene = PublicScene.model_validate(wrapper["public"])
                        if scene.revision != int(state["appearance_revision"]):
                            raise ValueError
                        raw_settings = SceneConfig.model_validate(
                            wrapper["settings"], context={"scene_registry": self.registry}
                        )
                        self._validate_scene_stage(scene, sprite_content)
                        background = self._appearance_background(state, scene)
                        if not _settings_match_public(
                            raw_settings,
                            scene,
                            sprite_content=sprite_content,
                            background_content=background,
                            registry=self.registry,
                        ):
                            raise ValueError
                        settings = _settings_payload(raw_settings, scene)
                        appearance_revision = int(state["appearance_revision"])
                        profile = profile.model_copy(
                            update={
                                "character": profile.character.model_copy(
                                    update={"revision": appearance_revision, "scene": scene}
                                )
                            }
                        )
                    else:
                        scene = profile.character.scene
                        background = self._bundle_background(
                            public_directory=public_directory,
                            bundle_id=bundle_id,
                            scene=scene,
                        )
                        settings = self._read_presentation_receipt(
                            bundle_id=bundle_id,
                            sprite_sha256=canonical.sha256,
                            source_character_revision=source_revision,
                            scene=scene,
                            sprite_content=sprite_content,
                            background_content=background,
                        )
                        if settings is None and not had_scene:
                            settings = _settings_from_public(scene)
                        appearance_revision = None
                    issued_revision = int(state["issued_revision"])
            if scene is None:
                raise ValueError("scene missing")
            return PublishedProfileSnapshot(
                profile,
                bundle_id,
                public_directory,
                sprite_content,
                canonical.sha256,
                source_revision,
                appearance_revision or source_revision,
                appearance_revision,
                background,
                settings,
                issued_revision,
            )
        except SceneServiceError:
            raise
        except (
            OSError,
            KeyError,
            BundleError,
            ManifestError,
            PublicProfileError,
            SpriteValidationError,
            SceneResolutionError,
            ValidationError,
            ValueError,
        ) as exc:
            raise SceneServiceError("PUBLIC_SCENE_UNAVAILABLE") from exc

    def _resolve(
        self,
        settings: SceneConfig,
        sprite: bytes,
        revision: int,
        *,
        background_content: bytes | None = None,
    ):
        try:
            return resolve_scene(
                settings,
                sprite_content=sprite,
                revision=revision,
                registry=self.registry,
                background_content=background_content,
            )
        except SceneResolutionError as exc:
            raise SceneServiceError(exc.code) from None

    def _background_for_proposal(
        self,
        *,
        session_hash: str,
        proposal: dict[str, object],
        snapshot: PublishedProfileSnapshot,
    ) -> tuple[bytes | None, str]:
        background = proposal.get("background", "current")
        if not isinstance(background, str):
            raise SceneServiceError("SCENE_SETTINGS_INVALID")
        if background == "none":
            return None, background
        if background == "current":
            return snapshot.background_content, background
        if background.startswith("draft:"):
            draft = self.get_background_draft(
                session_hash=session_hash, draft_id=background.removeprefix("draft:")
            )
            return draft.image.content, background
        raise SceneServiceError("SCENE_SETTINGS_INVALID")

    def _expected_matches(
        self,
        expected: dict[str, object],
        *,
        snapshot: PublishedProfileSnapshot,
        state: sqlite3.Row,
        draft: LocalPortfolioDraft | None,
    ) -> bool:
        return (
            int(state["issued_revision"]) == snapshot.issued_revision
            and expected.get("source_bundle_id") == snapshot.bundle_id
            and expected.get("sprite_sha256") == snapshot.sprite_sha256
            and expected.get("character_revision") == snapshot.character_revision
            and expected.get("appearance_revision") == (snapshot.appearance_revision or 0)
            and expected.get("draft_revision") == (draft.revision if draft else None)
            and expected.get("source_character_revision") == snapshot.source_character_revision
        )

    def _next_revision(self, snapshot: PublishedProfileSnapshot) -> int:
        with self._portfolio_lock():
            self._recover_unlocked()
            state = self._state_row()
            draft = self.portfolio._read_unlocked() if self.portfolio else None
            return (
                max(
                    int(state["issued_revision"]),
                    snapshot.source_character_revision,
                    _draft_character_revision(draft),
                )
                + 1
            )

    def _appearance_background(self, state: sqlite3.Row, scene: PublicScene) -> bytes | None:
        digest = state["background_sha256"]
        extension = state["background_extension"]
        if digest is None:
            if scene.background_url is not None:
                raise ValueError("scene image binding is missing")
            return None
        if (
            not isinstance(digest, str)
            or not _HASH_RE.fullmatch(digest)
            or extension not in {"png", "webp"}
        ):
            raise ValueError("scene image binding is invalid")
        if scene.background_url != f"/api/public/scene-background?rev={scene.revision}":
            raise ValueError("scene image URL is invalid")
        path = self.asset_root / f"{digest}.{extension}"
        if path.is_symlink() or not path.is_file() or path.stat().st_size > 2 * 1024 * 1024:
            raise ValueError("scene image is unavailable")
        content = path.read_bytes()
        image = validate_scene_image(content, filename=f"background.{extension}")
        if image.sha256 != digest or image.content != content:
            raise ValueError("scene image checksum is invalid")
        return content

    def _bundle_background(
        self, *, public_directory: Path, bundle_id: str, scene: PublicScene | None
    ) -> bytes | None:
        if scene is None or scene.background_url is None:
            return None
        try:
            manifest = parse_bundle_manifest(
                (public_directory.parent / "manifest.json").read_bytes()
            )
            if manifest.bundle_id != bundle_id:
                raise ValueError
            paths = [item.path for item in manifest.files if item.path.startswith("public/scene/")]
            if len(paths) != 1:
                raise ValueError
            match = re.fullmatch(r"public/scene/([0-9a-f]{64})\.(png|webp)", paths[0])
            if match is None:
                raise ValueError
            path = public_directory / paths[0].removeprefix("public/")
            if path.is_symlink() or not path.is_file() or path.stat().st_size > 2 * 1024 * 1024:
                raise ValueError
            content = path.read_bytes()
            image = validate_scene_image(content, filename=f"background.{match.group(2)}")
            if image.sha256 != match.group(1) or image.content != content:
                raise ValueError
            return content
        except OSError, ManifestError, SceneImageError, ValueError:
            raise SceneServiceError("PUBLIC_SCENE_UNAVAILABLE") from None

    def _read_presentation_receipt(
        self,
        *,
        bundle_id: str,
        sprite_sha256: str,
        source_character_revision: int,
        scene: PublicScene | None,
        sprite_content: bytes,
        background_content: bytes | None,
    ) -> dict[str, object] | None:
        if scene is None or not _HASH_RE.fullmatch(sprite_sha256):
            return None
        path = self.appearance_root / "receipts" / f"{bundle_id}.{sprite_sha256}.json"
        try:
            if path.is_symlink() or not path.is_file() or path.stat().st_size > 65_536:
                return None
            value = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_json_unique)
            if not isinstance(value, dict) or set(value) != {
                "bundle_id",
                "sprite_sha256",
                "source_character_revision",
                "public",
                "settings",
            }:
                return None
            if (
                value["bundle_id"] != bundle_id
                or value["sprite_sha256"] != sprite_sha256
                or value["source_character_revision"] != source_character_revision
                or value["public"] != scene.model_dump(mode="json")
            ):
                return None
            settings = SceneConfig.model_validate(
                value["settings"], context={"scene_registry": self.registry}
            )
            if (
                settings.color_mode != scene.color_mode
                or settings.visitor_mode_toggle != scene.visitor_mode_toggle
                or not _settings_match_public(
                    settings,
                    scene,
                    sprite_content=sprite_content,
                    background_content=background_content,
                    registry=self.registry,
                )
            ):
                return None
            return _settings_payload(settings, scene)
        except OSError, UnicodeError, json.JSONDecodeError, TypeError, ValueError:
            return None

    def _validate_scene_stage(self, scene: PublicScene | None, sprite: bytes) -> None:
        if scene is None:
            raise SceneServiceError("PUBLIC_SCENE_UNAVAILABLE")
        try:
            _validate_public_scene_stage(scene, sprite)
        except OSError, ValueError, SpriteValidationError:
            raise SceneServiceError("PUBLIC_SCENE_UNAVAILABLE") from None

    def _draft_row(self, *, session_hash: str, draft_id: str) -> sqlite3.Row:
        if not _DRAFT_ID_RE.fullmatch(draft_id):
            raise SceneServiceError("NOT_FOUND")
        digest = hashlib.sha256(draft_id.encode("ascii")).hexdigest()
        now = _timestamp(datetime.now(UTC))
        with self._database().connection() as connection:
            cursor = connection.execute(
                "DELETE FROM scene_background_drafts WHERE expires_at <= ?", (now,)
            )
            row = connection.execute(
                """SELECT content_sha256, extension, expires_at FROM scene_background_drafts
                   WHERE draft_id_hash=? AND session_hash=? AND expires_at > ?""",
                (digest, session_hash, now),
            ).fetchone()
        if cursor.rowcount:
            self._collect_draft_files()
        if row is None:
            raise SceneServiceError("NOT_FOUND")
        return row

    def _read_draft_image(self, digest: str, extension: str) -> CanonicalSceneImage:
        if not _HASH_RE.fullmatch(digest) or extension not in {"png", "webp"}:
            raise SceneServiceError("NOT_FOUND")
        path = self.draft_root / f"{digest}.{extension}"
        try:
            if path.is_symlink() or not path.is_file() or path.stat().st_size > 2 * 1024 * 1024:
                raise OSError
            content = path.read_bytes()
            image = validate_scene_image(content, filename=f"draft.{extension}")
            if image.sha256 != digest or image.content != content:
                raise OSError
            return image
        except OSError, SceneImageError:
            raise SceneServiceError("NOT_FOUND") from None

    def _state_row(self) -> sqlite3.Row:
        try:
            with self._database().connection() as connection:
                row = connection.execute(
                    "SELECT * FROM scene_appearance_state WHERE singleton=1"
                ).fetchone()
        except sqlite3.Error as exc:
            raise SceneServiceError("PUBLIC_SCENE_UNAVAILABLE") from exc
        if row is None:
            raise SceneServiceError("PUBLIC_SCENE_UNAVAILABLE")
        return row

    def _recover_unlocked(self) -> None:
        state = self._state_row()
        raw_journal = state["journal_json"]
        if raw_journal is None:
            return
        try:
            journal = json.loads(str(raw_journal), object_pairs_hook=_json_unique)
            journal_keys = {
                "backup_id",
                "backup_sha256",
                "old_draft_present",
                "old_draft_revision",
                "new_draft_revision",
                "old_scene_sha256",
                "old_pointer_sha256",
                "new_scene_sha256",
                "new_background_sha256",
            }
            if not isinstance(journal, dict) or set(journal) != journal_keys:
                raise ValueError
            backup_id = journal["backup_id"]
            if not isinstance(backup_id, str) or re.fullmatch(r"[0-9a-f]{48}", backup_id) is None:
                raise ValueError
            if not isinstance(journal["backup_sha256"], str) or not _HASH_RE.fullmatch(
                journal["backup_sha256"]
            ):
                raise ValueError
            if type(journal["old_draft_present"]) is not bool:
                raise ValueError
            old_revision = journal["old_draft_revision"]
            new_revision = journal["new_draft_revision"]
            for draft_revision in (old_revision, new_revision):
                if draft_revision is not None and (
                    not isinstance(draft_revision, str) or not _HASH_RE.fullmatch(draft_revision)
                ):
                    raise ValueError
            if journal["old_draft_present"] != (old_revision is not None):
                raise ValueError
            for key in ("old_scene_sha256", "old_pointer_sha256", "new_scene_sha256"):
                if not isinstance(journal[key], str) or not _HASH_RE.fullmatch(journal[key]):
                    raise ValueError
            new_background_sha256 = journal["new_background_sha256"]
            if new_background_sha256 is not None and (
                not isinstance(new_background_sha256, str)
                or not _HASH_RE.fullmatch(new_background_sha256)
            ):
                raise ValueError
            if journal["old_scene_sha256"] != _sha(str(state["scene_json"] or "").encode("utf-8")):
                raise ValueError
            if journal["old_pointer_sha256"] != _state_pointer_digest(state):
                raise ValueError
            if self.portfolio is None and (
                journal["old_draft_present"] or old_revision is not None or new_revision is not None
            ):
                raise ValueError
            backup_path = self.recovery_root / f"{backup_id}.json"
            if (
                self.recovery_root.is_symlink()
                or backup_path.is_symlink()
                or not backup_path.is_file()
                or backup_path.stat().st_size > _JSON_MAX_BYTES
            ):
                raise ValueError
            backup = backup_path.read_bytes()
            if len(backup) > _JSON_MAX_BYTES or _sha(backup) != journal["backup_sha256"]:
                raise ValueError
            if journal["old_draft_present"]:
                old_draft = _decode_draft(backup)
                if old_draft.revision != old_revision:
                    raise ValueError
                old_raw = backup
            else:
                if backup:
                    raise ValueError
                old_raw = None
            if self.portfolio:
                current = self.portfolio._read_unlocked()
                current_revision = current.revision if current is not None else None
                if current_revision not in {old_revision, new_revision}:
                    raise ValueError
                self.portfolio.restore_raw_locked(old_raw)
            with self._database().connection() as connection:
                connection.execute("BEGIN IMMEDIATE")
                connection.execute(
                    "UPDATE scene_appearance_state SET journal_json=NULL WHERE singleton=1"
                )
                connection.execute("COMMIT")
            self._remove_backup(backup_id)
        except (
            OSError,
            KeyError,
            TypeError,
            ValueError,
            sqlite3.Error,
            LocalPortfolioError,
            RuntimeDatabaseError,
        ) as exc:
            raise SceneServiceError("SCENE_RECOVERY_FAILED") from exc

    def _new_publication_is_committed(
        self,
        *,
        bundle_id: str,
        snapshot: PublishedProfileSnapshot,
        revision: int,
        scene: PublicScene,
        settings: SceneConfig,
        background_sha256: str | None,
        background_extension: str | None,
        draft: LocalPortfolioDraft | None,
    ) -> bool:
        try:
            state = self._state_row()
            wrapper = json.loads(str(state["scene_json"]), object_pairs_hook=_json_unique)
            if (
                state["journal_json"] is not None
                or int(state["issued_revision"]) != revision
                or state["source_bundle_id"] != bundle_id
                or state["sprite_sha256"] != snapshot.sprite_sha256
                or int(state["character_revision"]) != snapshot.source_character_revision
                or int(state["appearance_revision"]) != revision
                or wrapper
                != {
                    "public": scene.model_dump(mode="json"),
                    "settings": settings.model_dump(mode="json"),
                }
                or state["background_sha256"] != background_sha256
                or state["background_extension"] != background_extension
            ):
                return False
            if self.portfolio is not None:
                current = self.portfolio._read_unlocked()
                if (current.revision if current is not None else None) != (
                    draft.revision if draft is not None else None
                ):
                    return False
            return True
        except KeyError, TypeError, ValueError, LocalPortfolioError, SceneServiceError:
            return False

    def _read_draft_raw_locked(self) -> bytes | None:
        if self.portfolio is None:
            return None
        return self.portfolio.read_raw_locked()

    def _portfolio_lock(self):
        if self.portfolio is not None:
            return self.portfolio.mutation_lock()
        from reponpc.admin.local_portfolio import portfolio_mutation_lock

        return portfolio_mutation_lock()

    def _database(self) -> RuntimeDatabase:
        if self.database is None:
            raise SceneServiceError("SERVICE_NOT_READY")
        return self.database

    def _write_recovery_backup(self, backup_id: str, old_raw: bytes | None) -> None:
        self._atomic_write(self.recovery_root / f"{backup_id}.json", old_raw or b"")

    def _remove_backup(self, backup_id: str) -> None:
        path = self.recovery_root / f"{backup_id}.json"
        with contextlib.suppress(OSError):
            path.unlink(missing_ok=True)

    def _atomic_content_addressed(
        self, root: Path, digest: str, extension: str, content: bytes
    ) -> Path:
        if not _HASH_RE.fullmatch(digest) or extension not in {"png", "webp"}:
            raise SceneServiceError("SCENE_ASSET_INVALID")
        path = root / f"{digest}.{extension}"
        if path.exists():
            if path.is_symlink() or not path.is_file() or _sha(path.read_bytes()) != digest:
                raise SceneServiceError("SCENE_ASSET_INVALID")
            return path
        self._atomic_write(path, content)
        return path

    def _atomic_write(self, path: Path, content: bytes) -> None:
        temporary: Path | None = None
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            if path.parent.is_symlink() or path.is_symlink():
                raise OSError
            with tempfile.NamedTemporaryFile(
                mode="wb", dir=path.parent, prefix=".scene-", suffix=".tmp", delete=False
            ) as stream:
                temporary = Path(stream.name)
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
            with contextlib.suppress(OSError, NotImplementedError):
                temporary.chmod(0o600)
            os.replace(temporary, path)
            temporary = None
            with contextlib.suppress(OSError, NotImplementedError):
                path.chmod(0o600)
        except OSError as exc:
            raise SceneServiceError("SCENE_ASSET_WRITE_FAILED") from exc
        finally:
            if temporary is not None:
                with contextlib.suppress(OSError):
                    temporary.unlink(missing_ok=True)

    def _collect_draft_files(self) -> None:
        try:
            with self._database().connection() as connection:
                active = {
                    (str(row["content_sha256"]), str(row["extension"]))
                    for row in connection.execute(
                        "SELECT content_sha256, extension FROM scene_background_drafts"
                    )
                }
            if self.draft_root.is_dir() and not self.draft_root.is_symlink():
                for path in self.draft_root.iterdir():
                    if path.is_file() and not path.is_symlink():
                        stem, extension = path.stem, path.suffix.removeprefix(".")
                        if (stem, extension) not in active:
                            path.unlink(missing_ok=True)
        except OSError, sqlite3.Error:
            return


def _scene_settings(
    proposal: dict[str, object], *, background_present: bool, registry: SceneRegistry
) -> SceneConfig:
    allowed = {
        "color_scheme",
        "color_mode",
        "visitor_mode_toggle",
        "visitor_scheme_choice",
        "accent",
        "focus",
        "dim",
        "scaling",
    }
    if set(proposal) - (allowed | {"background"}):
        raise SceneServiceError("SCENE_SETTINGS_INVALID")
    focus = proposal.get("focus", {"x": 50, "y": 50})
    if not isinstance(focus, dict):
        raise SceneServiceError("SCENE_SETTINGS_INVALID")
    raw = {
        "color_scheme": proposal.get("color_scheme", DEFAULT_SCHEME_ID),
        "color_mode": proposal.get("color_mode", "system"),
        "visitor_mode_toggle": proposal.get("visitor_mode_toggle", True),
        "visitor_scheme_choice": proposal.get("visitor_scheme_choice", True),
        "accent": proposal.get("accent"),
        "background_path": "assets/scene/preview.png" if background_present else None,
        "background_scaling": proposal.get("scaling", "smooth"),
        "background_focus": focus,
        "background_dim": proposal.get("dim", "auto"),
    }
    try:
        return SceneConfig.model_validate(raw, context={"scene_registry": registry})
    except ValidationError:
        raise SceneServiceError("SCENE_SETTINGS_INVALID") from None


def _settings_payload(settings: SceneConfig, scene: PublicScene | None) -> dict[str, object]:
    return {
        "color_scheme": settings.color_scheme,
        "color_mode": settings.color_mode,
        "visitor_mode_toggle": settings.visitor_mode_toggle,
        "visitor_scheme_choice": settings.visitor_scheme_choice,
        "accent": settings.accent,
        "background": (
            "current"
            if (
                scene.background_url is not None
                if scene is not None
                else settings.background_path is not None
            )
            else "none"
        ),
        "focus": settings.background_focus.model_dump(mode="json"),
        "dim": settings.background_dim,
        "scaling": settings.background_scaling,
    }


def _settings_match_public(
    settings: SceneConfig,
    scene: PublicScene,
    *,
    sprite_content: bytes,
    background_content: bytes | None,
    registry: SceneRegistry,
) -> bool:
    try:
        canonical_scheme = registry.canonical_id(settings.color_scheme)
        canonical_public_scheme = registry.canonical_id(scene.scheme.id)
    except KeyError:
        return False
    semantically_matches = (
        canonical_scheme == canonical_public_scheme
        and settings.color_mode == scene.color_mode
        and settings.visitor_mode_toggle == scene.visitor_mode_toggle
        and settings.visitor_scheme_choice == scene.visitor_scheme_choice
        and settings.background_scaling == scene.background_scaling
        and settings.background_focus.model_dump(mode="json")
        == scene.background_focus.model_dump(mode="json")
        and (settings.background_path is not None) == (scene.background_url is not None)
        and (settings.background_dim == "auto" or settings.background_dim == scene.background_dim)
    )
    if not semantically_matches:
        return False
    # Validate exact tokens only while both settings and published scene refer to
    # the same current scheme ID and version. Retired IDs keep their immutable
    # resolved colors when an alias points at a replacement scheme.
    try:
        current_scheme = registry.scheme(settings.color_scheme)
        if canonical_scheme != scene.scheme.id or current_scheme.version != scene.scheme.version:
            return True
        return (
            resolve_scene(
                settings,
                sprite_content=sprite_content,
                revision=scene.revision,
                registry=registry,
                background_content=background_content,
            ).public
            == scene
        )
    except KeyError, SceneResolutionError:
        return False


def _settings_from_public(scene: PublicScene | None) -> dict[str, object]:
    if scene is None:
        return _default_settings_payload()
    return {
        "color_scheme": scene.scheme.id,
        "color_mode": scene.color_mode,
        "visitor_mode_toggle": scene.visitor_mode_toggle,
        "visitor_scheme_choice": scene.visitor_scheme_choice,
        "accent": None,
        "background": "current" if scene.background_url is not None else "none",
        "focus": scene.background_focus.model_dump(mode="json"),
        "dim": scene.background_dim,
        "scaling": scene.background_scaling,
    }


def _default_settings_payload() -> dict[str, object]:
    return _settings_payload(SceneConfig(), None)


def _draft_character_revision(draft: LocalPortfolioDraft | None) -> int:
    if draft is None:
        return 0
    try:
        from reponpc.config.models import parse_public_config_bytes

        config = parse_public_config_bytes(draft.content.encode("utf-8"))
        return config.character.revision
    except ValueError:
        raise SceneServiceError("SCENE_DRAFT_INVALID") from None


def write_presentation_receipt(
    *, data_directory: Path, bundle_directory: Path, settings: SceneConfig
) -> Path:
    """Persist a bounded immutable scene receipt for a verified local build."""

    try:
        bundle_directory = Path(bundle_directory)
        manifest = parse_bundle_manifest((bundle_directory / "manifest.json").read_bytes())
        profile = parse_public_profile_bytes(
            (bundle_directory / "public/profile.json").read_bytes()
        )
        sprite_bytes = (bundle_directory / "public/character.png").read_bytes()
        sprite = validate_sprite(sprite_bytes)
        if sprite.content != sprite_bytes:
            raise ValueError
        scene = profile.character.scene
        scene_paths = [
            item.path for item in manifest.files if item.path.startswith("public/scene/")
        ]
        if scene is not None and scene.background_url is not None:
            if len(scene_paths) != 1:
                raise ValueError
            match = re.fullmatch(r"public/scene/([0-9a-f]{64})\.(png|webp)", scene_paths[0])
            if match is None:
                raise ValueError
            background_content = (bundle_directory / scene_paths[0]).read_bytes()
            background = validate_scene_image(
                background_content, filename=f"background.{match.group(2)}"
            )
            if (
                background.sha256 != match.group(1)
                or background.format != match.group(2)
                or background.content != background_content
            ):
                raise ValueError
        elif scene_paths:
            raise ValueError
        else:
            background_content = None
        if (
            scene is None
            or scene.revision != profile.character.revision
            or profile.index.version != manifest.bundle_id
            or settings.color_mode != scene.color_mode
            or settings.visitor_mode_toggle != scene.visitor_mode_toggle
            or not _settings_match_public(
                settings,
                scene,
                sprite_content=sprite_bytes,
                background_content=background_content,
                registry=default_scene_registry(),
            )
        ):
            raise ValueError
        _validate_public_scene_stage(scene, sprite.content)
        payload = _json_bytes(
            {
                "bundle_id": manifest.bundle_id,
                "sprite_sha256": sprite.sha256,
                "source_character_revision": profile.character.revision,
                "public": scene.model_dump(mode="json"),
                "settings": settings.model_dump(mode="json"),
            }
        )
        if len(payload) > 65_536:
            raise ValueError
        root = Path(data_directory) / "scene-appearance" / "receipts"
        path = root / f"{manifest.bundle_id}.{sprite.sha256}.json"
        root.mkdir(parents=True, exist_ok=True)
        if path.is_symlink():
            raise OSError
        if path.exists():
            if path.read_bytes() != payload:
                raise ValueError
            return path
        _write_private_immutable(path, payload)
        _trim_receipts(root, keep=64)
        return path
    except (
        OSError,
        KeyError,
        ManifestError,
        PublicProfileError,
        SpriteValidationError,
        SceneServiceError,
        ValueError,
    ) as exc:
        raise SceneServiceError("SCENE_RECEIPT_WRITE_FAILED") from exc


def _binding_matches(
    row: sqlite3.Row, *, bundle_id: str, sprite_sha256: str, character_revision: int
) -> bool:
    return (
        row["source_bundle_id"] == bundle_id
        and row["sprite_sha256"] == sprite_sha256
        and row["character_revision"] == character_revision
        and row["appearance_revision"] is not None
        and row["scene_json"] is not None
    )


def _notice_dict(notice: SceneNotice) -> dict[str, object]:
    return {
        "kind": notice.kind,
        "variant": notice.variant,
        "adjusted_value": notice.adjusted_value,
        "reason": notice.reason,
    }


def _image_notices(
    background: bytes | None, proposal: dict[str, object]
) -> list[dict[str, object]]:
    if background is None:
        return []
    extension = "webp" if background.startswith(b"RIFF") else "png"
    image = validate_scene_image(background, filename=f"background.{extension}")
    notices: list[dict[str, object]] = []
    if image.width < 960 or image.height < 540:
        notices.append(
            {"kind": "image_upscaled", "reason": "The image may be enlarged in the hero."}
        )
    focus = proposal.get("focus")
    if isinstance(focus, dict) and (
        abs(int(focus.get("x", 50)) - 50) > 25 or abs(int(focus.get("y", 50)) - 50) > 25
    ):
        notices.append(
            {"kind": "strong_crop", "reason": "The selected focus creates a strong crop."}
        )
    return notices


def _timestamp(value: datetime) -> str:
    return value.astimezone(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _json_bytes(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def _json_text(value: object) -> str:
    return _json_bytes(value).decode("utf-8")


def _sha(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _state_pointer_digest(state: sqlite3.Row) -> str:
    fields = (
        "issued_revision",
        "source_bundle_id",
        "sprite_sha256",
        "character_revision",
        "appearance_revision",
        "scene_json",
        "background_sha256",
        "background_extension",
    )
    return _sha(_json_bytes({field: state[field] for field in fields}))


def _json_unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def _validate_public_scene_stage(scene: PublicScene, sprite: bytes) -> None:
    canonical = validate_sprite(sprite)
    with Image.open(io.BytesIO(canonical.content)) as image:
        edge = _average_edge_color(image.convert("RGBA"))
    validate_npc_separation(scene, edge)


def _write_private_immutable(path: Path, content: bytes) -> None:
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb", dir=path.parent, prefix=".receipt-", suffix=".tmp", delete=False
        ) as stream:
            temporary = Path(stream.name)
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        with contextlib.suppress(OSError, NotImplementedError):
            temporary.chmod(0o600)
        os.replace(temporary, path)
        temporary = None
        with contextlib.suppress(OSError, NotImplementedError):
            path.chmod(0o600)
    finally:
        if temporary is not None:
            with contextlib.suppress(OSError):
                temporary.unlink(missing_ok=True)


def _trim_receipts(root: Path, *, keep: int) -> None:
    files = sorted(
        (path for path in root.iterdir() if path.is_file() and not path.is_symlink()),
        key=lambda path: path.stat().st_mtime_ns,
        reverse=True,
    )
    for path in files[keep:]:
        with contextlib.suppress(OSError):
            path.unlink()
