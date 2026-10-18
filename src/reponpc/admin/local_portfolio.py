"""Validated, atomic storage for the local public portfolio draft.

The local draft is deliberately a small persistence boundary.  Public YAML is
validated by the existing configuration model and an optional character sheet
is validated and canonicalised by the existing sprite validator before either
value reaches disk.
"""

from __future__ import annotations

import base64
import binascii
import contextlib
import hashlib
import json
import os
import re
import tempfile
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any, NoReturn

import yaml

from reponpc.cards.assets import HARD_MAX_BYTES, SpriteValidationError, validate_sprite
from reponpc.config.models import (
    MAX_CONFIG_BYTES,
    ConfigValidationError,
    PublicConfig,
    parse_public_config_bytes,
)

__all__ = [
    "LocalPortfolioDraft",
    "LocalPortfolioError",
    "LocalPortfolioStore",
    "apply_character",
]


_REVISION_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_SPRITE_BASE64_MAX_BYTES = 4 * ((HARD_MAX_BYTES + 2) // 3)
_SCENE_IMAGE_BASE64_MAX_BYTES = 4 * ((2 * 1024 * 1024 + 2) // 3)
_JSON_MAX_BYTES = (
    (MAX_CONFIG_BYTES * 2) + _SPRITE_BASE64_MAX_BYTES + _SCENE_IMAGE_BASE64_MAX_BYTES + 8192
)
_DRAFT_KEYS = frozenset({"content", "sprite_base64", "revision"})
_DRAFT_KEYS_WITH_SCENE = _DRAFT_KEYS | {"scene_background_base64"}
_PORTFOLIO_LOCK = threading.RLock()


class LocalPortfolioError(ValueError):
    """A safe, machine-readable error raised by the local portfolio store."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__("local portfolio operation failed")


@dataclass(frozen=True, slots=True)
class LocalPortfolioDraft:
    """The validated public draft returned by the local store."""

    content: str
    sprite_base64: str | None
    revision: str
    scene_background_base64: str | None = None

    def as_dict(self) -> dict[str, object]:
        """Return the exact public persistence/API shape."""

        return {
            "content": self.content,
            "sprite_base64": self.sprite_base64,
            "revision": self.revision,
        }

    def storage_dict(self) -> dict[str, object]:
        """Return the private on-disk shape, including an applied background."""

        return {**self.as_dict(), "scene_background_base64": self.scene_background_base64}


def _raise(code: str) -> NoReturn:
    raise LocalPortfolioError(code) from None


def _parse_public_content(content: str) -> tuple[PublicConfig, bytes]:
    if not isinstance(content, str):
        _raise("CONFIG_INVALID")

    try:
        raw = content.encode("utf-8")
    except UnicodeEncodeError:
        _raise("CONFIG_INVALID")

    if len(raw) > MAX_CONFIG_BYTES:
        _raise("PAYLOAD_TOO_LARGE")

    try:
        config = parse_public_config_bytes(raw, max_bytes=MAX_CONFIG_BYTES)
    except ConfigValidationError as exc:
        if any(issue.code == "file_too_large" for issue in exc.issues):
            _raise("PAYLOAD_TOO_LARGE")
        _raise("CONFIG_INVALID")

    return config, raw


def _canonicalize_sprite(sprite_base64: str) -> bytes:
    if not isinstance(sprite_base64, str) or not sprite_base64:
        _raise("ASSET_INVALID")
    if len(sprite_base64) > _SPRITE_BASE64_MAX_BYTES:
        _raise("PAYLOAD_TOO_LARGE")

    try:
        decoded = base64.b64decode(sprite_base64, validate=True)
    except binascii.Error, ValueError:
        _raise("ASSET_INVALID")

    # Requiring the exact standard representation rejects whitespace, URL-safe
    # alphabets, and alternate padding forms before image parsing.
    if base64.b64encode(decoded).decode("ascii") != sprite_base64:
        _raise("ASSET_INVALID")
    if len(decoded) > HARD_MAX_BYTES:
        _raise("PAYLOAD_TOO_LARGE")

    try:
        canonical = validate_sprite(decoded, max_bytes=HARD_MAX_BYTES)
    except SpriteValidationError as exc:
        if exc.code == "FILE_TOO_LARGE":
            _raise("PAYLOAD_TOO_LARGE")
        _raise("ASSET_INVALID")

    if len(canonical.content) > HARD_MAX_BYTES:
        _raise("PAYLOAD_TOO_LARGE")
    return canonical.content


def _validate_draft_values(
    content: str, sprite_base64: str | None
) -> tuple[PublicConfig, bytes | None]:
    config, _ = _parse_public_content(content)
    mode = config.character.mode

    if mode == "builtin":
        if sprite_base64 is not None:
            _raise("PORTFOLIO_INVALID")
        return config, None

    if sprite_base64 is None:
        _raise("PORTFOLIO_ASSET_REQUIRED")
    return config, _canonicalize_sprite(sprite_base64)


def _revision(content: str, sprite: bytes | None, scene_background: bytes | None = None) -> str:
    digest = hashlib.sha256()
    digest.update(content.encode("utf-8"))
    if sprite is not None:
        digest.update(sprite)
    if scene_background is not None:
        digest.update(scene_background)
    return digest.hexdigest()


def _draft_from_validated(
    content: str,
    sprite: bytes | None,
    scene_background: bytes | None = None,
) -> LocalPortfolioDraft:
    sprite_base64 = None
    if sprite is not None:
        sprite_base64 = base64.b64encode(sprite).decode("ascii")
    return LocalPortfolioDraft(
        content=content,
        sprite_base64=sprite_base64,
        revision=_revision(content, sprite, scene_background),
        scene_background_base64=(
            None if scene_background is None else base64.b64encode(scene_background).decode("ascii")
        ),
    )


def _strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def _decode_draft(raw: bytes) -> LocalPortfolioDraft:
    """Fully validate a private draft before any recovery write can replace it."""

    if not isinstance(raw, bytes) or not raw or len(raw) > _JSON_MAX_BYTES:
        _raise("PORTFOLIO_CORRUPT")

    try:
        payload = json.loads(raw.decode("utf-8"), object_pairs_hook=_strict_object)
        if not isinstance(payload, dict) or frozenset(payload) not in {
            _DRAFT_KEYS,
            _DRAFT_KEYS_WITH_SCENE,
        }:
            _raise("PORTFOLIO_CORRUPT")
        content = payload["content"]
        sprite_base64 = payload["sprite_base64"]
        revision = payload["revision"]
        scene_background_base64 = payload.get("scene_background_base64")
        if not isinstance(content, str):
            _raise("PORTFOLIO_CORRUPT")
        if sprite_base64 is not None and not isinstance(sprite_base64, str):
            _raise("PORTFOLIO_CORRUPT")
        if scene_background_base64 is not None and not isinstance(scene_background_base64, str):
            _raise("PORTFOLIO_CORRUPT")
        if not isinstance(revision, str) or not _REVISION_PATTERN.fullmatch(revision):
            _raise("PORTFOLIO_CORRUPT")
        try:
            _, sprite = _validate_draft_values(content, sprite_base64)
        except LocalPortfolioError:
            _raise("PORTFOLIO_CORRUPT")
        canonical_sprite = None if sprite is None else base64.b64encode(sprite).decode("ascii")
        if sprite_base64 != canonical_sprite:
            _raise("PORTFOLIO_CORRUPT")
        scene_background = None
        if scene_background_base64 is not None:
            if len(scene_background_base64) > _SCENE_IMAGE_BASE64_MAX_BYTES:
                _raise("PORTFOLIO_CORRUPT")
            decoded = base64.b64decode(scene_background_base64, validate=True)
            if base64.b64encode(decoded).decode("ascii") != scene_background_base64:
                _raise("PORTFOLIO_CORRUPT")
            from reponpc.scene.images import validate_scene_image

            suffix = "webp" if decoded.startswith(b"RIFF") else "png"
            scene_background = validate_scene_image(decoded, filename=f"applied.{suffix}").content
            if base64.b64encode(scene_background).decode("ascii") != scene_background_base64:
                _raise("PORTFOLIO_CORRUPT")
        if _revision(content, sprite, scene_background) != revision:
            _raise("PORTFOLIO_CORRUPT")
        return LocalPortfolioDraft(
            content=content,
            sprite_base64=sprite_base64,
            revision=revision,
            scene_background_base64=scene_background_base64,
        )
    except LocalPortfolioError:
        raise
    except OSError, UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError:
        _raise("PORTFOLIO_CORRUPT")


def _set_scene_background_path(content: str, image_bytes: bytes) -> str:
    from reponpc.scene.images import validate_scene_image

    suffix = "webp" if image_bytes.startswith(b"RIFF") else "png"
    image = validate_scene_image(image_bytes, filename=f"applied.{suffix}")
    config, _raw = _parse_public_content(content)
    values = config.model_dump(mode="json")
    character = dict(values["character"])
    scene = dict(character["scene"])
    scene["background_path"] = f"assets/scene/{image.sha256}.{image.format}"
    character["scene"] = scene
    values["character"] = character
    try:
        updated = yaml.safe_dump(
            values, allow_unicode=True, sort_keys=False, default_flow_style=False
        )
        parse_public_config_bytes(updated.encode("utf-8"))
    except TypeError, ValueError, yaml.YAMLError, ConfigValidationError:
        _raise("CONFIG_INVALID")
    return updated


def _best_effort_chmod(path: Path, mode: int) -> None:
    with contextlib.suppress(NotImplementedError, OSError):
        path.chmod(mode)


@contextlib.contextmanager
def portfolio_mutation_lock():
    """Acquire the one lock shared by all mutable local-portfolio state."""

    with _PORTFOLIO_LOCK:
        yield


class LocalPortfolioStore:
    """Read and atomically replace the validated local public draft."""

    def __init__(self, data_directory: Path) -> None:
        self._data_directory = Path(data_directory)
        self._draft_directory = self._data_directory / "local-portfolio"
        self._draft_path = self._draft_directory / "draft.json"

    def read(self) -> LocalPortfolioDraft | None:
        """Read and validate the current draft, if one exists."""

        with _PORTFOLIO_LOCK:
            return self._read_unlocked()

    @contextlib.contextmanager
    def mutation_lock(self):
        """Share the single process-wide lock with appearance mutations."""

        with portfolio_mutation_lock():
            yield

    def replace_scene_locked(
        self,
        settings: dict[str, object],
        background: bytes | None,
        appearance_revision: int,
    ) -> LocalPortfolioDraft | None:
        """Change only scene fields and its applied image; caller holds the lock."""

        draft = self.build_scene_draft_locked(settings, background, appearance_revision)
        if draft is not None:
            self._write_unlocked(draft)
        return draft

    def build_scene_draft_locked(
        self,
        settings: dict[str, object],
        background: bytes | None,
        appearance_revision: int,
    ) -> LocalPortfolioDraft | None:
        """Prepare an appearance-only draft without writing it."""

        current = self._read_unlocked()
        if current is None:
            return None
        from reponpc.config.models import SceneConfig

        if background is not None:
            from reponpc.scene.images import SceneImageError, validate_scene_image

            try:
                suffix = "webp" if background.startswith(b"RIFF") else "png"
                canonical = validate_scene_image(background, filename=f"applied.{suffix}")
            except SceneImageError:
                _raise("ASSET_INVALID")
            background = canonical.content
            background_path = f"assets/scene/{canonical.sha256}.{canonical.format}"
        else:
            background_path = None
        try:
            config = parse_public_config_bytes(current.content.encode("utf-8"))
            scene = SceneConfig.model_validate({**settings, "background_path": background_path})
            values = config.model_dump(mode="json")
            character = dict(values["character"])
            character["scene"] = scene.model_dump(mode="json")
            character["revision"] = appearance_revision
            values["character"] = character
            rewritten = yaml.safe_dump(
                values,
                allow_unicode=True,
                sort_keys=False,
                default_flow_style=False,
            )
            parse_public_config_bytes(rewritten.encode("utf-8"))
        except ConfigValidationError, TypeError, ValueError, yaml.YAMLError:
            _raise("CONFIG_INVALID")
        sprite = (
            _canonicalize_sprite(current.sprite_base64)
            if current.sprite_base64 is not None
            else None
        )
        draft = _draft_from_validated(rewritten, sprite, background)
        return draft

    def write_draft_locked(self, draft: LocalPortfolioDraft) -> None:
        """Atomically write a fully validated draft; caller holds the lock."""

        self._write_unlocked(draft)

    def restore_raw_locked(self, raw: bytes | None) -> None:
        """Restore a private recovery copy; caller holds ``mutation_lock``."""

        if raw is None:
            with contextlib.suppress(FileNotFoundError):
                self._draft_path.unlink()
            return
        if len(raw) > _JSON_MAX_BYTES:
            _raise("PORTFOLIO_CORRUPT")
        _decode_draft(raw)
        # Reuse the normal atomic writer after the full parse succeeds.
        self._write_raw_unlocked(raw)

    def read_raw_locked(self) -> bytes | None:
        """Return the private recovery bytes; caller holds ``mutation_lock``."""

        try:
            if self._draft_path.is_symlink():
                _raise("PORTFOLIO_CORRUPT")
            if not self._draft_path.exists():
                return None
            if not self._draft_path.is_file() or self._draft_path.stat().st_size > _JSON_MAX_BYTES:
                _raise("PORTFOLIO_CORRUPT")
            raw = self._draft_path.read_bytes()
            _decode_draft(raw)
            return raw
        except LocalPortfolioError:
            raise
        except OSError:
            _raise("PORTFOLIO_CORRUPT")

    def save(
        self,
        *,
        content: str,
        sprite_base64: str | None,
        expected_revision: str | None,
    ) -> LocalPortfolioDraft:
        """Validate and atomically save a draft using compare-and-swap."""

        if expected_revision is not None and not isinstance(expected_revision, str):
            _raise("PORTFOLIO_CONFLICT")

        # Validation occurs before acquiring the mutation lock.  The current
        # revision is still checked while locked immediately before replace.
        _, sprite = _validate_draft_values(content, sprite_base64)
        draft = _draft_from_validated(content, sprite)

        with _PORTFOLIO_LOCK:
            current = self._read_unlocked()
            current_revision = None if current is None else current.revision
            if expected_revision != current_revision:
                _raise("PORTFOLIO_CONFLICT")
            if current is not None and current.scene_background_base64 is not None:
                scene_background = base64.b64decode(current.scene_background_base64, validate=True)
                content = _set_scene_background_path(content, scene_background)
                draft = _draft_from_validated(
                    content,
                    _canonicalize_sprite(draft.sprite_base64)
                    if draft.sprite_base64 is not None
                    else None,
                    scene_background,
                )
            self._write_unlocked(draft)
        return draft

    def _read_unlocked(self) -> LocalPortfolioDraft | None:
        try:
            if self._draft_path.is_symlink():
                _raise("PORTFOLIO_CORRUPT")
            if not self._draft_path.exists():
                return None
            if not self._draft_path.is_file():
                _raise("PORTFOLIO_CORRUPT")
            if self._draft_path.stat().st_size > _JSON_MAX_BYTES:
                _raise("PORTFOLIO_CORRUPT")
            raw = self._draft_path.read_bytes()
            return _decode_draft(raw)
        except LocalPortfolioError:
            raise
        except OSError, UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError:
            _raise("PORTFOLIO_CORRUPT")

    def _write_unlocked(self, draft: LocalPortfolioDraft) -> None:
        temp_path: Path | None = None
        try:
            self._draft_directory.mkdir(parents=True, exist_ok=True)
            _best_effort_chmod(self._draft_directory, 0o700)
            encoded = json.dumps(
                draft.storage_dict(),
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
            if len(encoded) > _JSON_MAX_BYTES:
                _raise("PAYLOAD_TOO_LARGE")

            with tempfile.NamedTemporaryFile(
                mode="wb",
                dir=self._draft_directory,
                prefix=".draft-",
                suffix=".tmp",
                delete=False,
            ) as temporary:
                temp_path = Path(temporary.name)
                temporary.write(encoded)
                temporary.flush()
                os.fsync(temporary.fileno())
            _best_effort_chmod(temp_path, 0o600)
            os.replace(temp_path, self._draft_path)
            temp_path = None
            _best_effort_chmod(self._draft_path, 0o600)
        except LocalPortfolioError:
            raise
        except OSError, TypeError, ValueError:
            _raise("PORTFOLIO_WRITE_FAILED")
        finally:
            if temp_path is not None:
                with contextlib.suppress(OSError):
                    temp_path.unlink(missing_ok=True)

    def _write_raw_unlocked(self, raw: bytes) -> None:
        temp_path: Path | None = None
        try:
            self._draft_directory.mkdir(parents=True, exist_ok=True)
            _best_effort_chmod(self._draft_directory, 0o700)
            with tempfile.NamedTemporaryFile(
                mode="wb", dir=self._draft_directory, prefix=".draft-", suffix=".tmp", delete=False
            ) as temporary:
                temp_path = Path(temporary.name)
                temporary.write(raw)
                temporary.flush()
                os.fsync(temporary.fileno())
            _best_effort_chmod(temp_path, 0o600)
            os.replace(temp_path, self._draft_path)
            temp_path = None
        except OSError:
            _raise("PORTFOLIO_WRITE_FAILED")
        finally:
            if temp_path is not None:
                with contextlib.suppress(OSError):
                    temp_path.unlink(missing_ok=True)


def apply_character(content: str, png_base64: str) -> LocalPortfolioDraft:
    """Return a canonical custom-character draft without writing to disk."""

    config, _ = _parse_public_content(content)
    sprite = _canonicalize_sprite(png_base64)
    values = config.model_dump(mode="json")
    character = dict(values["character"])
    character["mode"] = "custom"
    character.pop("builtin", None)
    character["custom"] = {"sprite_path": "assets/character/portfolio.png"}
    character["revision"] = int(character["revision"]) + 1
    values["character"] = character

    try:
        rewritten = yaml.safe_dump(
            values,
            allow_unicode=True,
            sort_keys=False,
            default_flow_style=False,
        )
    except TypeError, ValueError, yaml.YAMLError:
        _raise("CONFIG_INVALID")

    rewritten_config, _ = _parse_public_content(rewritten)
    if rewritten_config.character.mode != "custom":
        _raise("CONFIG_INVALID")
    return _draft_from_validated(rewritten, sprite)
