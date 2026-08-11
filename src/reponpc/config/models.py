"""Strict public configuration contract for ``reponpc.yml``.

The public YAML file is untrusted input. This module intentionally exposes a
sanitized error representation that omits rejected values.
"""

from __future__ import annotations

import re
from pathlib import Path, PurePosixPath
from typing import Annotated, Any, Literal
from urllib.parse import urlsplit

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

Locale = Literal["zh-TW", "en"]
LocalizedText = dict[str, str]
CLAIM_ID_RE = re.compile(r"^[a-z][a-z0-9_-]{2,63}$")
HEX_COLOR_RE = re.compile(r"^#[0-9a-fA-F]{6}$")
MAX_CONFIG_BYTES = 1024 * 1024
SECRET_KEY_PARTS = (
    "api_key",
    "apikey",
    "password",
    "secret",
    "token",
    "credential",
    "private_url",
)


class StrictModel(BaseModel):
    """Base for versioned public structures: unknown keys always fail."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)


class ConfigIssue(StrictModel):
    path: str
    code: str
    message: str


class ConfigValidationError(ValueError):
    """Safe configuration failure that never contains rejected values."""

    def __init__(self, issues: list[ConfigIssue]) -> None:
        self.issues = tuple(issues)
        super().__init__("public configuration is invalid")


def _localized(value: LocalizedText, supported: tuple[Locale, ...], path: str) -> None:
    expected = set(supported)
    actual = set(value)
    if actual != expected:
        missing = sorted(expected - actual)
        extra = sorted(actual - expected)
        raise ValueError(f"{path} locale keys mismatch; missing={missing}, extra={extra}")
    if any(not text for text in value.values()):
        raise ValueError(f"{path} localized values must be non-empty")


def _https_url(value: str | None) -> str | None:
    if value is None:
        return None
    parsed = urlsplit(value)
    localhost = parsed.hostname in {"localhost", "127.0.0.1", "::1"}
    if not parsed.netloc or parsed.username or parsed.password:
        raise ValueError("URL must be absolute and must not contain credentials")
    if parsed.scheme != "https" and not (parsed.scheme == "http" and localhost):
        raise ValueError("URL must use HTTPS")
    return value


def _relative_pattern(value: str) -> str:
    if not value or "\\" in value or value.startswith("/"):
        raise ValueError("path pattern must be a repository-relative POSIX path")
    parts = PurePosixPath(value).parts
    if ".." in parts or "." in parts:
        raise ValueError("path pattern must not traverse parent/current directories")
    return value


def _reject_secret_keys(value: Any, path: tuple[str, ...] = ()) -> None:
    if isinstance(value, dict):
        for raw_key, nested in value.items():
            key = str(raw_key).casefold().replace("-", "_")
            if any(part in key for part in SECRET_KEY_PARTS):
                location = ".".join((*path, str(raw_key)))
                raise ConfigValidationError(
                    [
                        ConfigIssue(
                            path=location,
                            code="secret_field",
                            message="secrets are not allowed",
                        )
                    ]
                )
            _reject_secret_keys(nested, (*path, str(raw_key)))
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            _reject_secret_keys(nested, (*path, str(index)))


class LocalesConfig(StrictModel):
    default: Locale
    supported: tuple[Locale, ...]

    @model_validator(mode="after")
    def validate_supported(self) -> LocalesConfig:
        if len(self.supported) != len(set(self.supported)):
            raise ValueError("supported locales must be unique")
        if set(self.supported) != {"zh-TW", "en"}:
            raise ValueError("v1 supported locales must be exactly zh-TW and en")
        if self.default not in self.supported:
            raise ValueError("default locale must be supported")
        return self


class LocalizedLink(StrictModel):
    label: LocalizedText
    url: str

    _validate_url = field_validator("url")(_https_url)


class ProfileConfig(StrictModel):
    display_name: Annotated[str, Field(min_length=1, max_length=80)]
    headline: LocalizedText
    bio: LocalizedText
    location: Annotated[str | None, Field(max_length=120)] = None
    avatar_url: str | None = None
    links: tuple[LocalizedLink, ...] = ()
    greeting: LocalizedText
    suggested_questions: dict[str, tuple[str, ...]]

    _validate_avatar = field_validator("avatar_url")(_https_url)


class ClaimConfig(StrictModel):
    id: str
    kind: Literal["role", "responsibility", "achievement", "context"]
    statement: LocalizedText

    @field_validator("id")
    @classmethod
    def validate_id(cls, value: str) -> str:
        if not CLAIM_ID_RE.fullmatch(value):
            raise ValueError("claim ID has an invalid format")
        return value


class RepositoryConfig(StrictModel):
    slug: str
    enabled: bool = True
    ref: str | None = None
    role: LocalizedText
    summary: LocalizedText
    tags: tuple[Annotated[str, Field(min_length=1, max_length=64)], ...] = ()
    demo_url: str | None = None
    include: tuple[str, ...]
    exclude: tuple[str, ...] = ()
    claims: tuple[ClaimConfig, ...] = ()

    _validate_demo = field_validator("demo_url")(_https_url)

    @field_validator("slug")
    @classmethod
    def validate_slug(cls, value: str) -> str:
        parts = value.split("/")
        if len(parts) != 2 or any(not part or part in {".", ".."} for part in parts):
            raise ValueError("repository slug must be owner/name")
        return value

    @field_validator("include", "exclude")
    @classmethod
    def validate_patterns(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(_relative_pattern(value) for value in values)


class BuiltinCharacterConfig(StrictModel):
    body: Literal["standard"]
    skin: Literal["light", "medium", "dark"]
    hair: Literal["none", "short", "long"]
    hair_color: str
    outfit: Literal["adventurer", "engineer", "mage"]
    primary_color: str
    secondary_color: str
    accessory: Literal["none", "glasses", "headphones"]

    @field_validator("hair_color", "primary_color", "secondary_color")
    @classmethod
    def validate_color(cls, value: str) -> str:
        if not HEX_COLOR_RE.fullmatch(value):
            raise ValueError("color must be a six-digit hexadecimal value")
        return value.lower()


class CustomCharacterConfig(StrictModel):
    sprite_path: str

    @field_validator("sprite_path")
    @classmethod
    def validate_sprite_path(cls, value: str) -> str:
        value = _relative_pattern(value)
        if not value.startswith("assets/character/") or not value.endswith(".png"):
            raise ValueError("custom sprite must be a PNG below assets/character/")
        if len(PurePosixPath(value).parts) != 3:
            raise ValueError("nested custom sprite paths are not allowed")
        return value


class CharacterAnimationConfig(StrictModel):
    frame_duration_ms: Annotated[int, Field(ge=80, le=1000)]
    movement: Literal["none", "subtle"]


class CharacterConfig(StrictModel):
    mode: Literal["builtin", "custom"]
    revision: Annotated[int, Field(ge=0)]
    builtin: BuiltinCharacterConfig | None = None
    custom: CustomCharacterConfig | None = None
    animation: CharacterAnimationConfig

    @model_validator(mode="after")
    def validate_mode(self) -> CharacterConfig:
        if self.mode == "builtin" and (self.builtin is None or self.custom is not None):
            raise ValueError("builtin mode requires builtin settings only")
        if self.mode == "custom" and (self.custom is None or self.builtin is not None):
            raise ValueError("custom mode requires custom settings only")
        return self


class CardAnimationConfig(StrictModel):
    enabled: bool
    frame_duration_ms: Annotated[int, Field(ge=80, le=1000)]


class CardThemeConfig(StrictModel):
    background: str
    panel: str
    text: str
    accent: str
    border: str

    @field_validator("background", "panel", "text", "accent", "border")
    @classmethod
    def validate_color(cls, value: str) -> str:
        if not HEX_COLOR_RE.fullmatch(value):
            raise ValueError("color must be a six-digit hexadecimal value")
        return value.lower()


class CardThemesConfig(StrictModel):
    light: CardThemeConfig
    dark: CardThemeConfig


class CardConfig(StrictModel):
    revision: Annotated[int, Field(ge=0)]
    call_to_action: LocalizedText
    show_repository_count: bool
    animation: CardAnimationConfig
    themes: CardThemesConfig


class ParserConfig(StrictModel):
    tree_sitter_languages: tuple[Literal["python", "javascript", "typescript", "go", "rust"], ...]


class ChunkingConfig(StrictModel):
    max_characters: Annotated[int, Field(gt=0, le=12000)]
    max_lines: Annotated[int, Field(gt=0, le=400)]
    fallback_overlap_lines: Annotated[int, Field(ge=0, le=40)]

    @model_validator(mode="after")
    def validate_overlap(self) -> ChunkingConfig:
        if self.fallback_overlap_lines >= self.max_lines:
            raise ValueError("fallback overlap must be smaller than max lines")
        return self


class RetrievalLimitsConfig(StrictModel):
    max_file_bytes: Annotated[int, Field(gt=0, le=2 * 1024 * 1024)]
    max_repository_text_bytes: Annotated[int, Field(gt=0, le=100 * 1024 * 1024)]
    max_corpus_text_bytes: Annotated[int, Field(gt=0, le=250 * 1024 * 1024)]
    max_evidence_records: Annotated[int, Field(gt=0, le=100000)]


class EmbeddingConfig(StrictModel):
    # Prefix whitespace is part of the declared embedding identity (for
    # example ``query: ``).  The base model strips presentation fields, but
    # stripping here would silently change both index and runtime semantics.
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=False)

    adapter: Literal["local_sentence_transformers", "openai_compatible", "ollama"]
    model: Annotated[str, Field(min_length=1, max_length=200)]
    dimension: Annotated[int, Field(gt=0, le=65536)]
    normalized: Literal[True]
    query_prefix: Annotated[str, Field(max_length=64)]
    passage_prefix: Annotated[str, Field(max_length=64)]


class FusionConfig(StrictModel):
    rrf_k: Annotated[int, Field(gt=0, le=1000)]
    lexical_weight: Annotated[float, Field(ge=0)]
    vector_weight: Annotated[float, Field(ge=0)]
    candidate_count_per_channel: Annotated[int, Field(gt=0, le=100)]
    final_context_records: Annotated[int, Field(gt=0, le=20)]
    max_records_per_repository: Annotated[int, Field(gt=0, le=20)]

    @model_validator(mode="after")
    def validate_weights(self) -> FusionConfig:
        if self.lexical_weight == 0 and self.vector_weight == 0:
            raise ValueError("at least one retrieval channel weight must be positive")
        return self


class SourceWeightsConfig(StrictModel):
    owner_assertions: Annotated[float, Field(ge=0)]
    repository_metadata: Annotated[float, Field(ge=0)]
    documentation: Annotated[float, Field(ge=0)]
    source_code: Annotated[float, Field(ge=0)]


class RetrievalConfig(StrictModel):
    enabled_sources: tuple[
        Literal["owner_assertions", "repository_metadata", "documentation", "source_code"], ...
    ]
    parsers: ParserConfig
    chunking: ChunkingConfig
    limits: RetrievalLimitsConfig
    embedding: EmbeddingConfig
    fusion: FusionConfig
    source_weights: SourceWeightsConfig


class PublicConfig(StrictModel):
    schema_version: Literal[1]
    locales: LocalesConfig
    profile: ProfileConfig
    repositories: tuple[RepositoryConfig, ...]
    character: CharacterConfig
    card: CardConfig
    retrieval: RetrievalConfig

    @model_validator(mode="after")
    def validate_cross_field_contracts(self) -> PublicConfig:
        supported = self.locales.supported
        _localized(self.profile.headline, supported, "profile.headline")
        _localized(self.profile.bio, supported, "profile.bio")
        _localized(self.profile.greeting, supported, "profile.greeting")
        if set(self.profile.suggested_questions) != set(supported):
            raise ValueError("profile.suggested_questions locale keys mismatch")
        for questions in self.profile.suggested_questions.values():
            if not questions or any(not question for question in questions):
                raise ValueError("suggested questions must be non-empty")
        for link in self.profile.links:
            _localized(link.label, supported, "profile.links.label")
        _localized(self.card.call_to_action, supported, "card.call_to_action")

        slugs = [repository.slug for repository in self.repositories]
        if len(slugs) != len(set(slugs)):
            raise ValueError("repository slugs must be unique")
        claim_ids: list[str] = []
        for repository in self.repositories:
            _localized(repository.role, supported, f"repositories.{repository.slug}.role")
            _localized(repository.summary, supported, f"repositories.{repository.slug}.summary")
            for claim in repository.claims:
                _localized(claim.statement, supported, f"claims.{claim.id}.statement")
                claim_ids.append(claim.id)
        if len(claim_ids) != len(set(claim_ids)):
            raise ValueError("owner claim IDs must be globally unique")
        return self


def _safe_issues(exc: ValidationError) -> list[ConfigIssue]:
    return [
        ConfigIssue(
            path=".".join(str(item) for item in error["loc"]) or "$",
            code=str(error["type"]),
            message=str(error["msg"]),
        )
        for error in exc.errors(include_url=False, include_context=False, include_input=False)
    ]


def validate_public_config(data: Any) -> PublicConfig:
    """Validate decoded YAML data and return an immutable public configuration."""

    _reject_secret_keys(data)
    try:
        return PublicConfig.model_validate(data)
    except ValidationError as exc:
        raise ConfigValidationError(_safe_issues(exc)) from None


def load_public_config(path: str | Path, *, max_bytes: int = MAX_CONFIG_BYTES) -> PublicConfig:
    """Load bounded UTF-8 YAML without accepting aliases or custom objects."""

    config_path = Path(path)
    raw = config_path.read_bytes()
    if len(raw) > max_bytes:
        raise ConfigValidationError(
            [
                ConfigIssue(
                    path="$",
                    code="file_too_large",
                    message="configuration exceeds size limit",
                )
            ]
        )
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        raise ConfigValidationError(
            [ConfigIssue(path="$", code="invalid_encoding", message="configuration must be UTF-8")]
        ) from None
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError:
        raise ConfigValidationError(
            [ConfigIssue(path="$", code="invalid_yaml", message="configuration is not valid YAML")]
        ) from None
    return validate_public_config(data)
