from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

import yaml
from argon2 import PasswordHasher, Type
from fastapi.testclient import TestClient

from reponpc.admin.auth import AdminSessionService
from reponpc.admin.onboarding import GuidedOnboardingError, GuidedOnboardingService
from reponpc.admin.operations import AdminOperations
from reponpc.main import create_app
from reponpc.runtime.database import RuntimeDatabase

ORIGIN = "https://portfolio.example.com"
PASSWORD = "npcx"


class RecordingOnboarding:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self.failure: GuidedOnboardingError | None = None

    def _record(self, operation: str, values: dict[str, Any]) -> None:
        self.calls.append((operation, values))
        if self.failure is not None:
            raise self.failure

    def discover_repositories(self, *, account: str, page: int) -> dict[str, object]:
        self._record("discover", {"account": account, "page": page})
        return {"repositories": [_metadata()], "page": page, "has_more": False}

    def resolve_repository(self, *, repository: str, ref: str | None) -> dict[str, object]:
        self._record("resolve", {"repository": repository, "ref": ref})
        return {**_metadata(), "ref": ref}

    def analyze_repository(self, **values: Any) -> dict[str, object]:
        values["cancel_requested"] = values["cancel_requested"].is_set()
        self._record("analyze", values)
        return {
            "repository": {
                "slug": values["slug"],
                "commit_sha": "a" * 40,
                "default_branch": "main",
                "html_url": "https://github.com/octocat/demo",
            },
            "facts": [
                {
                    "evidence_class": "REPOSITORY_FACT",
                    "evidence_id": "E_1234",
                    "path": "README.md",
                    "start_line": 1,
                    "end_line": 2,
                    "text": "Public repository overview",
                }
            ],
            "inferences": [
                {
                    "evidence_class": "MODEL_INFERENCE",
                    "statement": {
                        "zh-TW": "此 repository 包含架構說明。",
                        "en": "The repository contains an architecture overview.",
                    },
                    "supporting_evidence_ids": ["E_1234"],
                }
            ],
            "skipped_summary": {"count": 0, "reasons": []},
        }

    def suggest_contributions(self, **values: Any) -> dict[str, object]:
        self._record("suggest", values)
        return {
            "slug": values["slug"],
            "original_statement": values["owner_statement"],
            "proposal": {
                "role": {"zh-TW": "共同維護者", "en": "Co-maintainer"},
                "summary": {"zh-TW": "維護解析器", "en": "Maintained the parser"},
                "claims": [],
            },
            "confirmed": False,
        }

    def create_draft(self, **values: Any) -> dict[str, object]:
        self._record("draft", values)
        return {
            "content": "schema_version: 1\n",
            "validation": {"valid": True, "errors": [], "warnings": []},
        }


def _metadata() -> dict[str, object]:
    return {
        "slug": "octocat/demo",
        "name": "demo",
        "description": "Public demo",
        "primary_language": "Python",
        "default_branch": "main",
        "is_fork": False,
        "is_archived": False,
        "updated_at": "2026-08-14T00:00:00Z",
        "html_url": "https://github.com/octocat/demo",
    }


def _application(tmp_path: Path) -> tuple[Any, RecordingOnboarding]:
    database = RuntimeDatabase(tmp_path)
    database.initialize()
    auth = AdminSessionService(
        database=database,
        username="admin",
        password_hash=PasswordHasher(type=Type.ID).hash(PASSWORD),
        identity_hmac_key=b"o" * 32,
        now=lambda: datetime(2026, 8, 14, tzinfo=UTC),
    )
    onboarding = RecordingOnboarding()
    operations = AdminOperations(
        None,
        database,
        ORIGIN,
        onboarding=cast(GuidedOnboardingService, onboarding),
    )
    return (
        create_app(
            admin_session_service=auth,
            admin_origins=(ORIGIN,),
            admin_operations=operations,
        ),
        onboarding,
    )


def _login(client: TestClient) -> str:
    response = client.post(
        "/api/admin/session",
        headers={"Origin": ORIGIN},
        json={"username": "admin", "password": PASSWORD},
    )
    assert response.status_code == 200
    return str(response.json()["csrf_token"])


def _public_config() -> dict[str, object]:
    path = Path(__file__).parents[2] / "reponpc.example.yml"
    parsed = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(parsed, dict)
    return parsed


