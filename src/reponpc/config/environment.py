"""Typed, fail-closed deployment environment loading.

Only variables documented in ``.env.example`` are accepted.  This boundary
keeps public deployment settings separate from secret values and deliberately
never includes supplied values or filesystem locations in its errors.
"""

from __future__ import annotations

import math
import os
import re
import stat
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Final

SECRET_MAX_BYTES: Final = 64 * 1024
DEFAULT_SECRET_ROOTS: Final = (Path("/run/secrets"),)
_SECRET_PAIRS: Final = {
    "github_token": ("REPONPC_GITHUB_TOKEN", "REPONPC_GITHUB_TOKEN_FILE"),
    "chat_api_key": ("REPONPC_CHAT_API_KEY", "REPONPC_CHAT_API_KEY_FILE"),
    "embedding_api_key": (
        "REPONPC_EMBEDDING_API_KEY",
        "REPONPC_EMBEDDING_API_KEY_FILE",
    ),
    "ip_hash_key": ("REPONPC_IP_HASH_KEY", "REPONPC_IP_HASH_KEY_FILE"),
}
_ENVIRONMENT_NAMES: Final = frozenset(
    {
        "REPONPC_ENV",
        "REPONPC_PUBLIC_BASE_URL",
        "REPONPC_HOST",
        "REPONPC_PORT",
        "REPONPC_DATA_DIR",
        "REPONPC_LOG_LEVEL",
        "REPONPC_TRUSTED_HOSTS",
        "REPONPC_ALLOWED_ORIGINS",
        "REPONPC_TRUSTED_PROXY_CIDRS",
        "REPONPC_CONFIG_REPOSITORY",
        "REPONPC_CONFIG_BRANCH",
        "REPONPC_CONFIG_PATH",
        "REPONPC_INDEX_MANIFEST_URL",
        "REPONPC_INDEX_POLL_SECONDS",
        "REPONPC_MAX_BUNDLE_BYTES",
        "REPONPC_KEEP_VALID_BUNDLES",
        "REPONPC_GITHUB_TOKEN",
        "REPONPC_GITHUB_TOKEN_FILE",
        "REPONPC_GITHUB_API_URL",
        "REPONPC_INDEX_WORKFLOW",
        "REPONPC_CHAT_PROVIDER",
        "REPONPC_CHAT_MODEL",
        "REPONPC_CHAT_BASE_URL",
        "REPONPC_CHAT_API_KEY",
        "REPONPC_CHAT_API_KEY_FILE",
        "REPONPC_CHAT_MAX_CONTEXT_TOKENS",
        "REPONPC_CHAT_MAX_OUTPUT_TOKENS",
        "REPONPC_CHAT_TIMEOUT_SECONDS",
        "REPONPC_EMBEDDING_PROVIDER",
        "REPONPC_EMBEDDING_MODEL",
        "REPONPC_EMBEDDING_DIMENSION",
        "REPONPC_EMBEDDING_NORMALIZED",
        "REPONPC_EMBEDDING_BASE_URL",
        "REPONPC_EMBEDDING_API_KEY",
        "REPONPC_EMBEDDING_API_KEY_FILE",
        "REPONPC_ADMIN_USERNAME",
        "REPONPC_ADMIN_PASSWORD_HASH",
        "REPONPC_ADMIN_IDLE_MINUTES",
        "REPONPC_ADMIN_ABSOLUTE_HOURS",
        "REPONPC_IP_HASH_KEY",
        "REPONPC_IP_HASH_KEY_FILE",
        "REPONPC_RATE_LIMIT_REQUESTS_PER_MINUTE",
        "REPONPC_GLOBAL_CHAT_CONCURRENCY",
        "REPONPC_DAILY_CHAT_REQUEST_BUDGET",
        "REPONPC_MAX_MESSAGE_CHARACTERS",
        "REPONPC_MAX_HISTORY_MESSAGES",
        "REPONPC_MAX_HISTORY_CHARACTERS",
        "REPONPC_INPUT_COST_PER_MILLION_TOKENS",
        "REPONPC_OUTPUT_COST_PER_MILLION_TOKENS",
        "REPONPC_SQLITE_BUSY_TIMEOUT_MS",
        "REPONPC_PROVIDER_HEALTH_SECONDS",
        "REPONPC_SSE_KEEPALIVE_SECONDS",
        "REPONPC_SHUTDOWN_GRACE_SECONDS",
        "REPONPC_PERSIST_CONVERSATIONS",
    }
)
_LOG_LEVELS: Final = frozenset({"CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"})
_PROVIDERS: Final = frozenset({"ollama", "openai_compatible"})
_EMBEDDING_PROVIDERS: Final = frozenset(
    {"local_sentence_transformers", "ollama", "openai_compatible"}
)
_REPOSITORY_SLUG_RE: Final = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")


