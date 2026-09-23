from __future__ import annotations

import json
import time
from datetime import UTC, datetime
from pathlib import Path

import pytest
from argon2 import PasswordHasher, Type
from fastapi import FastAPI
from fastapi.testclient import TestClient

from reponpc.admin.auth import AdminSessionService
from reponpc.admin.batch_resolver import (
    BatchCapacity,
    BatchPreflightPlanner,
    GitHubHttpResponse,
    GitHubRateLimiter,
    GitHubRESTMetadataResolver,
)
from reponpc.admin.batch_runtime import BatchCreateRequest, BatchItemInput, BatchRuntimeStore
from reponpc.admin.batches import AnalysisBatchService, BatchExecutionError
from reponpc.admin.operations import AdminOperations
from reponpc.main import create_app
from reponpc.runtime.database import RuntimeDatabase

ORIGIN = "https://portfolio.example.com"
PASSWORD = "npcx"
SHA = "a" * 40


class RESTTransport:
    def request(self, **values: object) -> GitHubHttpResponse:
        url = str(values["url"])
        payload = (
            {"sha": SHA}
            if "/commits/" in url
            else {"id": "R_demo", "private": False, "archived": False, "default_branch": "main"}
        )
        return GitHubHttpResponse(
            status=200,
            body=json.dumps(payload).encode(),
            headers={"X-RateLimit-Resource": "core", "X-RateLimit-Remaining": "60"},
        )


def _application(
    tmp_path: Path,
    *,
    runner=None,
    analysis_generation_attempts: int = 3,
) -> tuple[FastAPI, RuntimeDatabase]:
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
        resolver=GitHubRESTMetadataResolver(
            transport=RESTTransport(),  # type: ignore[arg-type]
            limiter=limiter,
        ),
        limiter=limiter,
        maximum_generation_attempts=analysis_generation_attempts,
    )
    batches = AnalysisBatchService(
        store=BatchRuntimeStore(database),
        planner=planner,
        provider_ready_supplier=lambda: True,
        capacity=BatchCapacity(1, 1, 2, 1, 4),
        runner=runner or (lambda item, _cancelled: {"repository": {"slug": item.input.slug}}),
        analysis_generation_attempts=analysis_generation_attempts,
    )
    operations = AdminOperations(
        github=None,
        database=database,
        public_base_url=ORIGIN,
        analysis_batches=batches,
    )
    return (
        create_app(
            admin_session_service=auth,
            admin_origins=(ORIGIN,),
            admin_operations=operations,
            analysis_batch_service=batches,
        ),
        database,
    )


def _login(client: TestClient) -> str:
    response = client.post(
        "/api/admin/session",
        headers={"Origin": ORIGIN},
        json={"username": "admin", "password": PASSWORD},
    )
    assert response.status_code == 200
    return str(response.json()["csrf_token"])


def _selection(slug: str = "octocat/demo") -> dict[str, object]:
    return {"slug": slug, "confirmed": True, "include": [], "exclude": []}


