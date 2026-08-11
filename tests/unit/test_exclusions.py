from __future__ import annotations

from dataclasses import FrozenInstanceError, fields, replace
from inspect import signature

import pytest

from reponpc.indexing.exclusions import (
    ExclusionDecision,
    ExclusionPolicy,
    ExclusionReason,
    SourceEntryKind,
    SourceMetadata,
    classify_source,
)


def policy(
    *,
    include_patterns: tuple[str, ...] = ("README.md", "docs/**", "src/**"),
    repository_exclude_patterns: tuple[str, ...] = (),
    global_exclude_patterns: tuple[str, ...] = (),
    max_file_bytes: int = 100,
    max_repository_text_bytes: int = 1_000,
    max_corpus_text_bytes: int = 10_000,
) -> ExclusionPolicy:
    return ExclusionPolicy(
        include_patterns=include_patterns,
        repository_exclude_patterns=repository_exclude_patterns,
        global_exclude_patterns=global_exclude_patterns,
        max_file_bytes=max_file_bytes,
        max_repository_text_bytes=max_repository_text_bytes,
        max_corpus_text_bytes=max_corpus_text_bytes,
    )


def metadata(**changes: object) -> SourceMetadata:
    candidate = SourceMetadata(entry_kind=SourceEntryKind.REGULAR_FILE, size_bytes=10)
    return replace(candidate, **changes)


def assert_reason(
    path: str,
    expected: ExclusionReason,
    *,
    candidate: SourceMetadata | None = None,
    rules: ExclusionPolicy | None = None,
) -> None:
    decision = classify_source(path, candidate or metadata(), rules or policy())
    assert decision == ExclusionDecision(
        include=expected is ExclusionReason.ELIGIBLE,
        reason_code=expected,
    )


def test_purity_accepts_only_path_metadata_and_policy_and_returns_body_free_decision() -> None:
    assert tuple(signature(classify_source).parameters) == ("path", "metadata", "policy")
    assert tuple(field.name for field in fields(SourceMetadata)) == (
        "entry_kind",
        "size_bytes",
        "is_binary",
        "is_decodable",
        "has_high_confidence_secret",
        "repository_text_bytes_before",
        "corpus_text_bytes_before",
    )
    assert tuple(field.name for field in fields(ExclusionDecision)) == ("include", "reason_code")

    decision = classify_source("src/app.py", metadata(), policy())

    assert decision == ExclusionDecision(True, ExclusionReason.ELIGIBLE)
    assert "CANARY-SOURCE-BODY" not in repr(decision)


def test_purity_values_are_immutable() -> None:
    candidate = metadata()
    rules = policy()

    with pytest.raises(FrozenInstanceError):
        candidate.size_bytes = 11  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        rules.max_file_bytes = 99  # type: ignore[misc]


@pytest.mark.parametrize(
    "path",
    [
        "../outside.py",
        "/absolute.py",
        "src\\alias.py",
        "./src/app.py",
        "src//app.py",
        "src/./app.py",
        "src/app.py/",
        "C:/workspace/app.py",
        "src/\x00app.py",
    ],
)
def test_invalid_paths_fail_closed(path: str) -> None:
    assert_reason(path, ExclusionReason.INVALID_PATH)


@pytest.mark.parametrize(
    ("candidate", "expected"),
    [
        (metadata(entry_kind=SourceEntryKind.SYMLINK), ExclusionReason.SYMLINK),
        (metadata(entry_kind=SourceEntryKind.SUBMODULE), ExclusionReason.SUBMODULE),
        (metadata(entry_kind=SourceEntryKind.OTHER), ExclusionReason.NOT_REGULAR_FILE),
        (metadata(is_binary=True), ExclusionReason.BINARY),
        (metadata(is_decodable=False), ExclusionReason.UNDECODABLE),
        (metadata(has_high_confidence_secret=True), ExclusionReason.HIGH_CONFIDENCE_SECRET),
    ],
)
def test_mandatory_metadata_exclusions_win_over_include_rules(
    candidate: SourceMetadata,
    expected: ExclusionReason,
) -> None:
    assert_reason("src/app.py", expected, candidate=candidate)


