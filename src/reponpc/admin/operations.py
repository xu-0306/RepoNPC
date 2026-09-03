"""Side-effect ordered administration operations over validated public inputs."""

from __future__ import annotations

import base64
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, cast

from reponpc.admin.batch_resolver import BatchPreflightPlan, RepositorySelection
from reponpc.admin.batch_runtime import BatchRuntimeError, BatchSnapshot
from reponpc.admin.batches import AnalysisBatchService, BatchPreflightInput
from reponpc.admin.embedding_profiles import (
    EmbeddingProfile,
    EmbeddingProfileError,
    EmbeddingProfileInput,
    EmbeddingProfileRegistry,
)
from reponpc.admin.embedding_reindex import EmbeddingReindexCoordinator
from reponpc.admin.github import GitCommit, GitFile, GitHubAdminClient, GitHubAdminError
from reponpc.admin.model_operations import (
    OllamaModelOperation,
    OllamaModelOperationCoordinator,
)
from reponpc.admin.onboarding import (
    GuidedOnboardingError,
    GuidedOnboardingService,
    GuidedProfileDraft,
    GuidedRepositoryDraft,
)
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
    github: GitHubAdminClient | None
    database: RuntimeDatabase
    public_base_url: str
    onboarding: GuidedOnboardingService | None = None
    analysis_batches: AnalysisBatchService | None = None
    embedding_profiles: EmbeddingProfileRegistry | None = None
    embedding_reindex: EmbeddingReindexCoordinator | None = None
    ollama_model_operations: OllamaModelOperationCoordinator | None = None

    def read_config(self) -> GitFile:
        return self._github().read_config()

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
            self._github().dispatch_index()
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

    def list_embedding_profiles(self) -> tuple[EmbeddingProfile, ...]:
        return self._embedding_profiles().list()

    def get_embedding_profile(self, profile_id: str) -> EmbeddingProfile:
        return self._embedding_profiles().get(profile_id)

    def create_embedding_profile(self, values: EmbeddingProfileInput) -> EmbeddingProfile:
        return self._embedding_profiles().create(values)

    def update_embedding_profile(
        self, profile_id: str, values: EmbeddingProfileInput
    ) -> EmbeddingProfile:
        return self._embedding_profiles().update(profile_id, values)

    def delete_embedding_profile(self, profile_id: str) -> None:
        self._embedding_profiles().delete(profile_id)

    def probe_embedding_profile(self, profile_id: str) -> EmbeddingProfile:
        return self._embedding_profiles().probe(profile_id)

    def activate_embedding_profile(self, profile_id: str) -> EmbeddingProfile:
        if self.embedding_reindex is not None:
            return self.embedding_reindex.queue(profile_id)
        return self._embedding_profiles().activate(profile_id)

    def installed_ollama_embedding_models(self) -> tuple[str, ...]:
        return self._embedding_profiles().installed_ollama_models()

    def ollama_embedding_model_action(
        self, profile_id: str, *, action: str, confirmed: bool
    ) -> EmbeddingProfile:
        return self._embedding_profiles().ollama_model_action(
            profile_id, action=action, confirmed=confirmed
        )

    def start_ollama_embedding_model_pull(
        self, profile_id: str, *, confirmed: bool
    ) -> OllamaModelOperation | None:
        if self.ollama_model_operations is None:
            self.ollama_embedding_model_action(profile_id, action="pull", confirmed=confirmed)
            return None
        return self.ollama_model_operations.queue_pull(profile_id, confirmed=confirmed)

    def get_ollama_embedding_model_operation(self, operation_id: str) -> OllamaModelOperation:
        if self.ollama_model_operations is None:
            raise EmbeddingProfileError("NOT_FOUND")
        return self.ollama_model_operations.get(operation_id)

    def cancel_ollama_embedding_model_operation(self, operation_id: str) -> OllamaModelOperation:
        if self.ollama_model_operations is None:
            raise EmbeddingProfileError("NOT_FOUND")
        return self.ollama_model_operations.cancel(operation_id)

    def discover_repositories(self, *, account: str, page: int) -> dict[str, object]:
        return self._onboarding().discover_repositories(account=account, page=page)

    def resolve_repository(self, *, repository: str, ref: str | None) -> dict[str, object]:
        return self._onboarding().resolve_repository(repository=repository, ref=ref)

    def analyze_repository(
        self,
        *,
        session_hash: str,
        slug: str,
        ref: str | None,
        include: tuple[str, ...],
        exclude: tuple[str, ...],
        cancel_requested: Any,
    ) -> dict[str, object]:
        if self.analysis_batches is not None:
            try:
                selection = RepositorySelection(
                    slug=slug,
                    ref=ref,
                    include=include,
                    exclude=exclude,
                    confirmed=True,
                )
            except ValueError as exc:
                raise BatchRuntimeError("VALIDATION_ERROR") from exc
            cancelled = getattr(cancel_requested, "is_set", None)
            if not callable(cancelled):
                raise BatchRuntimeError("VALIDATION_ERROR")
            return self.analysis_batches.analyze_one_compatibility(
                selection=selection,
                cancelled=cancelled,
            )
        return self._onboarding().analyze_repository(
            session_hash=session_hash,
            slug=slug,
            ref=ref,
            include=include,
            exclude=exclude,
            cancel_requested=cancel_requested,
        )

    def preflight_analysis_batch(
        self, *, selections: tuple[RepositorySelection, ...]
    ) -> BatchPreflightPlan:
        return self._analysis_batches().preflight(BatchPreflightInput(selections=selections))

    def create_analysis_batch(
        self,
        *,
        plan_id: str,
        selections: tuple[RepositorySelection, ...],
        idempotency_key: str,
    ) -> tuple[BatchSnapshot, bool]:
        return self._analysis_batches().create(
            plan_id=plan_id,
            selections=selections,
            idempotency_key=idempotency_key,
        )

    def active_analysis_batch(self) -> BatchSnapshot:
        return self._analysis_batches().active()

    def analysis_batch(self, *, batch_id: str) -> BatchSnapshot:
        return self._analysis_batches().get(batch_id)

    def analysis_batch_events(self, *, batch_id: str, after_event_id: int | None):
        return self._analysis_batches().events(batch_id, after_event_id=after_event_id)

    def analysis_batch_action(self, *, batch_id: str, action: str) -> BatchSnapshot:
        return self._analysis_batches().action(batch_id, action=action)

    def suggest_contributions(
        self,
        *,
        session_hash: str,
        slug: str,
        owner_statement: str,
    ) -> dict[str, object]:
        return self._onboarding().suggest_contributions(
            session_hash=session_hash,
            slug=slug,
            owner_statement=owner_statement,
        )

    def create_onboarding_draft(
        self,
        *,
        profile: GuidedProfileDraft,
        repositories: tuple[GuidedRepositoryDraft, ...],
        base_config: PublicConfig | None,
        confirmed_assertions: bool,
    ) -> dict[str, object]:
        return self._onboarding().create_draft(
            profile=profile,
            repositories=repositories,
            base_config=base_config,
            confirmed_assertions=confirmed_assertions,
        )

    def _sprite(self, config: PublicConfig) -> CanonicalSprite:
        if config.character.builtin is not None:
            return validate_sprite(compose_builtin(config.character.builtin))
        custom = config.character.custom
        if custom is None:
            raise ConfigValidationError([])
        return validate_sprite(self._github().read(custom.sprite_path).content)

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
            commit = self._github().write(
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

    def _github(self) -> GitHubAdminClient:
        if self.github is None:
            raise GitHubAdminError("SERVICE_NOT_READY")
        return self.github

    def _onboarding(self) -> GuidedOnboardingService:
        if self.onboarding is None:
            raise GuidedOnboardingError("SERVICE_NOT_READY")
        return self.onboarding

    def _analysis_batches(self) -> AnalysisBatchService:
        if self.analysis_batches is None:
            raise BatchRuntimeError("SERVICE_NOT_READY")
        return self.analysis_batches

    def _embedding_profiles(self) -> EmbeddingProfileRegistry:
        if self.embedding_profiles is None:
            raise EmbeddingProfileError("SERVICE_NOT_READY")
        return self.embedding_profiles

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
