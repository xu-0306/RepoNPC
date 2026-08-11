from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_foundation_preserves_approved_scope_and_phase_one_limitations() -> None:
    specification = (ROOT / "docs" / "TECHNICAL_SPEC.md").read_text(encoding="utf-8")
    delivery_phases = (ROOT / "docs" / "DELIVERY_PHASES.md").read_text(encoding="utf-8")
    handoff = (ROOT / "docs" / "P2_FOUNDATION_HANDOFF.md").read_text(encoding="utf-8")
    plan = (ROOT / ".agent-foreman" / "phase2-foundation" / "plan.json").read_text(encoding="utf-8")

    assert "| Status | **Approved** |" in specification
    assert "complete v1" in delivery_phases
    assert '"mode": "main_direct"' in plan
    assert "The three original worker delta guards remain failed/non-attributable" in handoff
    assert "Do not start P2-01 delegation" in handoff