def test_running_application_cleans_expired_terminal_batches_without_restart(
    tmp_path: Path,
) -> None:
    app, database = _application(tmp_path)
    app.state.analysis_cleanup_seconds = 0.01
    store = BatchRuntimeStore(database)
    expired, _ = store.create_batch(
        BatchCreateRequest(
            plan_id="cleanup-terminal-plan",
            selection_hash="c" * 64,
            idempotency_key="cleanup-terminal-key",
            maximum_generation_attempts=1,
            items=(
                BatchItemInput(
                    slug="octocat/expired",
                    ref="main",
                    include=(),
                    exclude=(),
                    commit_sha=SHA,
                ),
            ),
        )
    )
    claimed = store.claim_next_item(expired.batch_id)
    assert claimed is not None
    store.fail_item(claimed, code="PROVIDER_ERROR")
    active, _ = store.create_batch(
        BatchCreateRequest(
            plan_id="cleanup-active-plan",
            selection_hash="d" * 64,
            idempotency_key="cleanup-active-key",
            items=(
                BatchItemInput(
                    slug="octocat/active",
                    ref="main",
                    include=(),
                    exclude=(),
                    commit_sha="b" * 40,
                ),
            ),
        )
    )

    with TestClient(app, base_url=ORIGIN):
        with database.connection() as connection:
            connection.execute(
                "UPDATE analysis_batches SET expires_at = ? WHERE batch_id = ?",
                ("2026-01-01T00:00:00+00:00", expired.batch_id),
            )
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline:
            with database.connection() as connection:
                remaining = connection.execute(
                    "SELECT COUNT(*) FROM analysis_batches WHERE batch_id = ?",
                    (expired.batch_id,),
                ).fetchone()[0]
            if remaining == 0:
                break
            time.sleep(0.01)

    with database.connection() as connection:
        expired_batches = connection.execute(
            "SELECT COUNT(*) FROM analysis_batches WHERE batch_id = ?",
            (expired.batch_id,),
        ).fetchone()[0]
        expired_events = connection.execute(
            "SELECT COUNT(*) FROM analysis_batch_events WHERE batch_id = ?",
            (expired.batch_id,),
        ).fetchone()[0]
        active_batches = connection.execute(
            "SELECT COUNT(*) FROM analysis_batches WHERE batch_id = ?",
            (active.batch_id,),
        ).fetchone()[0]
    assert expired_batches == 0
    assert expired_events == 0
    assert active_batches == 1


def test_batch_api_requires_csrf_and_replays_safe_snapshot(tmp_path: Path) -> None:
    app, _database = _application(tmp_path)
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
    assert snapshot.json()["maximum_generation_attempts"] == 3
    assert snapshot.json()["recovery_maximum_generation_attempts"] == 3
    assert snapshot.json()["items"][0]["commit_sha"] == SHA
    assert snapshot.json()["items"][0]["execution_budget_seconds"] == 1800
    assert snapshot.json()["items"][0]["recovery_execution_budget_seconds"] == 1800
    assert "api-test-token" not in snapshot.text
    assert events.status_code == 200
    assert "id: 1" in event_body
    assert "event: batch_created" in event_body


def test_legacy_analysis_is_projected_from_the_durable_batch_event_store(
    tmp_path: Path,
) -> None:
    app, database = _application(tmp_path)
    with TestClient(app, base_url=ORIGIN) as client:
        csrf = _login(client)
        legacy = client.post(
            "/api/admin/onboarding/repositories/analyze",
            headers={"Origin": ORIGIN, "X-CSRF-Token": csrf},
            json={
                "slug": "octocat/demo",
                "ref": None,
                "include": [],
                "exclude": [],
            },
        )
        assert legacy.status_code == 200, legacy.text
        with database.connection() as connection:
            row = connection.execute(
                "SELECT batch_id FROM analysis_batches ORDER BY created_at DESC LIMIT 1"
            ).fetchone()
        assert row is not None
        batch_id = str(row["batch_id"])
        snapshot_response = client.get(
            f"/api/admin/onboarding/analysis-batches/{batch_id}",
            headers={"Origin": ORIGIN},
        )
        with client.stream(
            "GET",
            f"/api/admin/onboarding/analysis-batches/{batch_id}/events",
            headers={"Origin": ORIGIN},
        ) as event_stream:
            event_body = event_stream.read().decode()

    assert legacy.json()["repository"]["slug"] == "octocat/demo"
    assert snapshot_response.status_code == 200
    snapshot = snapshot_response.json()
    assert snapshot["state"] == "completed"
    assert len(snapshot["items"]) == 1
    assert snapshot["items"][0]["slug"] == "octocat/demo"
    assert event_stream.status_code == 200
    assert "event: batch_created" in event_body
    assert "event: item_terminal" in event_body


