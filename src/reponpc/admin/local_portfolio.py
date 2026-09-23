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
_JSON_MAX_BYTES = (MAX_CONFIG_BYTES * 2) + ((HARD_MAX_BYTES + 2) // 3) * 4 + 8192
_SPRITE_BASE64_MAX_BYTES = 4 * ((HARD_MAX_BYTES + 2) // 3)
_DRAFT_KEYS = frozenset({"content", "sprite_base64", "revision"})
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

    def as_dict(self) -> dict[str, object]:
        """Return the exact public persistence/API shape."""

        return {
            "content": self.content,
            "sprite_base64": self.sprite_base64,
            "revision": self.revision,
        }


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
    except (binascii.Error, ValueError):
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


def _revision(content: str, sprite: bytes | None) -> str:
    digest = hashlib.sha256()
    digest.update(content.encode("utf-8"))
    if sprite is not None:
        digest.update(sprite)
    return digest.hexdigest()


def _draft_from_validated(content: str, sprite: bytes | None) -> LocalPortfolioDraft:
    sprite_base64 = None
    if sprite is not None:
        sprite_base64 = base64.b64encode(sprite).decode("ascii")
    return LocalPortfolioDraft(
        content=content,
        sprite_base64=sprite_base64,
        revision=_revision(content, sprite),
    )


def _strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def _best_effort_chmod(path: Path, mode: int) -> None:
    with contextlib.suppress(NotImplementedError, OSError):
        path.chmod(mode)


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
            if len(raw) > _JSON_MAX_BYTES:
                _raise("PORTFOLIO_CORRUPT")
            payload = json.loads(
                raw.decode("utf-8"),
                object_pairs_hook=_strict_object,
            )
            if not isinstance(payload, dict) or set(payload) != _DRAFT_KEYS:
                _raise("PORTFOLIO_CORRUPT")

            content = payload["content"]
            sprite_base64 = payload["sprite_base64"]
            revision = payload["revision"]
            if not isinstance(content, str):
                _raise("PORTFOLIO_CORRUPT")
            if sprite_base64 is not None and not isinstance(sprite_base64, str):
                _raise("PORTFOLIO_CORRUPT")
            if not isinstance(revision, str) or not _REVISION_PATTERN.fullmatch(revision):
                _raise("PORTFOLIO_CORRUPT")

            try:
                _, sprite = _validate_draft_values(content, sprite_base64)
            except LocalPortfolioError:
                _raise("PORTFOLIO_CORRUPT")

            canonical_sprite_base64 = (
                None if sprite is None else base64.b64encode(sprite).decode("ascii")
            )
            if sprite_base64 != canonical_sprite_base64:
                _raise("PORTFOLIO_CORRUPT")
            if _revision(content, sprite) != revision:
                _raise("PORTFOLIO_CORRUPT")
            return LocalPortfolioDraft(
                content=content,
                sprite_base64=sprite_base64,
                revision=revision,
            )
        except LocalPortfolioError:
            raise
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError):
            _raise("PORTFOLIO_CORRUPT")

    def _write_unlocked(self, draft: LocalPortfolioDraft) -> None:
        temp_path: Path | None = None
        try:
            self._draft_directory.mkdir(parents=True, exist_ok=True)
            _best_effort_chmod(self._draft_directory, 0o700)
            encoded = json.dumps(
                draft.as_dict(),
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
        except (OSError, TypeError, ValueError):
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
    except (TypeError, ValueError, yaml.YAMLError):
        _raise("CONFIG_INVALID")

    rewritten_config, _ = _parse_public_content(rewritten)
    if rewritten_config.character.mode != "custom":
        _raise("CONFIG_INVALID")
    return _draft_from_validated(rewritten, sprite)
