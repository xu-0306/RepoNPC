"""Deterministic, read-only release evidence audit.

The audit deliberately reports evidence availability rather than performing any
live release, provider, browser, GitHub, or host checks.  Callers provide an
explicit repository root; all paths inspected by this module remain beneath it.
"""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from typing import Any

_ALLOWED_STATUSES = frozenset({"pass", "fail", "not-run", "blocked"})
_EXTERNAL_CHECKS = (
    ("browser", "release-evidence/browser.json", "real browser evidence"),
    ("clean-host", "release-evidence/clean-host.json", "clean-host evidence"),
    ("github-profile", "release-evidence/github-profile.json", "real GitHub Profile evidence"),
    ("live-provider", "release-evidence/live-provider.json", "live provider evidence"),
    ("security-scan", "release-evidence/security-scan.json", "security scan evidence"),
    ("backup-restore", "release-evidence/backup-restore.json", "backup and restore evidence"),
    ("rollback", "release-evidence/rollback.json", "rollback evidence"),
)
_DOCUMENT_CHECKS = (
    ("technical-spec-approved", "docs/TECHNICAL_SPEC.md", "approved technical specification"),
    ("operations-document", "docs/OPERATIONS.md", "operations documentation"),
    ("security-document", "docs/SECURITY.md", "security documentation"),
    ("sprite-document", "docs/SPRITE_FORMAT.md", "sprite format documentation"),
)
_REQUIRED_FILE_CHECKS = (
    ("license", ("LICENSE", "LICENSE.txt"), "license notice"),
    ("notices", ("NOTICE", "NOTICES", "THIRD_PARTY_NOTICES.md"), "third-party notices"),
    ("security-reporting", ("SECURITY.md",), "security reporting policy"),
)
_STATUS_PATTERNS = (
    re.compile(r"^\s*\|\s*Status\s*\|\s*\*{0,2}([A-Za-z][A-Za-z -]*)", re.MULTILINE),
    re.compile(
        r"^\s*\*{0,2}Status\s*:\*{0,2}\s*\*{0,2}([A-Za-z][A-Za-z -]*)",
        re.MULTILINE,
    ),
)
_SENSITIVE_METADATA = re.compile(
    r"(?i)(?:api[_ -]?key|authorization|cookie|csrf|password|secret|"
    r"private[_ -]?key|credential|access[_ -]?token|bearer)"
)


def _record(
    check_id: str,
    status: str,
    evidence: str | list[str] | dict[str, Any],
    reason: str,
) -> dict[str, Any]:
    if status not in _ALLOWED_STATUSES:
        raise ValueError(f"unsupported audit status: {status}")
    return {"id": check_id, "status": status, "evidence": evidence, "reason": reason}


def _root_path(root: str | Path) -> Path:
    candidate = Path(root).expanduser()
    if not candidate.is_absolute():
        candidate = Path.cwd() / candidate
    return candidate.resolve(strict=False)


def _safe_child(root: Path, relative: str) -> Path:
    """Resolve a fixed relative path without allowing traversal."""

    child = (root / relative).resolve(strict=False)
    try:
        child.relative_to(root)
    except ValueError as error:
        raise ValueError(f"audit path escapes repository root: {relative}") from error
    return child