def test_invalid_metadata_fails_closed() -> None:
    assert_reason("src/app.py", ExclusionReason.INVALID_METADATA, candidate=metadata(size_bytes=-1))
    assert_reason(
        "src/app.py",
        ExclusionReason.INVALID_METADATA,
        candidate=metadata(entry_kind="regular_file"),  # type: ignore[arg-type]
    )
    assert_reason(
        "src/app.py",
        ExclusionReason.INVALID_METADATA,
        candidate=metadata(is_binary=1),  # type: ignore[arg-type]
    )


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        (".env.production", ExclusionReason.ENVIRONMENT_FILE),
        ("keys/id_rsa", ExclusionReason.CREDENTIAL_OR_KEY),
        ("certs/service.pem", ExclusionReason.CREDENTIAL_OR_KEY),
        ("src/.git/config", ExclusionReason.GIT_METADATA),
        ("node_modules/pkg/index.js", ExclusionReason.DEPENDENCY_OR_VENDOR),
        ("docs/generated/reference.md", ExclusionReason.BUILD_GENERATED_OR_CACHE),
        ("static/app.min.js", ExclusionReason.MINIFIED_OR_SOURCE_MAP),
        ("maps/app.js.map", ExclusionReason.MINIFIED_OR_SOURCE_MAP),
        ("archives/index.tar.zst", ExclusionReason.ARCHIVE_MEDIA_OR_DATABASE),
        ("media/portrait.png", ExclusionReason.ARCHIVE_MEDIA_OR_DATABASE),
        ("data/index.sqlite", ExclusionReason.ARCHIVE_MEDIA_OR_DATABASE),
        ("poetry.lock", ExclusionReason.LOCK_FILE),
    ],
)
def test_mandatory_path_exclusions_win_over_include_rules(
    path: str,
    expected: ExclusionReason,
) -> None:
    assert_reason(path, expected, rules=policy(include_patterns=("**",)))


def test_secret_and_environment_paths_cannot_be_reincluded_by_negated_rules() -> None:
    rules = policy(
        include_patterns=("**",),
        global_exclude_patterns=(".env*", "!.env.production"),
        repository_exclude_patterns=("!keys/id_rsa",),
    )

    assert_reason(".env.production", ExclusionReason.ENVIRONMENT_FILE, rules=rules)
    assert_reason("keys/id_rsa", ExclusionReason.CREDENTIAL_OR_KEY, rules=rules)


def test_configured_rules_use_gitignore_style_double_star_and_rule_order() -> None:
    rules = policy(
        include_patterns=("src/**", "docs/**", "!docs/private/**"),
        repository_exclude_patterns=("docs/**", "!docs/public/**", "!docs/private/**"),
        global_exclude_patterns=("src/ignored/**",),
    )

    assert_reason("src/ignored/client.py", ExclusionReason.GLOBAL_EXCLUDED, rules=rules)
    assert_reason("docs/private/notes.md", ExclusionReason.NOT_INCLUDED, rules=rules)
    assert_reason("docs/draft.md", ExclusionReason.REPOSITORY_EXCLUDED, rules=rules)
    assert_reason("docs/public/guide.md", ExclusionReason.ELIGIBLE, rules=rules)
    assert_reason("other/file.py", ExclusionReason.NOT_INCLUDED, rules=rules)


def test_filename_rule_matches_any_repository_depth_and_empty_include_is_fail_closed() -> None:
    assert_reason(
        "docs/README.md",
        ExclusionReason.ELIGIBLE,
        rules=policy(include_patterns=("README.md",)),
    )
    assert_reason("src/app.py", ExclusionReason.NOT_INCLUDED, rules=policy(include_patterns=()))


def test_directory_rule_matches_descendants_at_any_depth() -> None:
    assert_reason(
        "docs/ignored/nested/reference.md",
        ExclusionReason.REPOSITORY_EXCLUDED,
        rules=policy(repository_exclude_patterns=("docs/ignored/",)),
    )


def test_individual_and_cumulative_budgets_fail_closed_before_admission() -> None:
    rules = policy(
        include_patterns=("src/**",),
        max_file_bytes=10,
        max_repository_text_bytes=16,
        max_corpus_text_bytes=24,
    )

    assert_reason(
        "src/app.py",
        ExclusionReason.FILE_TOO_LARGE,
        candidate=metadata(size_bytes=11),
        rules=rules,
    )
    assert_reason(
        "src/app.py",
        ExclusionReason.REPOSITORY_TEXT_BUDGET_EXCEEDED,
        candidate=metadata(size_bytes=10, repository_text_bytes_before=7),
        rules=rules,
    )
    assert_reason(
        "src/app.py",
        ExclusionReason.CORPUS_TEXT_BUDGET_EXCEEDED,
        candidate=metadata(size_bytes=10, corpus_text_bytes_before=15),
        rules=rules,
    )
    assert_reason(
        "src/app.py",
        ExclusionReason.ELIGIBLE,
        candidate=metadata(
            size_bytes=9,
            repository_text_bytes_before=7,
            corpus_text_bytes_before=15,
        ),
        rules=rules,
    )


@pytest.mark.parametrize(
    "kwargs",
    [
        {"max_file_bytes": 0},
        {"max_repository_text_bytes": True},
        {"include_patterns": ("../outside",)},
        {"repository_exclude_patterns": ("src\\generated/**",)},
        {"global_exclude_patterns": ("!",)},
    ],
)
def test_invalid_policy_values_are_rejected(kwargs: dict[str, object]) -> None:
    with pytest.raises(ValueError):
        policy(**kwargs)  # type: ignore[arg-type]
