"""Offline reproduction of the acceptance walk's commit-lookup failures."""

from __future__ import annotations

import json
import threading
import time
from dataclasses import replace
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from reponpc.admin.batch_resolver import (
    BatchCapacity,
    GitHubHttpResponse,
    GitHubRateLimiter,
    GitHubRESTMetadataResolver,
)
from reponpc.admin.batches import BatchStageGates
from reponpc.admin.embedding_reindex import EmbeddingReindexCoordinator
from reponpc.admin.local_portfolio import LocalPortfolioStore
from reponpc.admin.local_publication import LocalArchiveResolver, LocalPublication
from tests.integration.test_embedding_reindex import _profile, _system
from tests.integration.test_index_build import FIXTURE_CONFIG
from tests.security.test_admin_assets import ORIGIN, _login, local_admin_application


@pytest.mark.parametrize(
    "status,code", [(409, "GITHUB_ERROR"), (404, "NOT_FOUND"), (500, "GITHUB_ERROR")]
)
def test_commit_lookup_failure_reaches_job_and_status_without_retry(
    tmp_path: Path, status: int, code: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    database, providers, manager, registry, _, transition = _system(tmp_path)
    profile = registry.probe(registry.create(_profile(providers["a"])).profile_id)
    calls: list[str] = []
    phases: dict[str, float] = {}

    class GitHubTransport:
        def request(self, *, method, url, headers, body):
            assert method == "GET" and headers == {} and body is None
            calls.append(url)
            if "/commits/" in url:
                phases["commit_response"] = time.monotonic()
                return GitHubHttpResponse(status, b"{}", {})
            return GitHubHttpResponse(
                200,
                json.dumps(
                    {"id": 1, "private": False, "archived": False, "default_branch": "main"}
                ).encode(),
                {},
            )

    class ArchiveSource:
        def fetch(self, **_kwargs):
            pytest.fail("An unsuccessful commit lookup must not fetch an archive")

    resolver = LocalArchiveResolver(
        GitHubRESTMetadataResolver(transport=GitHubTransport(), limiter=GitHubRateLimiter()),
        ArchiveSource(),
        BatchStageGates(BatchCapacity(1, 1, 1, 1, 1)),
    )
    store = LocalPortfolioStore(tmp_path / "data")
    draft = store.save(
        content=FIXTURE_CONFIG.read_text(encoding="utf-8"),
        sprite_base64=None,
        expected_revision=None,
    )
    coordinator = EmbeddingReindexCoordinator(
        registry=registry,
        manager=manager,
        builder=lambda *_args: pytest.fail("LocalPublication supplies its own builder"),
        provider_transition=transition,
    )
    publication = LocalPublication(
        store=store,
        data_directory=tmp_path / "data",
        coordinator=coordinator,
        registry=registry,
        manager=manager,
        resolver=resolver,
        max_bundle_bytes=10 * 1024 * 1024,
        transition_factory=lambda _chat_id: transition,
        stop_remote=lambda: None,
    )
    finished = threading.Event()
    original_finished = publication._finished

    def record_finished(outcome):
        original_finished(outcome)
        phases["job_failed"] = time.monotonic()
        finished.set()

    monkeypatch.setattr(publication, "_finished", record_finished)
    application = local_admin_application(tmp_path / "admin")
    application.state.admin_operations = replace(
        application.state.admin_operations,
        database=database,
        local_portfolio=store,
        local_publication=publication,
    )
    try:
        with TestClient(application, base_url=ORIGIN) as client:
            _login(client)
            phases["prepare_start"] = time.monotonic()
            publication.prepare(
                expected_revision=draft.revision,
                embedding_profile_id=profile.profile_id,
                chat_profile_id="fixture-chat",
            )
            phases["prepare_return"] = time.monotonic()
            assert finished.wait(5), "Immediate fake HTTP failures must not wait 300 seconds"
            assert publication.status()["state"] == "failed"
            response = client.get("/api/admin/portfolio/status", headers={"Origin": ORIGIN})
            phases["status_reported"] = time.monotonic()
            assert response.status_code == 200
            assert response.json()["state"] == "failed"
            assert response.json()["error_code"] == code
            assert response.json()["retry_at"] is None
            assert response.headers["cache-control"] == "no-store"
            assert len(calls) == 2
            assert sum("/commits/" in url for url in calls) == 1
            assert manager.status().active_bundle_id is None
            assert phases["job_failed"] - phases["commit_response"] < 5
            print(
                json.dumps(
                    {
                        "http_status": status,
                        "error_code": code,
                        "seconds_from_prepare": {
                            name: round(value - phases["prepare_start"], 6)
                            for name, value in phases.items()
                        },
                    },
                    sort_keys=True,
                )
            )
    finally:
        coordinator.shutdown()
