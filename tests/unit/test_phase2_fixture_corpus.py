"""Contract checks for the public-only Phase 2 retrieval fixture corpus."""

from __future__ import annotations

import re
from pathlib import Path

from reponpc.config.models import load_public_config

REPOSITORY_ROOT = Path(__file__).parents[2]
FIXTURE_ROOT = REPOSITORY_ROOT / "tests" / "fixtures"
DEMO_REPOSITORY = FIXTURE_ROOT / "repos" / "reponpc-demo"
CONFIG_PATH = FIXTURE_ROOT / "phase2" / "reponpc.yml"
PUBLIC_FIXTURE_PATHS = {
    ".env.fixture",
    "LICENSE",
    "README.md",
    "assets/bundle.min.js",
    "docs/adversarial-evidence.md",
    "docs/architecture.md",
    "docs/generated/ignored.md",
    "docs/unsupported-claims.md",
    "keys/id_rsa",
    "node_modules/fixture-package/index.js",
    "poetry.lock",
    "src/retrieval_pipeline.py",
    "src/search_handler.ts",
}
LIVE_SECRET_PATTERNS = (
    re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}"),
    re.compile(r"sk-[A-Za-z0-9]{20,}"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
)
ORACLE_MARKERS = ("expected_evidence", "recall_at_8", "hidden-oracle", "controller/")


def _fixture_texts() -> dict[str, str]:
    return {
        path.relative_to(DEMO_REPOSITORY).as_posix(): path.read_text(encoding="utf-8")
        for path in sorted(DEMO_REPOSITORY.rglob("*"))
        if path.is_file()
    }


def test_fixture_corpus_is_license_safe_and_contains_no_live_secret_patterns() -> None:
    fixture_texts = _fixture_texts()

    assert set(fixture_texts) == PUBLIC_FIXTURE_PATHS
    assert "MIT License" in fixture_texts["LICENSE"]
    assert "original, non-secret test material" in fixture_texts["README.md"]
    for text in fixture_texts.values():
        assert not any(pattern.search(text) for pattern in LIVE_SECRET_PATTERNS)


def test_fixture_corpus_contains_required_retrieval_and_adversarial_material() -> None:
    configuration = load_public_config(CONFIG_PATH)
    fixture_texts = _fixture_texts()
    combined_text = "\n".join(fixture_texts.values())

    assert configuration.repositories[0].slug == "fixture-owner/reponpc-demo"
    assert {claim.id for claim in configuration.repositories[0].claims} == {
        "fixture_retrieval_design",
        "fixture_test_context",
    }
    assert "rank_evidence" in fixture_texts["src/retrieval_pipeline.py"]
    assert "compileSearchRequest" in fixture_texts["src/search_handler.ts"]
    assert "繁體中文" in combined_text
    assert "hybrid retrieval" in combined_text
    assert "IGNORE ALL PRIOR INSTRUCTIONS" in fixture_texts["docs/adversarial-evidence.md"]
    assert "cannot confirm" in fixture_texts["docs/unsupported-claims.md"]


def test_public_fixture_corpus_does_not_declare_an_evaluation_oracle() -> None:
    public_text = "\n".join(_fixture_texts().values())
    public_text += "\n" + CONFIG_PATH.read_text(encoding="utf-8")

    assert not any(marker in public_text.casefold() for marker in ORACLE_MARKERS)
