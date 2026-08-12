"""Canonical bilingual public profile production and validation."""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from typing import Annotated, Literal, cast
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from reponpc.config.models import Locale, PublicConfig

MAX_PUBLIC_PROFILE_BYTES = 1024 * 1024
LOCALE_ORDER: tuple[Locale, Locale] = ("zh-TW", "en")
REQUIRED_LOCALES = frozenset(LOCALE_ORDER)
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
    schema_version: Literal[1]
    locales: dict[Locale, LocalizedPublicProfile]
    character: CharacterMetadata
    index: IndexMetadata

    @model_validator(mode="after")
    def validate_bilingual_equivalence(self) -> BilingualPublicProfile:
        if set(self.locales) != REQUIRED_LOCALES:
            raise ValueError("required locales are missing or unknown")
        zh_tw = self.locales["zh-TW"]
        english = self.locales["en"]
        if (
            len(zh_tw.repositories) != self.index.repository_count
            or len(english.repositories) != self.index.repository_count
        ):
            raise ValueError("repository count mismatch")
        if (
            zh_tw.profile.display_name,
            zh_tw.profile.location,
            zh_tw.profile.avatar_url,
            [link.url for link in zh_tw.profile.links],
        ) != (
            english.profile.display_name,
            english.profile.location,
            english.profile.avatar_url,
            [link.url for link in english.profile.links],
        ):
            raise ValueError("non-localized profile fields differ")
        zh_repositories = [(item.slug, item.tags, item.demo_url) for item in zh_tw.repositories]
        en_repositories = [(item.slug, item.tags, item.demo_url) for item in english.repositories]
        if zh_repositories != en_repositories:
            raise ValueError("non-localized repository fields differ")
        return self


def build_public_profile_bytes(
    *,
    config: PublicConfig,
    index_version: str,
    built_at: datetime,
    repository_count: int,
) -> bytes:
    """Build deterministic internal schema-v1 bytes from validated inputs."""

    repositories = tuple(repository for repository in config.repositories if repository.enabled)
    if repository_count != len(repositories):
        raise PublicProfileError("public_profile_metadata_invalid")
    try:
        locales = {
            locale: LocalizedPublicProfile(
                profile=PublicProfile(
                    display_name=config.profile.display_name,
                    headline=config.profile.headline[locale],
                    bio=config.profile.bio[locale],
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
                    )
                    for repository in repositories
                ],
                suggested_questions=list(config.profile.suggested_questions[locale]),
            )
            for locale in LOCALE_ORDER
        }
        document = BilingualPublicProfile(
            schema_version=1,
            locales=locales,
            character=CharacterMetadata(
                mode=config.character.mode,
                asset_url="/api/public/character.png",
                revision=config.character.revision,
            ),
            index=IndexMetadata(
                version=index_version,
                built_at=_canonical_timestamp(built_at),
                repository_count=repository_count,
            ),
        )
    except (KeyError, ValidationError, ValueError) as exc:
        raise PublicProfileError("public_profile_generation_failed") from exc
    return _canonical_json(document.model_dump(mode="json"))


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


def localized_public_profile_bytes(document: BilingualPublicProfile, locale: str) -> bytes:
    """Return the unchanged public response contract for one exact locale."""

    if locale not in REQUIRED_LOCALES:
        raise PublicProfileError("public_profile_locale_invalid")
    selected_locale = cast(Locale, locale)
    localized = document.locales[selected_locale]
    response = {
        "schema_version": 1,
        "locale": selected_locale,
        **localized.model_dump(mode="json"),
        "character": document.character.model_dump(mode="json"),
        "index": document.index.model_dump(mode="json"),
    }
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
