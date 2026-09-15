"""Trace the owner-approved Phase 2 closure decision across governing documents."""

from __future__ import annotations

from pathlib import Path

REPOSITORY_ROOT = Path(__file__).parents[2]


def _read(path: str) -> str:
    return (REPOSITORY_ROOT / path).read_text(encoding="utf-8")


def test_technical_spec_freezes_phase2_closure_contracts() -> None:
    specification = _read("docs/TECHNICAL_SPEC.md")

    assert "| Status | **Approved** |" in specification
    assert "| Version | 0.3.0 |" in specification
    assert "ADR-037" in specification
    assert "Version 0.1.1 records the owner-approved Phase 2 closure boundary" in specification
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

    assert "Technical Specification 0.3.0" in acceptance
    assert "Docker inspection and an access probe prove" in acceptance
    assert "host controller derives every pass/provenance boolean" in acceptance
    assert "## ADR-015:" in decisions
    assert "- **Status:** Accepted" in decisions.split("## ADR-015:", maxsplit=1)[1]
    assert "normal runtime image is not bloated" in decisions
    assert "prior failed delta evidence remains immutable history" in decisions


def test_vllm_preset_is_documented_without_expanding_browser_or_bundle_contracts() -> None:
    specification = _read("docs/TECHNICAL_SPEC.md")
    decisions = _read("docs/DECISIONS.md")
    operations = _read("docs/OPERATIONS.md")
    environment = _read(".env.example")

    assert "Version 0.1.5 records the owner-approved vLLM provider-preset" in specification
    assert "## ADR-019: Treat vLLM as a named OpenAI-compatible deployment preset" in decisions
    assert "REPONPC_CHAT_PROVIDER=vllm" in environment
    assert "REPONPC_EMBEDDING_PROVIDER=vllm" in environment
    assert "GET /v1/models" in operations
    assert "POST /v1/chat/completions" in operations
    assert "POST /v1/embeddings" in operations


def test_loopback_launch_and_public_read_credential_retirement_are_normative() -> None:
    specification = _read("docs/TECHNICAL_SPEC.md")
    acceptance = _read("docs/ACCEPTANCE_CRITERIA.md")
    decisions = _read("docs/DECISIONS.md")
    security = _read("docs/SECURITY.md")
    operations = _read("docs/OPERATIONS.md")

    assert "## ADR-027: Make loopback administration passwordless" in decisions
    assert "## ADR-028: Retire GitHub OAuth and public-read PATs" in decisions
    assert "POST /api/admin/session/local-launch" in specification
    assert "410 GITHUB_PUBLIC_READ_CREDENTIALS_REMOVED" in specification
    assert "Version 0.2.1 retirement amendment" in acceptance
    assert "## 19. Passwordless loopback launch (0.2.0)" in security
    assert "## 20. GitHub public-read credential retirement (0.2.1)" in security
    assert "/admin#local-launch=<grant>" in operations
    assert (
        "GITHUB_PUBLIC_READ_CREDENTIAL_REMOVAL_PLAN.md" in operations
        or "anonymous REST" in operations
    )


def test_model_first_onboarding_contract_is_traceable() -> None:
    specification = _read("docs/TECHNICAL_SPEC.md")
    acceptance = _read("docs/ACCEPTANCE_CRITERIA.md")
    decisions = _read("docs/DECISIONS.md")
    handoff = _read("docs/ONBOARDING_FLOW_IMPLEMENTATION_HANDOFF.md")

    assert "### 11.6 Model-first guided onboarding (0.2.3)" in specification
    assert "FR-041" in specification and "FR-042" in specification
    assert "### AC-058 - Model-first AI flow and immediate manual flow" in acceptance
    assert (
        "### AC-059 - Clean first-run analysis works before public index activation" in acceptance
    )
    assert (
        "### AC-060 - Recovery, revision changes and old guided state preserve work" in acceptance
    )
    assert "## ADR-030:" in decisions
    assert "ONBOARDING_FLOW_IMPLEMENTATION_HANDOFF.md" in decisions

    for step in ("models", "projects", "analysis", "contribution", "basic information", "draft"):
        assert step in specification.lower()

    assert "0.2.3" in handoff
    assert "H0" in handoff and "H4" in handoff


def test_environment_connection_controls_are_normative_and_secret_safe() -> None:
    specification = _read("docs/TECHNICAL_SPEC.md")
    acceptance = _read("docs/ACCEPTANCE_CRITERIA.md")
    decisions = _read("docs/DECISIONS.md")
    security = _read("docs/SECURITY.md")
    operations = _read("docs/OPERATIONS.md")

    assert "## ADR-031:" in decisions
    assert "HOST_CONNECTION_REPLACEMENT_REQUIRED" in specification
    assert "host_managed_connection_overrides" in decisions
    assert "host-managed cards" in acceptance.lower()
    assert "environment URL/key remain unreadable" in security
    assert "http://127.0.0.1:22434" in operations


def test_connection_updates_rebind_only_safe_candidates() -> None:
    specification = _read("docs/TECHNICAL_SPEC.md")
    acceptance = _read("docs/ACCEPTANCE_CRITERIA.md")
    decisions = _read("docs/DECISIONS.md")
    security = _read("docs/SECURITY.md")
    operations = _read("docs/OPERATIONS.md")

    assert "## ADR-032:" in decisions
    assert "directly referencing candidates" in specification
    assert "previous last-known-good" in specification
    assert "selection generation" in decisions
    assert "Migration 22" in acceptance
    assert "No automatic retest" in security
    assert "do not edit-save each model again" in operations


def test_valid_admin_sessions_resume_after_a_page_reload_without_grant_replay() -> None:
    specification = _read("docs/TECHNICAL_SPEC.md")
    acceptance = _read("docs/ACCEPTANCE_CRITERIA.md")
    decisions = _read("docs/DECISIONS.md")
    security = _read("docs/SECURITY.md")
    operations = _read("docs/OPERATIONS.md")

    assert "## ADR-033:" in decisions
    assert "POST /api/admin/session/resume" in specification
    assert "reloading a page with a still-valid session resumes it" in acceptance
    assert "domain-separated" in security
    assert "does not require another launcher grant" in operations