def test_metadata_routes_are_authenticated_same_origin_and_do_not_start_analysis(
    tmp_path: Path,
) -> None:
    app, onboarding = _application(tmp_path)
    with TestClient(app, base_url=ORIGIN) as client:
        unauthenticated = client.post(
            "/api/admin/onboarding/repositories/discover",
            headers={"Origin": ORIGIN},
            json={"account": "octocat", "page": 1},
        )
        _login(client)
        discovered = client.post(
            "/api/admin/onboarding/repositories/discover",
            headers={"Origin": ORIGIN},
            json={"account": "octocat", "page": 1},
        )
        resolved = client.post(
            "/api/admin/onboarding/repositories/resolve",
            headers={"Origin": ORIGIN},
            json={"repository": "https://github.com/octocat/demo", "ref": "main"},
        )

    assert unauthenticated.status_code == 401
    assert discovered.status_code == resolved.status_code == 200
    assert discovered.headers["cache-control"] == resolved.headers["cache-control"] == "no-store"
    assert discovered.json()["repositories"][0]["slug"] == "octocat/demo"
    assert resolved.json()["ref"] == "main"
    assert [name for name, _values in onboarding.calls] == ["discover", "resolve"]


def test_provider_routes_require_current_csrf_and_preserve_evidence_classes(
    tmp_path: Path,
) -> None:
    app, onboarding = _application(tmp_path)
    with TestClient(app, base_url=ORIGIN) as client:
        csrf = _login(client)
        denied = client.post(
            "/api/admin/onboarding/repositories/analyze",
            headers={"Origin": ORIGIN},
            json={"slug": "octocat/demo", "ref": None, "include": [], "exclude": []},
        )
        analyzed = client.post(
            "/api/admin/onboarding/repositories/analyze",
            headers={"Origin": ORIGIN, "X-CSRF-Token": csrf},
            json={"slug": "octocat/demo", "ref": None, "include": [], "exclude": []},
        )
        suggested = client.post(
            "/api/admin/onboarding/contributions/suggest",
            headers={"Origin": ORIGIN, "X-CSRF-Token": csrf},
            json={
                "slug": "octocat/demo",
                "owner_statement": "I maintained the parser with another contributor.",
            },
        )

    assert denied.status_code == 403
    assert denied.json()["error"]["code"] == "CSRF_FAILED"
    assert analyzed.status_code == suggested.status_code == 200
    assert analyzed.json()["facts"][0]["evidence_class"] == "REPOSITORY_FACT"
    assert analyzed.json()["inferences"][0]["evidence_class"] == "MODEL_INFERENCE"
    assert suggested.json()["confirmed"] is False
    assert suggested.json()["original_statement"].startswith("I maintained")
    assert [name for name, _values in onboarding.calls] == ["analyze", "suggest"]


def test_draft_is_local_model_free_and_available_without_github_writeback(
    tmp_path: Path,
) -> None:
    app, onboarding = _application(tmp_path)
    with TestClient(app, base_url=ORIGIN) as client:
        _login(client)
        draft = client.post(
            "/api/admin/onboarding/draft",
            headers={"Origin": ORIGIN},
            json={
                "profile": {
                    "display_name": "Example Developer",
                    "headline": {"zh-TW": "可靠系統", "en": "Reliable systems"},
                    "bio": {"zh-TW": "開發者工具", "en": "Developer tooling"},
                    "greeting": {"zh-TW": "你好", "en": "Hello"},
                },
                "repositories": [
                    {
                        "slug": "octocat/demo",
                        "role": {"zh-TW": "共同維護者", "en": "Co-maintainer"},
                        "summary": {
                            "zh-TW": "維護解析器",
                            "en": "Maintained the parser",
                        },
                        "claims": [],
                    }
                ],
                "base_config": _public_config(),
                "confirmed_assertions": True,
            },
        )

    assert draft.status_code == 200
    assert draft.json()["content"].startswith("schema_version: 1")
    assert [name for name, _values in onboarding.calls] == ["draft"]


def test_guided_error_codes_map_to_bounded_http_statuses(tmp_path: Path) -> None:
    app, onboarding = _application(tmp_path)
    with TestClient(app, base_url=ORIGIN) as client:
        _login(client)
        onboarding.failure = GuidedOnboardingError("RATE_LIMITED", retry_after_seconds=17)
        limited = client.post(
            "/api/admin/onboarding/repositories/discover",
            headers={"Origin": ORIGIN},
            json={"account": "octocat", "page": 1},
        )
        onboarding.failure = GuidedOnboardingError("CONFIG_INVALID", reason="NO_ELIGIBLE_CONTENT")
        invalid = client.post(
            "/api/admin/onboarding/repositories/resolve",
            headers={"Origin": ORIGIN},
            json={"repository": "octocat/demo"},
        )

    assert limited.status_code == 429
    assert limited.json()["error"]["retry_after_seconds"] == 17
    assert invalid.status_code == 422
    assert invalid.json()["error"]["details"] == {"reason": "NO_ELIGIBLE_CONTENT"}
