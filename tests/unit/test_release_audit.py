"""Focused contract tests for the Phase 5 read-only release audit."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from pathlib import Path

import pytest

from tools.release_audit import audit_repository

ALLOWED_STATUSES = {"pass", "fail", "not-run", "blocked"}
EXTERNAL_IDS = {
    "clean-host",
    "github-profile",
    "live-provider",
    "browser",
}


def _write_snapshot(root: Path, *, operations_status: str = "Draft") -> None:
    (root / "docs").mkdir(parents=True)
    (root / "docs" / "TECHNICAL_SPEC.md").write_text(
        "# Technical Specification\n\n| Status | **Approved** |\n",
        encoding="utf-8",
    )
    (root / "docs" / "OPERATIONS.md").write_text(
        f"# Operations\n\n**Status:** {operations_status}\n",
        encoding="utf-8",
    )
    (root / "docs" / "SECURITY.md").write_text(
        "# Security\n\n**Status:** Draft\n",
        encoding="utf-8",
    )
    (root / "docs" / "SPRITE_FORMAT.md").write_text(
        "# Sprite\n\n**Status:** Draft\n",
        encoding="utf-8",
    )


def _normalised(records: object) -> str:
    return json.dumps(records, ensure_ascii=True, sort_keys=True, separators=(",", ":"))


def test_release_audit_records_have_stable_shape_and_json_values(tmp_path: Path) -> None:
    _write_snapshot(tmp_path)

    records = audit_repository(tmp_path)

    assert isinstance(records, list)
    assert records
    assert [record["id"] for record in records] == sorted(record["id"] for record in records)
    assert len({record["id"] for record in records}) == len(records)
    for record in records:
        assert set(record) == {"id", "status", "evidence", "reason"}
        assert record["status"] in ALLOWED_STATUSES
        assert isinstance(record["evidence"], (str, list, dict))
        assert isinstance(record["reason"], str) and record["reason"]
    json.dumps(records, ensure_ascii=True, sort_keys=True)


def test_release_audit_determinism_is_byte_stable(tmp_path: Path) -> None:
    _write_snapshot(tmp_path)

    first = _normalised(audit_repository(tmp_path))
    second = _normalised(audit_repository(tmp_path))

    assert first == second


def test_release_audit_fail_closed_for_missing_external_evidence(tmp_path: Path) -> None:
    _write_snapshot(tmp_path)

    records = audit_repository(tmp_path)
    external = {record["id"]: record for record in records if record["id"] in EXTERNAL_IDS}

    assert set(external) == EXTERNAL_IDS
    assert all(record["status"] in {"not-run", "blocked"} for record in external.values())
    assert not any(record["status"] == "pass" for record in external.values())


def test_release_audit_fail_closed_for_draft_documents(tmp_path: Path) -> None:
    _write_snapshot(tmp_path)

    records = {record["id"]: record for record in audit_repository(tmp_path)}

    for check_id in ("operations-document", "security-document", "sprite-document"):
        assert records[check_id]["status"] in {"not-run", "blocked", "fail"}
        assert records[check_id]["status"] != "pass"
        assert records[check_id]["evidence"]["document_status"] == "Draft"


def test_release_audit_uses_last_document_status_declaration(tmp_path: Path) -> None:
    _write_snapshot(tmp_path)
    (tmp_path / "docs" / "OPERATIONS.md").write_text(
        "# Operations\n\n| Status | Approved |\n\n**Status:** Draft\n",
        encoding="utf-8",
    )

    records = {record["id"]: record for record in audit_repository(tmp_path)}

    assert records["operations-document"]["status"] == "not-run"
    assert records["operations-document"]["evidence"]["document_status"] == "Draft"


def test_release_audit_fail_closed_for_unverified_external_evidence(tmp_path: Path) -> None:
    _write_snapshot(tmp_path)
    evidence_dir = tmp_path / "release-evidence"
    evidence_dir.mkdir()
    for name in ("clean-host", "github-profile", "live-provider", "browser"):
        (evidence_dir / f"{name}.json").write_text(
            json.dumps({"status": "pass", "observed_at": "not-a-date"}),
            encoding="utf-8",
        )

    records = audit_repository(tmp_path)
    external = [record for record in records if record["id"] in EXTERNAL_IDS]

    assert all(record["status"] in {"not-run", "blocked"} for record in external)
    assert not any(record["status"] == "pass" for record in external)


def test_release_audit_fail_closed_for_incomplete_external_metadata(tmp_path: Path) -> None:
    _write_snapshot(tmp_path)
    evidence_dir = tmp_path / "release-evidence"
    evidence_dir.mkdir()
    for name in ("clean-host", "github-profile", "live-provider", "browser"):
        (evidence_dir / f"{name}.json").write_text(
            json.dumps({"status": "pass", "observed_at": "2020-01-01T00:00:00Z"}),
            encoding="utf-8",
        )

    records = audit_repository(tmp_path)
    external = [record for record in records if record["id"] in EXTERNAL_IDS]

    assert all(record["status"] in {"not-run", "blocked"} for record in external)
    assert all("environment detail" in record["reason"] for record in external)


def test_release_audit_fail_closed_for_missing_referenced_artifact(tmp_path: Path) -> None:
    _write_snapshot(tmp_path)
    evidence_dir = tmp_path / "release-evidence"
    evidence_dir.mkdir()
    for name in ("clean-host", "github-profile", "live-provider", "browser"):
        (evidence_dir / f"{name}.json").write_text(
            json.dumps(
                {
                    "status": "pass",
                    "observed_at": "2020-01-01T00:00:00Z",
                    "environment": "fixture host",
                    "version": "fixture version",
                    "artifacts": [
                        {
                            "path": f"release-evidence/{name}.txt",
                            "sha256": "0" * 64,
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )

    records = audit_repository(tmp_path)
    external = [record for record in records if record["id"] in EXTERNAL_IDS]

    assert all(record["status"] in {"not-run", "blocked"} for record in external)
    assert all("hash-verified safe artifact" in record["reason"] for record in external)


def test_release_audit_accepts_complete_hashed_external_evidence(tmp_path: Path) -> None:
    _write_snapshot(tmp_path)
    evidence_dir = tmp_path / "release-evidence"
    evidence_dir.mkdir()
    for name in ("clean-host", "github-profile", "live-provider", "browser"):
        artifact = evidence_dir / f"{name}.txt"
        content = f"sanitized {name} observation\n".encode()
        artifact.write_bytes(content)
        (evidence_dir / f"{name}.json").write_text(
            json.dumps(
                {
                    "status": "pass",
                    "observed_at": "2020-01-01T00:00:00Z",
                    "environment": "fixture host",
                    "version": "fixture version",
                    "artifacts": [
                        {
                            "path": f"release-evidence/{name}.txt",
                            "sha256": sha256(content).hexdigest(),
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )

    records = audit_repository(tmp_path)
    external = [record for record in records if record["id"] in EXTERNAL_IDS]

    assert all(record["status"] == "pass" for record in external)
    assert all(record["evidence"]["verified"] is True for record in external)


def test_release_audit_fail_closed_for_future_external_evidence(tmp_path: Path) -> None:
    _write_snapshot(tmp_path)
    evidence_dir = tmp_path / "release-evidence"
    evidence_dir.mkdir()
    artifact = evidence_dir / "browser.txt"
    content = b"sanitized browser observation\n"
    artifact.write_bytes(content)
    (evidence_dir / "browser.json").write_text(
        json.dumps(
            {
                "status": "pass",
                "observed_at": (datetime.now(UTC) + timedelta(days=1)).isoformat(),
                "environment": "fixture host",
                "version": "fixture version",
                "artifacts": [
                    {
                        "path": "release-evidence/browser.txt",
                        "sha256": sha256(content).hexdigest(),
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    records = {record["id"]: record for record in audit_repository(tmp_path)}

    assert records["browser"]["status"] == "not-run"
    assert "in the future" in records["browser"]["reason"]


def test_release_audit_fail_closed_for_symlinked_artifact_escape(tmp_path: Path) -> None:
    root = tmp_path / "repository"
    root.mkdir()
    _write_snapshot(root)
    evidence_dir = root / "release-evidence"
    evidence_dir.mkdir()
    outside = tmp_path / "outside.txt"
    content = b"outside observation\n"
    outside.write_bytes(content)
    link = evidence_dir / "browser.txt"
    try:
        link.symlink_to(outside)
    except OSError as error:
        pytest.skip(f"host cannot create symlink: {error}")
    (evidence_dir / "browser.json").write_text(
        json.dumps(
            {
                "status": "pass",
                "observed_at": "2020-01-01T00:00:00Z",
                "environment": "fixture host",
                "version": "fixture version",
                "artifacts": [
                    {
                        "path": "release-evidence/browser.txt",
                        "sha256": sha256(content).hexdigest(),
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    records = {record["id"]: record for record in audit_repository(root)}

    assert records["browser"]["status"] == "not-run"
    assert records["browser"]["evidence"]["verified"] is False


def test_release_audit_scope_does_not_write_or_use_external_capabilities(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_snapshot(tmp_path)
    before = sorted(
        (path.relative_to(tmp_path).as_posix(), path.read_bytes())
        for path in tmp_path.rglob("*")
        if path.is_file()
    )

    def forbidden(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("external capability used by read-only audit")

    monkeypatch.setattr("subprocess.run", forbidden)
    monkeypatch.setattr("socket.socket", forbidden)
    monkeypatch.setattr("urllib.request.urlopen", forbidden)

    audit_repository(tmp_path)

    after = sorted(
        (path.relative_to(tmp_path).as_posix(), path.read_bytes())
        for path in tmp_path.rglob("*")
        if path.is_file()
    )
    assert after == before


def test_release_audit_covers_acceptance_and_release_input_gates(tmp_path: Path) -> None:
    _write_snapshot(tmp_path)

    records = {record["id"]: record for record in audit_repository(tmp_path)}

    assert records["acceptance-coverage"]["status"] in {"not-run", "blocked"}
    assert records["license"]["status"] == "not-run"
    assert records["notices"]["status"] == "not-run"
    assert records["security-reporting"]["status"] == "not-run"
    for check_id in ("security-scan", "backup-restore", "rollback"):
        assert records[check_id]["status"] == "not-run"


def test_release_audit_requires_every_accepted_criterion_through_ac_050(tmp_path: Path) -> None:
    _write_snapshot(tmp_path)
    acceptance = tmp_path / "docs" / "ACCEPTANCE_CRITERIA.md"
    acceptance.write_text(
        "# Acceptance Criteria\n\n"
        + "\n".join(f"### AC-{index:03d} — Fixture" for index in range(1, 51)),
        encoding="utf-8",
    )

    records = {record["id"]: record for record in audit_repository(tmp_path)}
    assert records["acceptance-coverage"]["status"] == "pass"
    assert records["acceptance-coverage"]["evidence"]["required"] == ("AC-001 through AC-050")

    acceptance.write_text(
        "# Acceptance Criteria\n\n"
        + "\n".join(f"### AC-{index:03d} — Fixture" for index in range(1, 50)),
        encoding="utf-8",
    )
    records = {record["id"]: record for record in audit_repository(tmp_path)}
    assert records["acceptance-coverage"]["status"] == "blocked"
    assert records["acceptance-coverage"]["evidence"]["missing"] == ["AC-050"]