@dataclass(frozen=True, slots=True)
class EnvironmentIssue:
    """A safe field-level environment validation result."""

    name: str
    code: str
    message: str


class EnvironmentValidationError(ValueError):
    """Failure whose representation intentionally omits values and paths."""

    def __init__(self, issues: Sequence[EnvironmentIssue]) -> None:
        self.issues = tuple(issues)
        super().__init__("deployment environment is invalid")


class SecretValue:
    """An opaque server-only secret whose normal representations are redacted.

    This deliberately is not a dataclass: :func:`dataclasses.asdict` traverses
    dataclass fields and would otherwise turn the private value into a plain
    mapping.  Slots also prevent accidental ``vars()`` serialization.
    """

    __slots__ = ("_value",)
    _value: str

    def __init__(self, value: str) -> None:
        object.__setattr__(self, "_value", value)

    def __setattr__(self, name: str, value: object) -> None:
        raise AttributeError("SecretValue is immutable")

    def reveal(self) -> str:
        """Return the value only to server-side callers that already own it."""

        return self._value

    def __repr__(self) -> str:
        return "SecretValue(<redacted>)"

    def __str__(self) -> str:
        return "<redacted>"


@dataclass(frozen=True, slots=True)
class EnvironmentSettings:
    """Validated deployment settings used by the application foundation."""

    environment: str
    public_base_url: str
    host: str
    port: int
    data_dir: Path
    log_level: str
    trusted_hosts: tuple[str, ...]
    allowed_origins: tuple[str, ...]
    trusted_proxy_cidrs: tuple[str, ...]
    config_repository: str
    config_branch: str
    config_path: str
    index_manifest_url: str
    index_poll_seconds: int
    max_bundle_bytes: int
    keep_valid_bundles: int
    github_api_url: str
    index_workflow: str
    chat_provider: str
    chat_model: str
    chat_base_url: str
    chat_max_context_tokens: int
    chat_max_output_tokens: int
    chat_timeout_seconds: int
    embedding_provider: str
    embedding_model: str
    embedding_dimension: int
    embedding_normalized: bool
    embedding_base_url: str
    admin_username: str
    admin_password_hash: SecretValue | None
    admin_idle_minutes: int
    admin_absolute_hours: int
    rate_limit_requests_per_minute: int
    global_chat_concurrency: int
    daily_chat_request_budget: int
    max_message_characters: int
    max_history_messages: int
    max_history_characters: int
    input_cost_per_million_tokens: float | None
    output_cost_per_million_tokens: float | None
    sqlite_busy_timeout_ms: int
    provider_health_seconds: int
    sse_keepalive_seconds: int
    shutdown_grace_seconds: int
    persist_conversations: bool
    secrets: Mapping[str, SecretValue]


def _issue(issues: list[EnvironmentIssue], name: str, code: str, message: str) -> None:
    issues.append(EnvironmentIssue(name=name, code=code, message=message))


