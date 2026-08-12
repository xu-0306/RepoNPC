"""Side-effect ordered administration operations over validated public inputs."""

from __future__ import annotations

import base64
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, cast

from reponpc.admin.github import GitCommit, GitFile, GitHubAdminClient
from reponpc.cards.assets import CanonicalSprite, validate_sprite, validate_sprite_filename
from reponpc.cards.render import (
    CardCopy,
    CardPalette,
    Extension,
    Locale,
    Theme,
    render_card_assets,
    render_readme_snippet,
)
from reponpc.cards.sprite_composer import compose_builtin
from reponpc.config.models import ConfigValidationError, PublicConfig, parse_public_config_bytes
from reponpc.runtime.database import RuntimeDatabase, RuntimeDatabaseError


@dataclass(frozen=True, slots=True)
class AdminOperations:
    github: GitHubAdminClient
    database: RuntimeDatabase
    public_base_url: str

    def read_config(self) -> GitFile:
        return self.github.read_config()

    def validate_config(self, content: bytes) -> PublicConfig:
        return parse_public_config_bytes(content)

    def preview_config(self, content: bytes) -> dict[str, Any]:
        config = self.validate_config(content)
        sprite = self._sprite(config)
        encoded_sprite = base64.b64encode(sprite.content).decode("ascii")
        cards: dict[str, dict[str, str]] = {}
        for locale in config.locales.supported:
            for theme in ("light", "dark"):
                selected = getattr(config.card.themes, theme)
                assets = render_card_assets(
                    copy=CardCopy(
                        display_name=config.profile.display_name,
                        headline=config.profile.headline[locale],
                        call_to_action=config.card.call_to_action[locale],
                        repository_count=(
                            sum(item.enabled for item in config.repositories)
                            if config.card.show_repository_count
                            else None
                        ),
                    ),
                    palette=CardPalette(**selected.model_dump()),
                    sprite=sprite,
                    animation_enabled=config.card.animation.enabled,
                    frame_duration_ms=config.card.animation.frame_duration_ms,
                )
                cards[f"{theme}-{locale}"] = {
                    "svg_base64": base64.b64encode(assets.svg).decode("ascii"),
                    "gif_base64": base64.b64encode(assets.gif).decode("ascii"),
                    "png_base64": base64.b64encode(assets.png).decode("ascii"),
                }
        return {
            "profile": {
                locale: {
                    "display_name": config.profile.display_name,
                    "headline": config.profile.headline[locale],
                    "bio": config.profile.bio[locale],
                    "greeting": config.profile.greeting[locale],
                }
                for locale in config.locales.supported
            },
            "character": {
                "mode": config.character.mode,
                "revision": config.character.revision,
                "png_base64": encoded_sprite,
                "sha256": sprite.sha256,
            },
            "cards": cards,
        }

    def write_config(
        self,
        *,
        content: bytes,
        expected_blob_sha: str,
        commit_message: str,
        request_id: str,
        session_hash: str,
    ) -> GitCommit:
        self.validate_config(content)
        return self._write_and_audit(
            path="reponpc.yml",
            content=content,
            expected_blob_sha=expected_blob_sha,
            commit_message=commit_message,
            request_id=request_id,
            session_hash=session_hash,
            action="config.write",
        )

    def validate_asset(self, *, filename: str, content: bytes) -> CanonicalSprite:
        validate_sprite_filename(filename)
        return validate_sprite(content)

    def write_asset(
        self,
        *,
        filename: str,
        content: bytes,
        expected_blob_sha: str | None,
        commit_message: str,
        request_id: str,
        session_hash: str,
    ) -> tuple[GitCommit, CanonicalSprite]:
        canonical = self.validate_asset(filename=filename, content=content)
        commit = self._write_and_audit(
            path=f"assets/character/{filename}",
            content=canonical.content,
            expected_blob_sha=expected_blob_sha,
            commit_message=commit_message,
            request_id=request_id,
            session_hash=session_hash,
            action="asset.write",
        )
        return commit, canonical

    def readme_snippet(self, *, locale: str, theme: str, extension: str, revision: int) -> str:
        return render_readme_snippet(
            public_base_url=self.public_base_url,
            locale=cast(Locale, locale),
            theme=cast(Theme, theme),
            extension=cast(Extension, extension),
            revision=revision,
        )

    def dispatch(self, *, request_id: str, session_hash: str) -> None:
        try:
            self.github.dispatch_index()
        except Exception:
            self._audit(
                action="index.dispatch",
                target_path=None,
                result_commit_sha=None,
                request_id=request_id,
                outcome="failed",
                session_hash=session_hash,
            )
            raise
        self._audit(
            action="index.dispatch",
            target_path=None,
            result_commit_sha=None,
            request_id=request_id,
            outcome="succeeded",
            session_hash=session_hash,
        )

    def index_status(self) -> dict[str, str | None]:
        state = self.database.bundle_state()
        return {
            "active_bundle_id": state.active_bundle_id,
            "previous_bundle_id": state.previous_bundle_id,
            "pinned_bundle_id": state.pinned_bundle_id,
            "last_checked_at": state.last_checked_at,
            "update_error": state.safe_update_error,
        }

    def _sprite(self, config: PublicConfig) -> CanonicalSprite:
        if config.character.builtin is not None:
            return validate_sprite(compose_builtin(config.character.builtin))
        custom = config.character.custom
        if custom is None:
            raise ConfigValidationError([])
        return validate_sprite(self.github.read(custom.sprite_path).content)

    def _write_and_audit(
        self,
        *,
        path: str,
        content: bytes,
        expected_blob_sha: str | None,
        commit_message: str,
        request_id: str,
        session_hash: str,
        action: str,
    ) -> GitCommit:
        try:
            commit = self.github.write(
                path=path,
                content=content,
                expected_blob_sha=expected_blob_sha,
                commit_message=commit_message,
            )
        except Exception:
            self._audit(
                action=action,
                target_path=path,
                result_commit_sha=None,
                request_id=request_id,
                outcome="failed",
                session_hash=session_hash,
            )
            raise
        self._audit(
            action=action,
            target_path=path,
            result_commit_sha=commit.commit_sha,
            request_id=request_id,
            outcome="succeeded",
            session_hash=session_hash,
        )
        return commit

    def _audit(
        self,
        *,
        action: str,
        target_path: str | None,
        result_commit_sha: str | None,
        request_id: str,
        outcome: str,
        session_hash: str,
    ) -> None:
        try:
            with self.database.connection() as connection:
                connection.execute(
                    """
                    INSERT INTO admin_audit(
                        occurred_at, action, target_path, result_commit_sha,
                        request_id, outcome, session_hash
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        datetime.now(UTC).isoformat().replace("+00:00", "Z"),
                        action,
                        target_path,
                        result_commit_sha,
                        request_id,
                        outcome,
                        session_hash,
                    ),
                )
        except sqlite3.Error as exc:
            raise RuntimeDatabaseError("runtime_admin_audit_failed") from exc
