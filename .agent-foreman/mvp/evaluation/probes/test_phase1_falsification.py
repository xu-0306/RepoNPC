"""Fresh black-box-style falsification probes for the Phase 1 MVP.

This module belongs to the evaluator, not the production suite.  It deliberately
uses production contracts only through their published callable/HTTP boundaries.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient
from pydantic import ValidationError

from reponpc.api import public
from reponpc.api.public import SetupState
from reponpc.config.models import ConfigValidationError, load_public_config
from reponpc.domain.evidence import EvidenceClass, EvidenceRecord
from reponpc.main import create_app

ROOT = Path(__file__).resolve().parents[4]


class ScopeGateError(RuntimeError):
    """Raised by this evaluator's documented pre-launch scope gate."""


def _approved_spec(path: Path) -> bool:
    text = path.read_text(encoding="utf-8")
    return "| Status | **Approved** |" in text and "**Approved by:** project owner" in text


def _scope_guarded_production_trigger(spec_path: Path) -> int:
    """Run the actual FastAPI health boundary only after the scope precondition."""

    if not _approved_spec(spec_path):
        raise ScopeGateError("Technical Specification approval is required before application launch")
    with TestClient(create_app()) as client:
        return client.get("/healthz").status_code


def test_authorized_scope_rejects_injected_draft_before_real_entrypoint(tmp_path: Path) -> None:
    """INV-AUTHORIZED-SCOPE: a Draft spec must prevent the launch trigger."""

    actual_spec = ROOT / "docs" / "TECHNICAL_SPEC.md"
    assert _scope_guarded_production_trigger(actual_spec) == 200

    draft_spec = tmp_path / "TECHNICAL_SPEC-draft.md"
    draft_spec.write_text(
        actual_spec.read_text(encoding="utf-8").replace(
            "| Status | **Approved** |", "| Status | **Draft** |", 1
        ),
        encoding="utf-8",
    )
    with pytest.raises(ScopeGateError, match="approval"):
        _scope_guarded_production_trigger(draft_spec)


def test_config_loader_rejects_nested_secret_key_without_echoing_value(tmp_path: Path) -> None:
    """INV-CONFIG-STRICT: invoke the production YAML loader against a canary."""

    payload = yaml.safe_load((ROOT / "reponpc.example.yml").read_text(encoding="utf-8"))
    canary = "EVAL-CONFIG-SECRET-DO-NOT-ECHO"
    payload["profile"]["openaiApiKey"] = canary
    candidate = tmp_path / "nested-secret.yml"
    candidate.write_text(yaml.safe_dump(payload, allow_unicode=True), encoding="utf-8")

    with pytest.raises(ConfigValidationError) as captured:
        load_public_config(candidate)
    assert any(issue.path == "profile.openaiApiKey" for issue in captured.value.issues)
    assert canary not in str(captured.value)
    assert canary not in repr(captured.value.issues)


def test_evidence_record_rejects_malformed_repository_slug() -> None:
    """INV-EVIDENCE-STABLE: source metadata must retain the owner/name contract."""

    with pytest.raises(ValidationError):
        EvidenceRecord.model_validate(
            {
                "evidence_class": EvidenceClass.REPOSITORY_FACT,
                "repository_slug": "owner/repo/extra",
                "commit_sha": "a" * 40,
                "path": "src/app.py",
                "start_line": 1,
                "end_line": 1,
                "content": "safe source line",
            }
        )


def test_public_status_does_not_reflect_private_state_canaries() -> None:
    """INV-PUBLIC-SETUP-SAFE: trigger the real HTTP status route with bad state."""

    canary = "EVAL-PRIVATE-PROVIDER-URL-http://ollama.internal:11434"
    app = create_app(
        setup_state=SetupState(
            index_ready=True,
            index_version=canary,
            model_ready=False,
            model_provider=canary,
        )
    )
    with TestClient(app) as client:
        response = client.get("/api/public/status")

    assert response.status_code == 200
    assert canary not in response.text


def test_profile_route_passes_selected_locale_to_message_boundary(monkeypatch: pytest.MonkeyPatch) -> None:
    """INV-I18N-PARITY: fault-inject tagged translations through the real route."""

    def tagged_translate(locale: str, key: str, /, **_: object) -> str:
        return f"EVAL-LOCALE-{locale}-{key}"

    monkeypatch.setattr(public, "translate", tagged_translate)
    with TestClient(create_app()) as client:
        zh_tw = client.get("/api/public/profile", params={"locale": "zh-TW"})
        en = client.get("/api/public/profile", params={"locale": "en"})

    assert zh_tw.json()["error"]["message"] == "EVAL-LOCALE-zh-TW-index_unavailable"
    assert en.json()["error"]["message"] == "EVAL-LOCALE-en-index_unavailable"