def _present(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


def _text(
    values: Mapping[str, str],
    name: str,
    default: str,
    issues: list[EnvironmentIssue],
    *,
    allow_empty: bool = False,
) -> str:
    value = _present(values.get(name))
    if value is None:
        if allow_empty:
            return ""
        value = default
    if not value and not allow_empty:
        _issue(issues, name, "empty", "a non-empty value is required")
        return default
    return value


def _integer(
    values: Mapping[str, str],
    name: str,
    default: int,
    issues: list[EnvironmentIssue],
    *,
    minimum: int = 1,
    maximum: int | None = None,
) -> int:
    value = _present(values.get(name))
    if value is None:
        return default
    try:
        result = int(value)
    except ValueError:
        _issue(issues, name, "invalid_integer", "an integer is required")
        return default
    if result < minimum or (maximum is not None and result > maximum):
        _issue(issues, name, "out_of_range", "the value is outside the supported range")
        return default
    return result


def _optional_float(
    values: Mapping[str, str], name: str, issues: list[EnvironmentIssue]
) -> float | None:
    value = _present(values.get(name))
    if value is None:
        return None
    try:
        result = float(value)
    except ValueError:
        _issue(issues, name, "invalid_number", "a finite non-negative number is required")
        return None
    if not math.isfinite(result) or result < 0:
        _issue(issues, name, "invalid_number", "a finite non-negative number is required")
        return None
    return result


def _boolean(
    values: Mapping[str, str], name: str, default: bool, issues: list[EnvironmentIssue]
) -> bool:
    value = _present(values.get(name))
    if value is None:
        return default
    normalized = value.casefold()
    if normalized == "true":
        return True
    if normalized == "false":
        return False
    _issue(issues, name, "invalid_boolean", "true or false is required")
    return default


def _csv(values: Mapping[str, str], name: str, default: str) -> tuple[str, ...]:
    value = values.get(name, default)
    return tuple(item.strip() for item in value.split(",") if item.strip())


def _resolve_roots(secret_roots: Sequence[Path]) -> tuple[Path, ...]:
    return tuple(root.resolve(strict=False) for root in secret_roots)


def _inside_allowed_root(path: Path, roots: Sequence[Path]) -> bool:
    return any(path.is_relative_to(root) for root in roots)


def _read_open_secret_file(
    path: Path,
    roots: Sequence[Path],
    *,
    max_secret_bytes: int,
) -> tuple[bytes, os.stat_result]:
    """Read one resolved file without following a replacement symlink on POSIX."""

    read_flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_BINARY", 0)
    nofollow = getattr(os, "O_NOFOLLOW", 0)
    if os.name != "posix":
        file_descriptor = os.open(path, read_flags | nofollow)
        try:
            return os.read(file_descriptor, max_secret_bytes + 1), os.fstat(file_descriptor)
        finally:
            os.close(file_descriptor)

    directory_flags = read_flags | getattr(os, "O_DIRECTORY", 0) | nofollow
    for root in roots:
        try:
            relative_path = path.relative_to(root)
        except ValueError:
            continue
        if not relative_path.parts:
            raise OSError("secret file must not be the secret root")

        descriptors: list[int] = []
        try:
            directory_fd = os.open(root, directory_flags)
            descriptors.append(directory_fd)
            for segment in relative_path.parts[:-1]:
                directory_fd = os.open(segment, directory_flags, dir_fd=directory_fd)
                descriptors.append(directory_fd)
            file_descriptor = os.open(
                relative_path.name,
                read_flags | nofollow,
                dir_fd=directory_fd,
            )
            descriptors.append(file_descriptor)
            return os.read(file_descriptor, max_secret_bytes + 1), os.fstat(file_descriptor)
        finally:
            for descriptor in reversed(descriptors):
                os.close(descriptor)
    raise OSError("secret file is outside the allowed roots")


def _read_secret_file(
    name: str,
    raw_path: str,
    *,
    roots: Sequence[Path],
    issues: list[EnvironmentIssue],
    max_secret_bytes: int,
) -> SecretValue | None:
    try:
        candidate = Path(raw_path)
        if candidate.is_symlink():
            _issue(
                issues,
                name,
                "unsafe_secret_file",
                "the secret file is not an allowed regular file",
            )
            return None
        resolved = candidate.resolve(strict=True)
    except (OSError, RuntimeError, ValueError):
        _issue(issues, name, "unreadable_secret_file", "the secret file cannot be read safely")
        return None
    if not _inside_allowed_root(resolved, roots):
        _issue(
            issues,
            name,
            "secret_file_outside_root",
            "the secret file is outside an allowed root",
        )
        return None
    try:
        raw_content, file_stat = _read_open_secret_file(
            resolved,
            roots,
            max_secret_bytes=max_secret_bytes,
        )
    except OSError:
        _issue(issues, name, "unsafe_secret_file", "the secret file is not an allowed regular file")
        return None
    if not stat.S_ISREG(file_stat.st_mode):
        _issue(issues, name, "unsafe_secret_file", "the secret file is not an allowed regular file")
        return None
    if os.name == "posix" and file_stat.st_mode & (stat.S_IRGRP | stat.S_IROTH):
        _issue(
            issues,
            name,
            "unsafe_secret_permissions",
            "the secret file permissions are too broad",
        )
        return None
    if file_stat.st_size <= 0:
        _issue(issues, name, "empty_secret_file", "the secret file is empty")
        return None
    if file_stat.st_size > max_secret_bytes or len(raw_content) > max_secret_bytes:
        _issue(issues, name, "secret_file_too_large", "the secret file exceeds the size limit")
        return None
    try:
        content = raw_content.decode("utf-8").strip()
    except UnicodeDecodeError:
        _issue(issues, name, "invalid_secret_encoding", "the secret file must contain UTF-8 text")
        return None
    if not content:
        _issue(issues, name, "empty_secret_file", "the secret file is empty")
        return None
    return SecretValue(content)


def _load_secret(
    values: Mapping[str, str],
    name: str,
    file_name: str,
    *,
    roots: Sequence[Path],
    issues: list[EnvironmentIssue],
    max_secret_bytes: int,
) -> SecretValue | None:
    direct = _present(values.get(name))
    file_path = _present(values.get(file_name))
    if direct is not None and file_path is not None:
        _issue(
            issues,
            name,
            "secret_source_collision",
            "set either direct or file secret input, not both",
        )
        return None
    if direct is not None:
        return SecretValue(direct)
    if file_path is None:
        return None
    return _read_secret_file(
        file_name,
        file_path,
        roots=roots,
        issues=issues,
        max_secret_bytes=max_secret_bytes,
    )


def load_environment(
    environ: Mapping[str, str] | None = None,
    *,
    secret_roots: Sequence[Path] = DEFAULT_SECRET_ROOTS,
    max_secret_bytes: int = SECRET_MAX_BYTES,
) -> EnvironmentSettings:
    """Load documented deployment settings with safe, aggregate validation.

    Empty direct secret values are treated as absent; a configured secret file
    whose decoded content is empty is rejected.  This makes optional secrets
    usable during first-boot setup while preventing a mistaken empty file from
    silently authenticating as an empty credential.
    """

    source = {
        name: value
        for name, value in (environ or os.environ).items()
        if name.startswith("REPONPC_")
    }
    issues: list[EnvironmentIssue] = []
    for name in sorted(set(source) - _ENVIRONMENT_NAMES):
        _issue(
            issues,
            name,
            "unknown_variable",
            "the variable is not part of the deployment contract",
        )
    if max_secret_bytes <= 0:
        raise ValueError("max_secret_bytes must be positive")
    roots = _resolve_roots(secret_roots)
    if not roots:
        raise ValueError("at least one secret root is required")

    secrets = {
        logical_name: _load_secret(
            source,
            direct_name,
            file_name,
            roots=roots,
            issues=issues,
            max_secret_bytes=max_secret_bytes,
        )
        for logical_name, (direct_name, file_name) in _SECRET_PAIRS.items()
    }
    nonempty_secrets = {name: value for name, value in secrets.items() if value is not None}

    environment = _text(source, "REPONPC_ENV", "production", issues)
    if environment not in {"development", "production", "test"}:
        _issue(
            issues,
            "REPONPC_ENV",
            "invalid_choice",
            "development, production, or test is required",
        )
    log_level = _text(source, "REPONPC_LOG_LEVEL", "INFO", issues).upper()
    if log_level not in _LOG_LEVELS:
        _issue(issues, "REPONPC_LOG_LEVEL", "invalid_choice", "a supported log level is required")
    config_repository = _text(source, "REPONPC_CONFIG_REPOSITORY", "", issues)
    if config_repository and not _REPOSITORY_SLUG_RE.fullmatch(config_repository):
        _issue(issues, "REPONPC_CONFIG_REPOSITORY", "invalid_repository", "owner/name is required")
    chat_provider = _text(source, "REPONPC_CHAT_PROVIDER", "ollama", issues)
    if chat_provider not in _PROVIDERS:
        _issue(
            issues,
            "REPONPC_CHAT_PROVIDER",
            "invalid_choice",
            "a supported chat provider is required",
        )
    embedding_provider = _text(
        source,
        "REPONPC_EMBEDDING_PROVIDER",
        "local_sentence_transformers",
        issues,
    )
    if embedding_provider not in _EMBEDDING_PROVIDERS:
        _issue(
            issues,
            "REPONPC_EMBEDDING_PROVIDER",
            "invalid_choice",
            "a supported embedding provider is required",
        )
    embedding_normalized = _boolean(source, "REPONPC_EMBEDDING_NORMALIZED", True, issues)
    if not embedding_normalized:
        _issue(
            issues,
            "REPONPC_EMBEDDING_NORMALIZED",
            "must_be_true",
            "normalized embeddings are required",
        )
    persist_conversations = _boolean(source, "REPONPC_PERSIST_CONVERSATIONS", False, issues)
    if persist_conversations:
        _issue(
            issues,
            "REPONPC_PERSIST_CONVERSATIONS",
            "unsupported_value",
            "conversation persistence is not supported",
        )

    admin_hash = _present(source.get("REPONPC_ADMIN_PASSWORD_HASH"))
    settings = EnvironmentSettings(
        environment=environment,
        public_base_url=_text(source, "REPONPC_PUBLIC_BASE_URL", "", issues),
        host=_text(source, "REPONPC_HOST", "127.0.0.1", issues),
        port=_integer(source, "REPONPC_PORT", 8000, issues, maximum=65535),
        data_dir=Path(_text(source, "REPONPC_DATA_DIR", "/var/lib/reponpc", issues)),
        log_level=log_level,
        trusted_hosts=_csv(source, "REPONPC_TRUSTED_HOSTS", ""),
        allowed_origins=_csv(source, "REPONPC_ALLOWED_ORIGINS", ""),
        trusted_proxy_cidrs=_csv(source, "REPONPC_TRUSTED_PROXY_CIDRS", ""),
        config_repository=config_repository,
        config_branch=_text(source, "REPONPC_CONFIG_BRANCH", "main", issues),
        config_path=_text(source, "REPONPC_CONFIG_PATH", "reponpc.yml", issues),
        index_manifest_url=_text(source, "REPONPC_INDEX_MANIFEST_URL", "", issues),
        index_poll_seconds=_integer(source, "REPONPC_INDEX_POLL_SECONDS", 300, issues),
        max_bundle_bytes=_integer(
            source,
            "REPONPC_MAX_BUNDLE_BYTES",
            512 * 1024 * 1024,
            issues,
            maximum=1024 * 1024 * 1024,
        ),
        keep_valid_bundles=_integer(source, "REPONPC_KEEP_VALID_BUNDLES", 2, issues),
        github_api_url=_text(source, "REPONPC_GITHUB_API_URL", "https://api.github.com", issues),
        index_workflow=_text(source, "REPONPC_INDEX_WORKFLOW", "build-index.yml", issues),
        chat_provider=chat_provider,
        chat_model=_text(source, "REPONPC_CHAT_MODEL", "", issues),
        chat_base_url=_text(source, "REPONPC_CHAT_BASE_URL", "", issues),
        chat_max_context_tokens=_integer(source, "REPONPC_CHAT_MAX_CONTEXT_TOKENS", 32768, issues),
        chat_max_output_tokens=_integer(
            source, "REPONPC_CHAT_MAX_OUTPUT_TOKENS", 1000, issues, maximum=2000
        ),
        chat_timeout_seconds=_integer(
            source, "REPONPC_CHAT_TIMEOUT_SECONDS", 45, issues, maximum=300
        ),
        embedding_provider=embedding_provider,
        embedding_model=_text(source, "REPONPC_EMBEDDING_MODEL", "", issues),
        embedding_dimension=_integer(
            source, "REPONPC_EMBEDDING_DIMENSION", 384, issues, maximum=65536
        ),
        embedding_normalized=embedding_normalized,
        embedding_base_url=_text(
            source,
            "REPONPC_EMBEDDING_BASE_URL",
            "",
            issues,
            allow_empty=True,
        ),
        admin_username=_text(source, "REPONPC_ADMIN_USERNAME", "", issues),
        admin_password_hash=SecretValue(admin_hash) if admin_hash is not None else None,
        admin_idle_minutes=_integer(source, "REPONPC_ADMIN_IDLE_MINUTES", 30, issues),
        admin_absolute_hours=_integer(source, "REPONPC_ADMIN_ABSOLUTE_HOURS", 12, issues),
        rate_limit_requests_per_minute=_integer(
            source, "REPONPC_RATE_LIMIT_REQUESTS_PER_MINUTE", 10, issues
        ),
        global_chat_concurrency=_integer(source, "REPONPC_GLOBAL_CHAT_CONCURRENCY", 2, issues),
        daily_chat_request_budget=_integer(
            source, "REPONPC_DAILY_CHAT_REQUEST_BUDGET", 200, issues
        ),
        max_message_characters=_integer(
            source, "REPONPC_MAX_MESSAGE_CHARACTERS", 2000, issues, maximum=4000
        ),
        max_history_messages=_integer(
            source, "REPONPC_MAX_HISTORY_MESSAGES", 6, issues, maximum=10
        ),
        max_history_characters=_integer(
            source, "REPONPC_MAX_HISTORY_CHARACTERS", 6000, issues, maximum=12000
        ),
        input_cost_per_million_tokens=_optional_float(
            source, "REPONPC_INPUT_COST_PER_MILLION_TOKENS", issues
        ),
        output_cost_per_million_tokens=_optional_float(
            source, "REPONPC_OUTPUT_COST_PER_MILLION_TOKENS", issues
        ),
        sqlite_busy_timeout_ms=_integer(
            source, "REPONPC_SQLITE_BUSY_TIMEOUT_MS", 5000, issues, maximum=60000
        ),
        provider_health_seconds=_integer(
            source, "REPONPC_PROVIDER_HEALTH_SECONDS", 60, issues, maximum=3600
        ),
        sse_keepalive_seconds=_integer(
            source, "REPONPC_SSE_KEEPALIVE_SECONDS", 15, issues, maximum=60
        ),
        shutdown_grace_seconds=_integer(
            source, "REPONPC_SHUTDOWN_GRACE_SECONDS", 30, issues, maximum=300
        ),
        persist_conversations=persist_conversations,
        secrets=MappingProxyType(nonempty_secrets),
    )
    if "*" in settings.allowed_origins:
        _issue(
            issues,
            "REPONPC_ALLOWED_ORIGINS",
            "wildcard_origin_forbidden",
            "wildcard origins are not supported",
        )
    if issues:
        raise EnvironmentValidationError(issues)
    return settings
