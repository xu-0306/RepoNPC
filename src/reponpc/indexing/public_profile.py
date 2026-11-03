"""Canonical localized public profile production and validation."""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from typing import Annotated, Literal
from urllib.parse import urlsplit

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    ValidationInfo,
    field_validator,
    model_validator,
)

from reponpc.config.models import Locale, PublicConfig
from reponpc.i18n.languages import get_language
from reponpc.i18n.plan import ANALYSIS_LOCALES, require_enabled
from reponpc.indexing.sources import ResolvedRepository
from reponpc.scene.resolve import PublicScene, resolve_scene

MAX_PUBLIC_PROFILE_BYTES = 1024 * 1024
_INDEX_VERSION_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._+-]{0,127}$")


class PublicProfileError(ValueError):
    """Safe profile failure without rejected content or internal paths."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__("public profile is invalid")


class _StrictProfileModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class PublicLink(_StrictProfileModel):
    label: Annotated[str, Field(min_length=1, max_length=200)]
    url: Annotated[str, Field(min_length=1, max_length=2048)]

    @field_validator("url")
    @classmethod
    def validate_url(cls, value: str) -> str:
        _validate_public_url(value)
        return value


class PublicProfile(_StrictProfileModel):
    display_name: Annotated[str, Field(min_length=1, max_length=80)]
    headline: Annotated[str, Field(min_length=1, max_length=10_000)]
    bio: Annotated[str, Field(min_length=1, max_length=100_000)]
    greeting: Annotated[str, Field(min_length=1, max_length=10_000)]
    location: Annotated[str | None, Field(max_length=120)] = None
    avatar_url: Annotated[str | None, Field(max_length=2048)] = None
    links: Annotated[list[PublicLink], Field(max_length=100)]

    @field_validator("avatar_url")
    @classmethod
    def validate_avatar_url(cls, value: str | None) -> str | None:
        if value is not None:
            _validate_public_url(value)
        return value


class PublicRepository(_StrictProfileModel):
    slug: Annotated[str, Field(min_length=3, max_length=200)]
    summary: Annotated[str, Field(min_length=1, max_length=100_000)]
    role: Annotated[str, Field(min_length=1, max_length=10_000)]
    tags: Annotated[list[Annotated[str, Field(min_length=1, max_length=64)]], Field(max_length=100)]
    demo_url: Annotated[str | None, Field(max_length=2048)] = None
    language: Annotated[str | None, Field(max_length=100)] = None
    stars: Annotated[int | None, Field(ge=0, le=2_147_483_647)] = None
    forks: Annotated[int | None, Field(ge=0, le=2_147_483_647)] = None

    @field_validator("language")
    @classmethod
    def validate_language(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("repository language must be non-empty")
        return value

    @field_validator("slug")
    @classmethod
    def validate_slug(cls, value: str) -> str:
        parts = value.split("/")
        if len(parts) != 2 or any(not part or part in {".", ".."} for part in parts):
            raise ValueError("invalid repository slug")
        return value

    @field_validator("demo_url")
    @classmethod
    def validate_demo_url(cls, value: str | None) -> str | None:
        if value is not None:
            _validate_public_url(value)
        return value


class LocalizedPublicProfile(_StrictProfileModel):
    profile: PublicProfile
    repositories: Annotated[list[PublicRepository], Field(max_length=10_000)]
    suggested_questions: Annotated[
        list[Annotated[str, Field(min_length=1, max_length=2_000)]],
        Field(min_length=1, max_length=100),
    ]


class CharacterMetadata(_StrictProfileModel):
    mode: Literal["builtin", "custom"]
    asset_url: Literal["/api/public/character.png"]
    revision: Annotated[int, Field(ge=0)]
    frame_duration_ms: Annotated[int, Field(ge=80, le=1000)]
    movement: Literal["none", "subtle"]
    scene: PublicScene | None = None

    @model_validator(mode="after")
    def validate_scene_revision(self) -> CharacterMetadata:
        if self.scene is not None and self.scene.revision != self.revision:
            raise ValueError("scene revision must match character revision")
        return self


class IndexMetadata(_StrictProfileModel):
    version: Annotated[str, Field(min_length=1, max_length=128)]
    built_at: Annotated[str, Field(min_length=1, max_length=64)]
    repository_count: Annotated[int, Field(ge=0, le=10_000)]

    @field_validator("version")
    @classmethod
    def validate_version(cls, value: str) -> str:
        if not _INDEX_VERSION_RE.fullmatch(value):
            raise ValueError("invalid index version")
        return value

    @field_validator("built_at")
    @classmethod
    def validate_built_at(cls, value: str) -> str:
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError("invalid build timestamp") from exc
        if parsed.tzinfo is None:
            raise ValueError("build timestamp must have a timezone")
        return value


class BilingualPublicProfile(_StrictProfileModel):
    schema_version: Literal[1, 2]
    locales: Annotated[dict[Locale, LocalizedPublicProfile], Field(min_length=1)]
    character: CharacterMetadata
    index: IndexMetadata

    @field_validator("locales")
    @classmethod
    def preserve_legacy_order(
        cls, value: dict[Locale, LocalizedPublicProfile], info: ValidationInfo
    ) -> dict[Locale, LocalizedPublicProfile]:
        if info.data.get("schema_version") == 1 and set(value) == set(ANALYSIS_LOCALES):
            return {tag: value[tag] for tag in ANALYSIS_LOCALES}
        return value

    @model_validator(mode="after")
    def validate_bilingual_equivalence(self) -> BilingualPublicProfile:
        # Schema 1 is the frozen legacy pair, also used by the durable analysis contract.
        if self.schema_version == 1 and set(self.locales) != set(ANALYSIS_LOCALES):
            raise ValueError("required legacy locales are missing or unknown")
        first = next(iter(self.locales.values()))
        for localized in self.locales.values():
            if len(localized.repositories) != self.index.repository_count:
                raise ValueError("repository count mismatch")
            if (
                localized.profile.display_name,
                localized.profile.location,
                localized.profile.avatar_url,
                [link.url for link in localized.profile.links],
            ) != (
                first.profile.display_name,
                first.profile.location,
                first.profile.avatar_url,
                [link.url for link in first.profile.links],
            ):
                raise ValueError("non-localized profile fields differ")
            if [
                (item.slug, item.tags, item.demo_url, item.language, item.stars, item.forks)
                for item in localized.repositories
            ] != [
                (item.slug, item.tags, item.demo_url, item.language, item.stars, item.forks)
                for item in first.repositories
            ]:
                raise ValueError("non-localized repository fields differ")
        return self


def build_public_profile_bytes(
    *,
    config: PublicConfig,
    index_version: str,
    built_at: datetime,
    repository_count: int,
    sprite_content: bytes | None = None,
    background_content: bytes | None = None,
    repository_snapshots: tuple[ResolvedRepository, ...] = (),
) -> bytes:
    """Build profile bytes, resolving scene only from an explicit canonical sheet."""

    repositories = tuple(repository for repository in config.repositories if repository.enabled)
    if repository_count != len(repositories):
        raise PublicProfileError("public_profile_metadata_invalid")
    if (config.character.scene.background_path is None) != (background_content is None):
        raise PublicProfileError("public_profile_generation_failed")
    if config.character.scene.background_path is not None and sprite_content is None:
        raise PublicProfileError("public_profile_generation_failed")
    snapshots = {snapshot.slug: snapshot for snapshot in repository_snapshots}
    try:
        locales = {
            locale: LocalizedPublicProfile(
                profile=PublicProfile(
                    display_name=config.profile.display_name,
                    headline=config.profile.headline[locale],
                    bio=config.profile.bio[locale],
                    greeting=config.profile.greeting[locale],
                    location=config.profile.location,
                    avatar_url=config.profile.avatar_url,
                    links=[
                        PublicLink(label=link.label[locale], url=link.url)
                        for link in config.profile.links
                    ],
                ),
                repositories=[
                    PublicRepository(
                        slug=repository.slug,
                        summary=repository.summary[locale],
                        role=repository.role[locale],
                        tags=list(repository.tags),
                        demo_url=repository.demo_url,
                        language=(
                            snapshot.language
                            if (snapshot := snapshots.get(repository.slug))
                            else None
                        ),
                        stars=snapshot.stars if snapshot else None,
                        forks=snapshot.forks if snapshot else None,
                    )
                    for repository in repositories
                ],
                suggested_questions=list(config.profile.suggested_questions[locale]),
            )
            for locale in config.locales.supported
        }
        document = BilingualPublicProfile(
            schema_version=2,
            locales=locales,
            character=CharacterMetadata(
                mode=config.character.mode,
                asset_url="/api/public/character.png",
                revision=config.character.revision,
                frame_duration_ms=config.character.animation.frame_duration_ms,
                movement=config.character.animation.movement,
                scene=(
                    resolve_scene(
                        config.character.scene,
                        sprite_content=sprite_content,
                        revision=config.character.revision,
                        background_content=background_content,
                    ).public
                    if sprite_content is not None
                    else None
                ),
            ),
            index=IndexMetadata(
                version=index_version,
                built_at=_canonical_timestamp(built_at),
                repository_count=repository_count,
            ),
        )
    except (KeyError, ValidationError, ValueError) as exc:
        raise PublicProfileError("public_profile_generation_failed") from exc
    serialized = document.model_dump(mode="json")
    if document.character.scene is None:
        serialized["character"].pop("scene", None)
    return json.dumps(serialized, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def parse_public_profile_bytes(payload: bytes) -> BilingualPublicProfile:
    """Parse untrusted bundle bytes without exposing rejected content."""

    if not isinstance(payload, bytes) or not payload or len(payload) > MAX_PUBLIC_PROFILE_BYTES:
        raise PublicProfileError("public_profile_invalid")
    try:
        return BilingualPublicProfile.model_validate_json(payload)
    except (ValidationError, ValueError) as exc:
        raise PublicProfileError("public_profile_invalid") from exc


def validate_public_profile_metadata(
    document: BilingualPublicProfile,
    *,
    index_version: str,
    built_at: str | None = None,
    repository_count: int | None = None,
) -> None:
    """Bind a parsed profile to its immutable manifest or active version."""

    if document.index.version != index_version:
        raise PublicProfileError("public_profile_metadata_invalid")
    if built_at is not None and document.index.built_at != built_at:
        raise PublicProfileError("public_profile_metadata_invalid")
    if repository_count is not None and document.index.repository_count != repository_count:
        raise PublicProfileError("public_profile_metadata_invalid")


def normalize_public_profile_scene(
    document: BilingualPublicProfile,
    *,
    sprite_content: bytes,
    background_content: bytes | None = None,
) -> BilingualPublicProfile:
    """Resolve only legacy profiles missing scene, using their active canonical sheet."""

    if document.character.scene is not None:
        return document
    try:
        scene = resolve_scene(
            {},
            sprite_content=sprite_content,
            revision=document.character.revision,
            background_content=background_content,
        ).public
    except ValueError as exc:
        raise PublicProfileError("public_profile_invalid") from exc
    return document.model_copy(
        update={"character": document.character.model_copy(update={"scene": scene})}
    )


def available_locales(document: BilingualPublicProfile) -> list[dict[str, str]]:
    """Public language choices in the site's configured order."""

    return [{"tag": tag, "endonym": get_language(tag).endonym} for tag in document.locales]


def localized_public_profile_bytes(document: BilingualPublicProfile, locale: str) -> bytes:
    """Return the public response for one exact enabled locale."""

    selected_locale = require_enabled(locale, document.locales)
    localized = document.locales[selected_locale]
    response = {
        "schema_version": 1,
        "locale": selected_locale,
        "available_locales": available_locales(document),
        **localized.model_dump(mode="json"),
        "character": document.character.model_dump(mode="json"),
        "index": document.index.model_dump(mode="json"),
    }
    if document.character.scene is None:
        response["character"].pop("scene", None)
    return _canonical_json(response)


def _canonical_json(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _canonical_timestamp(value: datetime) -> str:
    if value.tzinfo is None:
        raise ValueError("build timestamp must have a timezone")
    return value.astimezone(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _validate_public_url(value: str) -> None:
    parsed = urlsplit(value)
    localhost = parsed.hostname in {"localhost", "127.0.0.1", "::1"}
    if not parsed.netloc or parsed.username or parsed.password:
        raise ValueError("invalid public URL")
    if parsed.scheme != "https" and not (parsed.scheme == "http" and localhost):
        raise ValueError("invalid public URL")