@pytest.mark.parametrize(
    "reason", ["PROVIDER_OUTPUT_SCHEMA_INVALID", "PROVIDER_OUTPUT_LIMIT_REACHED"]
)
def test_batch_snapshot_and_events_expose_only_allowlisted_failure_reason(
    tmp_path: Path, reason: str
) -> None:
    def fail_analysis(_item, _cancelled):
        raise BatchExecutionError(
            "PROVIDER_ERROR",
            reason=reason,
        )

    app, _database = _application(tmp_path, runner=fail_analysis)
    with TestClient(app, base_url=ORIGIN) as client:
        csrf = _login(client)
        preflight = client.post(
            "/api/admin/onboarding/analysis-batches/preflight",
            headers={"Origin": ORIGIN, "X-CSRF-Token": csrf},
            json={"selections": [_selection()]},
        )
        created = client.post(
            "/api/admin/onboarding/analysis-batches",
            headers={"Origin": ORIGIN, "X-CSRF-Token": csrf},
            json={
                "plan_id": preflight.json()["plan_id"],
                "idempotency_key": "analysis-batch-safe-error",
                "selections": [_selection()],
            },
        )
        batch_id = created.json()["batch"]["batch_id"]
        for _attempt in range(100):
            snapshot = client.get(
                f"/api/admin/onboarding/analysis-batches/{batch_id}",
                headers={"Origin": ORIGIN},
            )
            if snapshot.json()["state"] == "failed":
                break
            time.sleep(0.01)
        with client.stream(
            "GET",
            f"/api/admin/onboarding/analysis-batches/{batch_id}/events",
            headers={"Origin": ORIGIN},
        ) as events:
            event_body = events.read().decode()

    assert snapshot.status_code == 200
    assert snapshot.json()["items"][0]["error_code"] == "PROVIDER_ERROR"
    assert snapshot.json()["items"][0]["error_reason"] == reason
    assert reason in event_body
    assert "provider response body" not in snapshot.text


def test_reanalysis_endpoint_creates_idempotent_successor_and_preserves_source(
    tmp_path: Path,
) -> None:
    def fail_analysis(_item, _cancelled):
        raise BatchExecutionError("PROVIDER_ERROR")

    app, database = _application(
        tmp_path,
        runner=fail_analysis,
        analysis_generation_attempts=1,
    )
    with TestClient(app, base_url=ORIGIN) as client:
        csrf = _login(client)
        preflight = client.post(
            "/api/admin/onboarding/analysis-batches/preflight",
            headers={"Origin": ORIGIN, "X-CSRF-Token": csrf},
            json={"selections": [_selection()]},
        )
        created = client.post(
            "/api/admin/onboarding/analysis-batches",
            headers={"Origin": ORIGIN, "X-CSRF-Token": csrf},
            json={
                "plan_id": preflight.json()["plan_id"],
                "idempotency_key": "analysis-source-failure-key",
                "selections": [_selection()],
            },
        )
        source_batch_id = created.json()["batch"]["batch_id"]
        for _attempt in range(100):
            source = client.get(
                f"/api/admin/onboarding/analysis-batches/{source_batch_id}",
                headers={"Origin": ORIGIN},
            )
            if source.json()["state"] == "failed":
                break
            time.sleep(0.01)
        source_item_id = source.json()["items"][0]["item_id"]
        with database.connection() as connection:
            connection.execute(
                "UPDATE analysis_batch_items SET generation_attempt_count = 1 WHERE item_id = ?",
                (source_item_id,),
            )

        exhausted = client.get(
            f"/api/admin/onboarding/analysis-batches/{source_batch_id}",
            headers={"Origin": ORIGIN},
        )
        forbidden = client.post(
            f"/api/admin/onboarding/analysis-batches/{source_batch_id}/reanalyze",
            headers={"Origin": ORIGIN},
            json={
                "item_ids": [source_item_id],
                "idempotency_key": "successor-analysis-key",
            },
        )
        payload = {
            "item_ids": [source_item_id],
            "idempotency_key": "successor-analysis-key",
            "model_selection": "frozen",
            "confirm_model_change": False,
        }
        successor = client.post(
            f"/api/admin/onboarding/analysis-batches/{source_batch_id}/reanalyze",
            headers={"Origin": ORIGIN, "X-CSRF-Token": csrf},
            json=payload,
        )
        repeated = client.post(
            f"/api/admin/onboarding/analysis-batches/{source_batch_id}/reanalyze",
            headers={"Origin": ORIGIN, "X-CSRF-Token": csrf},
            json=payload,
        )

    assert exhausted.status_code == 200
    exhausted_item = exhausted.json()["items"][0]
    assert exhausted_item["retryable"] is False
    assert exhausted_item["reanalyzable"] is True
    assert exhausted_item["retry_blocker"] == "ATTEMPTS_EXHAUSTED"
    assert forbidden.status_code == 403
    assert successor.status_code == 200, successor.text
    assert repeated.status_code == 200, repeated.text
    successor_body = successor.json()
    assert successor_body["created"] is True
    assert repeated.json()["created"] is False
    assert repeated.json()["batch"]["batch_id"] == successor_body["batch"]["batch_id"]
    assert successor_body["batch"]["source_batch_id"] == source_batch_id
    assert successor_body["batch"]["analysis_round"] == 2
    assert successor_body["batch"]["items"][0]["source_item_id"] == source_item_id
    assert successor_body["batch"]["items"][0]["commit_sha"] == SHA
    assert exhausted.json()["items"][0]["error_code"] == "PROVIDER_ERROR"


