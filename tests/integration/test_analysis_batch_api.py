from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from argon2 import PasswordHasher, Type
from fastapi.testclient import TestClient

from reponpc.admin.auth import AdminSessionService
from reponpc.admin.batch_resolver import (
    BatchCapacity,
    BatchPreflightPlanner,
    CredentialPurpose,
    GitHubGraphQLMetadataResolver,
    GitHubHttpResponse,
    GitHubRateLimiter,
    PublicReadCredential,
)
from reponpc.admin.batch_runtime import BatchRuntimeStore
from reponpc.admin.batches import AnalysisBatchService
from reponpc.admin.operations import AdminOperations
from reponpc.main import create_app
from reponpc.runtime.database import RuntimeDatabase

ORIGIN = "https://portfolio.example.com"
PASSWORD = "npcx"
SHA = "a" * 40


class GraphQLTransport:
    def request(self, **_values: object) -> GitHubHttpResponse:
        return GitHubHttpResponse(
            status=200,
            body=json.dumps(
                {
                    "data": {
                        "repo0": {
                            "id": "R_demo",
                            "nameWithOwner": "octocat/demo",
                            "isPrivate": False,
                            "isArchived": False,
                            "defaultBranchRef": {
                                "name": "main",
                                "target": {"oid": SHA},
                            },
                        }
                    }
                }
            ).encode(),
            headers={"X-RateLimit-Remaining": "5000"},
        )


def _application(tmp_path: Path):
    database = RuntimeDatabase(tmp_path / "runtime")
    database.initialize()
    auth = AdminSessionService(
        database=database,
        username="admin",
        password_hash=PasswordHasher(type=Type.ID).hash(PASSWORD),
        identity_hmac_key=b"a" * 32,
        now=lambda: datetime(2026, 8, 16, tzinfo=UTC),
    )
    limiter = GitHubRateLimiter()
    planner = BatchPreflightPlanner(
        resolver=GitHubGraphQLMetadataResolver(
            transport=GraphQLTransport(),  # type: ignore[arg-type]
            limiter=limiter,
        ),
        limiter=limiter,
    )
    batches = AnalysisBatchService(
        store=BatchRuntimeStore(database),
        planner=planner,
        credentials_supplier=lambda: (
            PublicReadCredential(
                credential_id=1,
                purpose=CredentialPurpose.IDENTITY_PUBLIC_READ,
                status="ready",
                token="api-test-token",
            ),
        ),
        mark_connection_required=lambda _credential_id: None,
        provider_ready_supplier=lambda: True,
        capacity=BatchCapacity(1, 1, 2, 1, 4),
        runner=lambda item, _cancelled: {"repository": {"slug": item.input.slug}},
    )
    operations = AdminOperations(
        github=None,
        database=database,
        public_base_url=ORIGIN,
        analysis_batches=batches,
    )
    return create_app(
        admin_session_service=auth,
        admin_origins=(ORIGIN,),
        admin_operations=operations,
    )


def _login(client: TestClient) -> str:
    response = client.post(
        "/api/admin/session",
        headers={"Origin": ORIGIN},
        json={"username": "admin", "password": PASSWORD},
    )
    assert response.status_code == 200
    return str(response.json()["csrf_token"])


def _selection() -> dict[str, object]:
    return {"slug": "octocat/demo", "confirmed": True, "include": [], "exclude": []}


def test_batch_api_requires_csrf_and_replays_safe_snapshot(tmp_path: Path) -> None:
    app = _application(tmp_path)
    with TestClient(app, base_url=ORIGIN) as client:
        csrf = _login(client)
        forbidden = client.post(
            "/api/admin/onboarding/analysis-batches/preflight",
            headers={"Origin": ORIGIN},
            json={"selections": [_selection()]},
        )
        preflight = client.post(
            "/api/admin/onboarding/analysis-batches/preflight",
            headers={"Origin": ORIGIN, "X-CSRF-Token": csrf},
            json={"selections": [_selection()]},
        )
        assert preflight.status_code == 200
        plan = preflight.json()
        created = client.post(
            "/api/admin/onboarding/analysis-batches",
            headers={"Origin": ORIGIN, "X-CSRF-Token": csrf},
            json={
                "plan_id": plan["plan_id"],
                "idempotency_key": "analysis-batch-api-key",
                "selections": [_selection()],
            },
        )
        assert created.status_code == 200
        batch_id = created.json()["batch"]["batch_id"]
        snapshot = client.get(
            f"/api/admin/onboarding/analysis-batches/{batch_id}",
            headers={"Origin": ORIGIN},
        )
        with client.stream(
            "GET",
            f"/api/admin/onboarding/analysis-batches/{batch_id}/events",
            headers={"Origin": ORIGIN},
        ) as events:
            event_body = events.read().decode()

    assert forbidden.status_code == 403
    assert snapshot.status_code == 200
    assert snapshot.headers["cache-control"] == "no-store"
    assert snapshot.json()["items"][0]["commit_sha"] == SHA
    assert "api-test-token" not in snapshot.text
    assert events.status_code == 200
    assert "id: 1" in event_body
    assert "event: batch_created" in event_body