def _read_text(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return None


def _document_status(text: str) -> str | None:
    """Return a normalized explicit document status marker, if one exists."""

    matches = (match for pattern in _STATUS_PATTERNS for match in pattern.finditer(text))
    latest = max(matches, key=lambda match: match.start(), default=None)
    if latest is None:
        return None
    return " ".join(latest.group(1).split())


def _document_record(root: Path, check_id: str, relative: str, description: str) -> dict[str, Any]:
    try:
        path = _safe_child(root, relative)
    except ValueError:
        return _record(
            check_id,
            "blocked",
            {"path": relative, "present": False},
            f"{description} resolves outside the repository root.",
        )
    text = _read_text(path)
    if text is None:
        return _record(
            check_id,
            "not-run",
            {"path": relative, "present": False},
            f"{description} is missing or unreadable; verification was not run.",
        )

    status_marker = _document_status(text)
    evidence = {"path": relative, "present": True, "document_status": status_marker}
    if status_marker == "Approved":
        return _record(check_id, "pass", evidence, f"{description} declares Approved.")
    if status_marker == "Draft":
        return _record(
            check_id,
            "not-run",
            evidence,
            f"{description} declares Draft and is not release-ready.",
        )

    return _record(
        check_id,
        "blocked",
        evidence,
        f"{description} has no recognized Approved status marker.",
    )


def _non_secret_text(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = " ".join(value.split())
    if not normalized or _SENSITIVE_METADATA.search(normalized):
        return None
    return normalized


def _verified_artifact_references(root: Path, value: object) -> list[str] | None:
    if not isinstance(value, list) or not value:
        return None
    references: list[str] = []
    for item in value:
        if not isinstance(item, dict) or set(item) != {"path", "sha256"}:
            return None
        reference = _non_secret_text(item["path"])
        expected_sha256 = item["sha256"]
        if (
            reference is None
            or not isinstance(expected_sha256, str)
            or not re.fullmatch(r"[0-9a-f]{64}", expected_sha256)
        ):
            return None
        candidate = Path(reference)
        if candidate.is_absolute() or ".." in candidate.parts:
            return None
        normalized = candidate.as_posix()
        try:
            artifact = _safe_child(root, normalized)
        except ValueError:
            return None
        try:
            content = artifact.read_bytes()
        except OSError:
            return None
        if not content or sha256(content).hexdigest() != expected_sha256:
            return None
        references.append(normalized)
    return references


def _parse_dated_evidence(root: Path, path: Path) -> tuple[bool, str]:
    """Validate metadata completeness without executing an external release check."""

    raw = _read_text(path)
    if raw is None:
        return False, "evidence file is missing or unreadable"
    try:
        payload = json.loads(raw)
    except (TypeError, ValueError):
        return False, "evidence file is not valid JSON"
    if not isinstance(payload, dict):
        return False, "evidence file must contain a JSON object"
    observed_at = payload.get("observed_at")
    if not isinstance(observed_at, str) or not observed_at.strip():
        return False, "evidence has no dated observed_at value"
    try:
        observed = datetime.fromisoformat(observed_at.replace("Z", "+00:00"))
    except ValueError:
        return False, "evidence observed_at is not an ISO-8601 timestamp"
    if observed.tzinfo is None:
        return False, "evidence observed_at has no timezone"
    if observed > datetime.now(UTC):
        return False, "evidence observed_at is in the future"
    if payload.get("status") != "pass":
        return False, "evidence does not explicitly report pass"
    environment = _non_secret_text(payload.get("environment"))
    if environment is None:
        return False, "evidence has no non-secret environment detail"
    version = _non_secret_text(payload.get("version"))
    if version is None:
        return False, "evidence has no non-secret version detail"
    artifacts = _verified_artifact_references(root, payload.get("artifacts"))
    if artifacts is None:
        return False, "evidence has no existing hash-verified safe artifact reference"
    return (
        True,
        "dated evidence metadata is complete; external check was not executed by this audit",
    )


def _external_record(root: Path, check_id: str, relative: str, description: str) -> dict[str, Any]:
    try:
        path = _safe_child(root, relative)
    except ValueError:
        return _record(
            check_id,
            "not-run",
            {"path": relative, "verified": False},
            f"{description} resolves outside the repository root.",
        )
    verified, reason = _parse_dated_evidence(root, path)
    if verified:
        # The audit can record a supplied artifact, but it never performs the check itself.
        return _record(check_id, "pass", {"path": relative, "verified": True}, reason)
    return _record(
        check_id,
        "not-run",
        {"path": relative, "verified": False},
        f"{description} is unavailable or unverified: {reason}.",
    )


def _required_file_record(
    root: Path,
    check_id: str,
    candidates: tuple[str, ...],
    description: str,
) -> dict[str, Any]:
    for relative in candidates:
        try:
            path = _safe_child(root, relative)
        except ValueError:
            continue
        if path.is_file() and _read_text(path):
            return _record(
                check_id,
                "pass",
                {"path": relative, "present": True},
                f"{description} is present.",
            )
    return _record(
        check_id,
        "not-run",
        {"paths": list(candidates), "present": False},
        f"{description} is missing; release evidence was not run.",
    )


def _acceptance_coverage_record(root: Path) -> dict[str, Any]:
    relative = "docs/ACCEPTANCE_CRITERIA.md"
    try:
        path = _safe_child(root, relative)
    except ValueError:
        path = root / relative
    text = _read_text(path)
    if text is None:
        return _record(
            "acceptance-coverage",
            "not-run",
            {"path": relative, "present": False},
            "acceptance criteria document is missing or unreadable.",
        )
    found = {int(value) for value in re.findall(r"^###\s+AC-(\d{3})\b", text, re.MULTILINE)}
    required = set(range(1, 51))
    missing = sorted(required - found)
    if missing:
        return _record(
            "acceptance-coverage",
            "blocked",
            {"path": relative, "missing": [f"AC-{value:03d}" for value in missing]},
            "acceptance criteria coverage does not include AC-001 through AC-050.",
        )
    return _record(
        "acceptance-coverage",
        "pass",
        {"path": relative, "required": "AC-001 through AC-050"},
        "acceptance criteria document enumerates AC-001 through AC-050.",
    )


def audit_repository(root: str | Path) -> list[dict[str, Any]]:
    """Return stable release-readiness records for an explicit repository root.

    This function performs bounded local reads only.  It does not invoke a
    process, open a socket, contact a provider, mutate files, or update release
    state.  External records are ``not-run`` unless a caller-supplied evidence
    artifact contains a dated, explicit pass assertion.
    """

    repository_root = _root_path(root)
    if not repository_root.is_dir():
        return [
            _record(
                "repository-root",
                "fail",
                {"path": str(repository_root), "present": False},
                "explicit repository root does not exist or is not a directory.",
            )
        ]

    records = [
        _acceptance_coverage_record(repository_root),
        *(
            _required_file_record(repository_root, check_id, candidates, description)
            for check_id, candidates, description in _REQUIRED_FILE_CHECKS
        ),
        *(
            _document_record(repository_root, check_id, relative, description)
            for check_id, relative, description in _DOCUMENT_CHECKS
        ),
    ]
    records.extend(
        _external_record(repository_root, check_id, relative, description)
        for check_id, relative, description in _EXTERNAL_CHECKS
    )
    return sorted(records, key=lambda record: record["id"])


__all__ = ["audit_repository"]
