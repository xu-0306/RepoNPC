from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from reponpc.config.models import load_public_config
from reponpc.indexing.public_profile import (
    PublicRepository,
    build_public_profile_bytes,
    parse_public_profile_bytes,
)
from reponpc.indexing.sources import ResolvedRepository

FIXTURE_CONFIG = Path(__file__).parents[1] / "fixtures" / "phase2" / "reponpc.yml"


def _snapshot(**metadata: object) -> ResolvedRepository:
    return ResolvedRepository(
        slug="fixture-owner/reponpc-demo",
        commit_sha="a" * 40,
        default_branch="main",
        github_html_url="https://github.com/fixture-owner/reponpc-demo",
        blobs=(),
        **metadata,
    )


def test_profile_carries_only_bounded_metadata_from_the_resolved_snapshot() -> None:
    payload = build_public_profile_bytes(
        config=load_public_config(FIXTURE_CONFIG),
        index_version="fixture-v1",
        built_at=datetime(2026, 9, 29, tzinfo=UTC),
        repository_count=1,
        repository_snapshots=(_snapshot(language="Python", stars=42, forks=7),),
    )

    document = parse_public_profile_bytes(payload)
    for locale in ("zh-TW", "en"):
        repository = document.locales[locale].repositories[0]
        assert (repository.language, repository.stars, repository.forks) == (
            "Python",
            42,
            7,
        )


def test_missing_source_metadata_remains_unknown_not_zero() -> None:
    payload = build_public_profile_bytes(
        config=load_public_config(FIXTURE_CONFIG),
        index_version="fixture-v1",
        built_at=datetime(2026, 9, 29, tzinfo=UTC),
        repository_count=1,
    )
    raw = json.loads(payload)
    for locale in ("zh-TW", "en"):
        repository = raw["locales"][locale]["repositories"][0]
        assert repository["language"] is None
        assert repository["stars"] is None
        assert repository["forks"] is None


@pytest.mark.parametrize("field", ["stars", "forks"])
def test_public_repository_counts_are_bounded(field: str) -> None:
    values: dict[str, object] = {
        "slug": "owner/repo",
        "summary": "Summary",
        "role": "Role",
        "tags": [],
        "demo_url": None,
        field: -1,
    }
    with pytest.raises(ValidationError):
        PublicRepository.model_validate(values)