def test_partial_batch_recovers_only_failed_item_and_preserves_successes(
    tmp_path: Path,
) -> None:
    calls: dict[str, int] = {}

    def mixed_analysis(item, _cancelled):
        slug = item.input.slug
        calls[slug] = calls.get(slug, 0) + 1
        if slug == "octocat/fails-once" and calls[slug] == 1:
            raise BatchExecutionError("PROVIDER_ERROR")
        evidence_id = f"fact-{slug.rsplit('/', 1)[-1]}"
        return {
            "repository": {
                "slug": slug,
                "commit_sha": item.input.commit_sha,
                "default_branch": "main",
                "html_url": f"https://github.com/{slug}",
            },
            "facts": [
                {
                    "evidence_class": "REPOSITORY_FACT",
                    "evidence_id": evidence_id,
                    "path": "src/main.py",
                    "start_line": 1,
                    "end_line": 2,
                    "excerpt": f"validated excerpt for {slug}",
                }
            ],
            "inferences": [
                {
                    "evidence_class": "MODEL_INFERENCE",
                    "statement": {"zh-TW": f"推論 {slug}", "en": f"Inference {slug}"},
                    "supporting_evidence_ids": [evidence_id],
                }
            ],
            "skipped_summary": {"count": 0, "reasons": []},
        }

    app, database = _application(
        tmp_path,
        runner=mixed_analysis,
        analysis_generation_attempts=1,
    )
    selections = [
        _selection("octocat/one"),
        _selection("octocat/fails-once"),
        _selection("octocat/two"),
    ]
    with TestClient(app, base_url=ORIGIN) as client:
        csrf = _login(client)
        headers = {"Origin": ORIGIN, "X-CSRF-Token": csrf}
        preflight = client.post(
            "/api/admin/onboarding/analysis-batches/preflight",
            headers=headers,
            json={"selections": selections},
        )
        created = client.post(
            "/api/admin/onboarding/analysis-batches",
            headers=headers,
            json={
                "plan_id": preflight.json()["plan_id"],
                "idempotency_key": "partial-source-batch-key",
                "selections": selections,
            },
        )
        source_batch_id = created.json()["batch"]["batch_id"]
        for _attempt in range(200):
            source_response = client.get(
                f"/api/admin/onboarding/analysis-batches/{source_batch_id}",
                headers={"Origin": ORIGIN},
            )
            if source_response.json()["state"] == "completed_with_errors":
                break
            time.sleep(0.01)

        source = source_response.json()
        failed = next(item for item in source["items"] if item["state"] == "failed")
        succeeded = [item for item in source["items"] if item["state"] == "complete"]
        # The lightweight fake runner bypasses the production runner's atomic
        # generation reservation, so mirror its one consumed dispatch here.
        with database.connection() as connection:
            connection.execute(
                "UPDATE analysis_batch_items SET generation_attempt_count = 1 WHERE item_id = ?",
                (failed["item_id"],),
            )
        exhausted_response = client.get(
            f"/api/admin/onboarding/analysis-batches/{source_batch_id}",
            headers={"Origin": ORIGIN},
        )
        failed = next(
            item
            for item in exhausted_response.json()["items"]
            if item["item_id"] == failed["item_id"]
        )
        successor_payload = {
            "item_ids": [failed["item_id"]],
            "idempotency_key": "partial-successor-key",
            "model_selection": "frozen",
            "confirm_model_change": False,
        }
        successor_response = client.post(
            f"/api/admin/onboarding/analysis-batches/{source_batch_id}/reanalyze",
            headers=headers,
            json=successor_payload,
        )
        repeated_response = client.post(
            f"/api/admin/onboarding/analysis-batches/{source_batch_id}/reanalyze",
            headers=headers,
            json=successor_payload,
        )
        conflicting_response = client.post(
            f"/api/admin/onboarding/analysis-batches/{source_batch_id}/reanalyze",
            headers=headers,
            json={**successor_payload, "idempotency_key": "partial-successor-other-key"},
        )
        successor_batch_id = successor_response.json()["batch"]["batch_id"]
        for _attempt in range(200):
            successor_snapshot_response = client.get(
                f"/api/admin/onboarding/analysis-batches/{successor_batch_id}",
                headers={"Origin": ORIGIN},
            )
            if successor_snapshot_response.json()["state"] == "completed":
                break
            time.sleep(0.01)
        source_after = client.get(
            f"/api/admin/onboarding/analysis-batches/{source_batch_id}",
            headers={"Origin": ORIGIN},
        ).json()

    assert len(succeeded) == 2
    assert {item["result"]["facts"][0]["excerpt"] for item in succeeded} == {
        "validated excerpt for octocat/one",
        "validated excerpt for octocat/two",
    }
    assert failed["retryable"] is False
    assert failed["reanalyzable"] is True
    assert successor_response.status_code == 200, successor_response.text
    assert successor_response.json()["created"] is True
    assert repeated_response.status_code == 200, repeated_response.text
    assert repeated_response.json()["created"] is False
    assert repeated_response.json()["batch"]["batch_id"] == successor_batch_id
    assert conflicting_response.status_code == 200, conflicting_response.text
    assert conflicting_response.json()["created"] is False
    assert conflicting_response.json()["batch"]["batch_id"] == successor_batch_id
    successor_snapshot = successor_snapshot_response.json()
    assert successor_snapshot["state"] == "completed"
    assert len(successor_snapshot["items"]) == 1
    assert successor_snapshot["items"][0]["slug"] == "octocat/fails-once"
    assert successor_snapshot["items"][0]["source_item_id"] == failed["item_id"]
    assert successor_snapshot["items"][0]["result"]["facts"][0]["excerpt"] == (
        "validated excerpt for octocat/fails-once"
    )
    assert [item["result"] for item in source_after["items"] if item["state"] == "complete"] == [
        item["result"] for item in succeeded
    ]
    source_failed_after = next(
        item for item in source_after["items"] if item["item_id"] == failed["item_id"]
    )
    assert source_failed_after["state"] == "failed"
    assert source_failed_after["retryable"] is False
    assert source_failed_after["reanalyzable"] is False
    assert source_failed_after["retry_blocker"] == "SUCCESSOR_EXISTS"
    assert calls == {
        "octocat/one": 1,
        "octocat/fails-once": 2,
        "octocat/two": 1,
    }
