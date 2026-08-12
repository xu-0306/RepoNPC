"""Trace the owner-approved Phase 2 closure decision across governing documents."""

from __future__ import annotations

from pathlib import Path

REPOSITORY_ROOT = Path(__file__).parents[2]


def _read(path: str) -> str:
    return (REPOSITORY_ROOT / path).read_text(encoding="utf-8")


def test_technical_spec_freezes_phase2_closure_contracts() -> None:
    specification = _read("docs/TECHNICAL_SPEC.md")

    assert "| Status | **Approved** |" in specification
    assert "| Version | 0.1.1 |" in specification
    assert "reponpc index publish-manifest --bundle-dir <directory>" in specification
    assert "MUST NOT mutate the remote stable manifest" in specification
    assert '"locales": {' in specification
    assert "The locale keys MUST be exactly `zh-TW` and `en`" in specification
    assert "`pyproject.toml`, `package.json`, `Cargo.toml`, `go.mod`" in specification
    assert "only the repository fixture, public questions" in specification
    assert "`--cpus=4 --memory=8g`" in specification


def test_acceptance_and_adr_require_derived_formal_evidence() -> None:
    acceptance = _read("docs/ACCEPTANCE_CRITERIA.md")
    decisions = _read("docs/DECISIONS.md")

    assert "Technical Specification 0.1.1" in acceptance
    assert "Docker inspection and an access probe prove" in acceptance
    assert "host controller derives every pass/provenance boolean" in acceptance
    assert "## ADR-015:" in decisions
    assert "- **Status:** Accepted" in decisions.split("## ADR-015:", maxsplit=1)[1]
    assert "normal runtime image is not bloated" in decisions
    assert "prior failed delta evidence remains immutable history" in decisions


def test_phase_and_operations_documents_keep_runtime_provider_work_in_phase3() -> None:
    phases = _read("docs/DELIVERY_PHASES.md")
    implementation = _read("docs/IMPLEMENTATION_PLAN.md")
    operations = _read("docs/OPERATIONS.md")
    readme = _read("README.md")

    assert "optional build-time production `local_sentence_transformers` adapter" in phases
    assert "runtime query-provider health/readiness integration" in phases
    assert "host-only oracle/scoring" in phases
    assert "Technical Specification 0.1.1" in implementation
    assert "no oracle access" in implementation
    assert "reponpc index publish-manifest --bundle-dir dist" in operations
    assert "cannot update the remote pointer" in operations
    assert "Delivery Phase 2 closure in progress" in readme
