from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from argon2 import PasswordHasher, Type
from fastapi.testclient import TestClient

from reponpc.admin.auth import AdminSessionService
from reponpc.admin.onboarding import GuidedOnboardingError, GuidedOnboardingService
from reponpc.admin.operations import AdminOperations
from reponpc.indexing.github import (
    SourceResolutionError,
    normalize_github_account,
    normalize_github_repository,
)
from reponpc.main import create_app
from reponpc.runtime.database import RuntimeDatabase

ORIGIN = "https://portfolio.example.com"
PASSWORD = "npcx"
CANARY = "CANARY-GITHUB-TOKEN-AND-PROVIDER-BODY"


class BoundaryProbe:
    def __init__(self) -> None:
        self.metadata_calls = 0
        self.source_calls = 0
        self.provider_calls = 0
        self.mutation_calls = 0

    def discover_repositories(self, *, account: str, page: int) -> dict[str, object]:
        del page
        try:
            normalize_github_account(account)
        except SourceResolutionError as exc:
            raise GuidedOnboardingError("VALIDATION_ERROR") from exc
        self.metadata_calls += 1
        return {"repositories": [], "page": 1, "has_more": False}

    def resolve_repository(self, *, repository: str, ref: str | None) -> dict[str, object]:
        del ref
        try:
            normalize_github_repository(repository)
        except SourceResolutionError as exc:
            raise GuidedOnboardingError("VALIDATION_ERROR") from exc
        self.metadata_calls += 1
        return {
            "slug": "octocat/demo",
            "name": "demo",
            "description": None,
            "primary_language": None,
            "default_branch": "main",
            "is_fork": False,
            "is_archived": False,
            "updated_at": None,
            "html_url": "https://github.com/octocat/demo",
            "ref": None,
        }

    def analyze_repository(self, **_values: Any) -> dict[str, object]:
        self.source_calls += 1
        self.provider_calls += 1
        try:
            raise ValueError(CANARY)
        except ValueError as exc:
            raise GuidedOnboardingError("PROVIDER_ERROR") from exc

    def suggest_contributions(self, **_values: Any) -> dict[str, object]:
        self.provider_calls += 1
        raise GuidedOnboardingError("MODEL_UNAVAILABLE")

    def create_draft(self, **_values: Any) -> dict[str, object]:
        return {
            "content": "schema_version: 1\n",
            "validation": {"valid": True, "errors": [], "warnings": []},
        }


def _application(tmp_path: Path) -> tuple[Any, BoundaryProbe]:
    database = RuntimeDatabase(tmp_path)
    database.initialize()
    auth = AdminSessionService(
        database=database,
        username="admin",
        password_hash=PasswordHasher(type=Type.ID).hash(PASSWORD),
        identity_hmac_key=b"s" * 32,
        now=lambda: datetime(2026, 8, 14, tzinfo=UTC),
    )
    probe = BoundaryProbe()
    operations = AdminOperations(
        None,
        database,
        ORIGIN,
        onboarding=cast(GuidedOnboardingService, probe),
    )
    return (
        create_app(
            admin_session_service=auth,
            admin_origins=(ORIGIN,),
            admin_operations=operations,
        ),
        probe,
    )


def _login(client: TestClient) -> str:
    response = client.post(
        "/api/admin/session",
        headers={"Origin": ORIGIN},
        json={"username": "admin", "password": PASSWORD},
    )
    assert response.status_code == 200
    return str(response.json()["csrf_token"])


def test_hostile_repository_inputs_fail_without_source_provider_or_canary_leak(
    tmp_path: Path,
) -> None:
    app, probe = _application(tmp_path)
    hostile = (
        "https://evil.example/octocat",
        "https://github.com/octocat/demo?token=" + CANARY,
        "https://github.com:invalid/octocat/demo",
        "../octocat/demo",
    )
    with TestClient(app, base_url=ORIGIN) as client:
        _login(client)
        responses = [
            client.post(
                "/api/admin/onboarding/repositories/resolve",
                headers={"Origin": ORIGIN},
                json={"repository": value},
            )
            for value in hostile
        ]

    assert all(response.status_code >= 400 for response in responses)
    assert all(CANARY not in response.text for response in responses)
    assert probe.source_calls == probe.provider_calls == probe.mutation_calls == 0


def test_cross_origin_and_csrf_fail_before_onboarding_side_effects(tmp_path: Path) -> None:
    app, probe = _application(tmp_path)
    with TestClient(app, base_url=ORIGIN) as client:
        csrf = _login(client)
        cross_origin = client.post(
            "/api/admin/onboarding/repositories/discover",
            headers={"Origin": "https://evil.example"},
            json={"account": "octocat", "page": 1},
        )
        forged = client.post(
            "/api/admin/onboarding/repositories/analyze",
            headers={"Origin": ORIGIN, "X-CSRF-Token": "forged"},
            json={"slug": "octocat/demo", "ref": None, "include": [], "exclude": []},
        )
        wrong_origin = client.post(
            "/api/admin/onboarding/contributions/suggest",
            headers={
                "Origin": "https://evil.example",
                "X-CSRF-Token": csrf,
            },
            json={"slug": "octocat/demo", "owner_statement": "public statement"},
        )

    assert cross_origin.status_code == forged.status_code == wrong_origin.status_code == 403
    assert probe.metadata_calls == probe.source_calls == probe.provider_calls == 0


def test_provider_failures_are_generic_and_never_return_exception_causes(tmp_path: Path) -> None:
    app, probe = _application(tmp_path)
    with TestClient(app, base_url=ORIGIN) as client:
        csrf = _login(client)
        failed = client.post(
            "/api/admin/onboarding/repositories/analyze",
            headers={"Origin": ORIGIN, "X-CSRF-Token": csrf},
            json={"slug": "octocat/demo", "ref": None, "include": [], "exclude": []},
        )

    assert failed.status_code == 502
    assert failed.json()["error"]["code"] == "PROVIDER_ERROR"
    assert CANARY not in failed.text
    assert "ValueError" not in failed.text
    assert probe.source_calls == probe.provider_calls == 1
    assert probe.mutation_calls == 0


def test_normalizers_map_malformed_ports_to_safe_domain_errors() -> None:
    for operation, value in (
        (normalize_github_account, "https://github.com:invalid/octocat"),
        (normalize_github_repository, "https://github.com:invalid/octocat/demo"),
    ):
        try:
            operation(value)
        except SourceResolutionError as exc:
            assert exc.code.endswith("_invalid")
        else:
            raise AssertionError("malformed port must fail closed")
