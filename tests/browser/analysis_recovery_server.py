"""Isolated production-stack server for the R01-R04/R07 browser acceptance.

The application serves the built React application and the real FastAPI batch
routes.  The batch planner, archive parser, index builder, validation, durable
store, worker, and runner are production objects.  Only the external GitHub
and model-provider transports are deterministic test doubles.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import shutil
import tarfile
import threading
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np
import uvicorn
from starlette.responses import JSONResponse

from reponpc.admin.analysis_selection import AnalysisSelectionRegistry
from reponpc.admin.auth import AdminSessionService, issue_admin_local_launch_grant
from reponpc.admin.batch_execution import PinnedBatchItemRunner
from reponpc.admin.batch_resolver import (
    ArchiveSafetyLimits,
    BatchCapacity,
    BatchPreflightPlanner,
    GitHubArchiveSource,
    GitHubHttpResponse,
    GitHubRateLimiter,
    GitHubRESTMetadataResolver,
)
from reponpc.admin.batch_runtime import BatchRuntimeStore
from reponpc.admin.batches import AnalysisBatchService, BatchStageGates
from reponpc.admin.chat_profiles import ChatProfileInput, ChatProfileRegistry
from reponpc.admin.embedding_profiles import EmbeddingProfileInput, EmbeddingProfileRegistry
from reponpc.admin.model_connections import (
    ModelConnectionInput,
    ModelConnectionRegistry,
    ProtectedModelSecretStore,
)
from reponpc.admin.onboarding import GuidedOnboardingService
from reponpc.admin.operations import AdminOperations
from reponpc.chat.limits import ChatLimits
from reponpc.indexing.github import PublicRepositoryMetadata, RepositoryDiscoveryPage
from reponpc.indexing.sources import EmbeddingIdentity
from reponpc.main import create_app
from reponpc.providers.contracts import (
    ProviderCapabilities,
    ProviderError,
    ProviderFailureCode,
    ProviderHealth,
    ProviderResult,
)
from reponpc.providers.runtime import ProviderRuntime
from reponpc.runtime.database import RuntimeDatabase

SLUGS = ("fixture/alpha", "fixture/beta", "fixture/fails-once")


def _sha(slug: str) -> str:
    return hashlib.sha256(slug.encode()).hexdigest()[:40]


class FixtureRESTTransport:
    def request(self, **values: object) -> GitHubHttpResponse:
        url = str(values["url"])
        slug = next((value for value in SLUGS if f"/repos/{value}" in url), None)
        if slug is None:
            return GitHubHttpResponse(404, b"{}", {})
        payload: dict[str, object]
        if "/commits/" in url:
            payload = {"sha": _sha(slug)}
        else:
            payload = {
                "id": f"R_{slug.rsplit('/', 1)[-1]}",
                "private": False,
                "archived": False,
                "default_branch": "main",
            }
        return GitHubHttpResponse(
            200,
            json.dumps(payload).encode(),
            {"X-RateLimit-Resource": "core", "X-RateLimit-Remaining": "500"},
        )


class FixtureArchiveTransport:
    def __init__(self) -> None:
        self.calls: dict[str, int] = {}

    def stream(self, **values: object):
        repository = values["repository"]
        slug = str(repository.slug)
        self.calls[slug] = self.calls.get(slug, 0) + 1
        source = (
            f"def repository_name():\n"
            f"    return {slug!r}\n\n"
            "def validated_path():\n"
            "    return 'production runner and validator'\n"
        ).encode()
        root = f"{slug.rsplit('/', 1)[-1]}-{repository.commit_sha}"
        output = io.BytesIO()
        with tarfile.open(fileobj=output, mode="w:gz") as archive:
            info = tarfile.TarInfo(f"{root}/src/main.py")
            info.size = len(source)
            archive.addfile(info, io.BytesIO(source))
        yield output.getvalue()


class FixtureSourceResolver:
    def discover(self, *, account: str, page: int) -> RepositoryDiscoveryPage:
        if account != "fixture":
            return RepositoryDiscoveryPage((), page, False)
        return RepositoryDiscoveryPage(
            tuple(self.repository_metadata(repository=slug) for slug in SLUGS),
            page,
            False,
        )

    def repository_metadata(self, *, repository: str) -> PublicRepositoryMetadata:
        if repository not in SLUGS:
            raise ValueError("unknown fixture repository")
        name = repository.rsplit("/", 1)[-1]
        return PublicRepositoryMetadata(
            slug=repository,
            name=name,
            description=f"Browser acceptance {name}",
            primary_language="Python",
            default_branch="main",
            is_fork=False,
            is_archived=False,
            updated_at="2026-09-17T00:00:00Z",
            html_url=f"https://github.com/{repository}",
        )


class FixtureEmbedding:
    def identity(self) -> EmbeddingIdentity:
        return EmbeddingIdentity(
            "openai_compatible",
            "browser-embedding",
            3,
            True,
            "query: ",
            "passage: ",
        )

    def embed_query(self, texts: list[str]) -> np.ndarray:
        return np.tile(np.asarray([[1.0, 0.0, 0.0]], dtype=np.float32), (len(texts), 1))

    def embed_passages(self, texts: list[str]) -> np.ndarray:
        return np.tile(np.asarray([[1.0, 0.0, 0.0]], dtype=np.float32), (len(texts), 1))

    def health(self) -> ProviderHealth:
        return ProviderHealth(True, "2026-09-17T00:00:00Z")


class FixtureChatController:
    def __init__(self) -> None:
        self.calls: Counter[tuple[str, str]] = Counter()
        self.contribution_calls = 0
        self.contribution_requests: list[dict[str, object]] = []
        self.contribution_context_tokens = 8192
        self.contribution_release = threading.Event()
        self.retry_release = threading.Event()
        self._lock = threading.Lock()


class FixtureChat:
    def __init__(self, controller: FixtureChatController, model_id: str) -> None:
        self.controller = controller
        self.model_id = model_id

    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            False,
            True,
            True,
            True,
            True,
            self.controller.contribution_context_tokens,
            min(self.controller.contribution_context_tokens, 1000),
        )

    def generate(self, messages, response_schema, max_output_tokens, timeout):
        del timeout
        prompt = messages[-1].content
        if 'Reply only with JSON: {"ok":true}.' in prompt:
            return ProviderResult({"ok": True}, "stop", None, None, 1.0)
        if "[UNTRUSTED OWNER DRAFT]" in prompt:
            with self.controller._lock:
                self.controller.contribution_calls += 1
                self.controller.contribution_requests.append(
                    {
                        "max_output_tokens": max_output_tokens,
                        "schema_required": response_schema.get("required"),
                        "schema_closed": response_schema.get("additionalProperties") is False,
                    }
                )
            proposal: dict[str, object] = {
                "role": {"zh-TW": "共同維護者", "en": "Co-maintainer"},
                "summary": {
                    "zh-TW": "協助建立 alpha 驗收流程",
                    "en": "Assisted with the alpha acceptance flow",
                },
                "claims": [],
            }
            if "DELAY_BROWSER_CONTRIBUTION" in prompt:
                self.controller.contribution_release.wait(timeout=30)
            if "INVALID_BROWSER_CONTRIBUTION" in prompt:
                proposal["unexpected"] = "must be rejected"
            return ProviderResult(
                proposal,
                "length" if "TRUNCATE_BROWSER_CONTRIBUTION" in prompt else "stop",
                None,
                None,
                1.0,
            )
        slug = next(value for value in SLUGS if value in prompt)
        with self.controller._lock:
            self.controller.calls[(self.model_id, slug)] += 1
            slug_call = sum(
                count
                for (model, called_slug), count in self.controller.calls.items()
                if called_slug == slug and model == "browser-chat-a"
            )
        if slug == "fixture/fails-once" and self.model_id == "browser-chat-a":
            if slug_call == 2:
                self.controller.retry_release.wait(timeout=30)
            if slug_call <= 2:
                raise ProviderError(ProviderFailureCode.INVALID_RESPONSE)
        evidence_ids = re.findall(r"persistent_id=(E_[0-9a-f]+)", prompt)
        if not evidence_ids:
            raise ProviderError(ProviderFailureCode.INVALID_RESPONSE)
        return ProviderResult(
            {
                "inferences": [
                    {
                        "statement": {
                            "zh-TW": f"已驗證 {slug} 的正式分析路徑",
                            "en": f"Validated production analysis path for {slug}",
                        },
                        "supporting_evidence_ids": [evidence_ids[0]],
                    }
                ]
            },
            "stop",
            None,
            None,
            1.0,
        )

    def health(self) -> ProviderHealth:
        return ProviderHealth(True, "2026-09-17T00:00:00Z")


class BrowserAcceptanceApp:
    """Safe test-only observations and controls around the production ASGI app."""

    def __init__(
        self,
        application: Any,
        *,
        database: RuntimeDatabase,
        batches: AnalysisBatchService,
        selection: AnalysisSelectionRegistry,
        alternate_chat_profile_id: str,
        embedding_profile_id: str,
        chat_controller: FixtureChatController,
        archive_calls: dict[str, int],
    ) -> None:
        self.application = application
        self.database = database
        self.batches = batches
        self.selection = selection
        self.alternate_chat_profile_id = alternate_chat_profile_id
        self.embedding_profile_id = embedding_profile_id
        self.chat_controller = chat_controller
        self.archive_calls = archive_calls
        self.discarded: Counter[str] = Counter()
        self.requests: list[dict[str, object]] = []
        self.second_key_result: dict[str, object] | None = None

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        if scope["type"] != "http":
            await self.application(scope, receive, send)
            return
        path = str(scope["path"])
        method = str(scope["method"])
        if path == "/__browser-test/state":
            await JSONResponse(self._state())(scope, receive, send)
            return
        if method == "POST" and path.startswith("/__browser-test/discarded/"):
            self.discarded[path.rsplit("/", 1)[-1]] += 1
            await JSONResponse({"ok": True})(scope, receive, send)
            return
        if method == "POST" and path == "/__browser-test/release-retry":
            self.chat_controller.retry_release.set()
            await JSONResponse({"ok": True})(scope, receive, send)
            return
        if method == "POST" and path == "/__browser-test/release-contribution":
            self.chat_controller.contribution_release.set()
            await JSONResponse({"ok": True})(scope, receive, send)
            return
        if method == "POST" and path == "/__browser-test/contribution-context-small":
            self.chat_controller.contribution_context_tokens = 800
            await JSONResponse({"ok": True})(scope, receive, send)
            return
        if method == "POST" and path == "/__browser-test/contribution-context-normal":
            self.chat_controller.contribution_context_tokens = 8192
            await JSONResponse({"ok": True})(scope, receive, send)
            return
        if method == "POST" and path == "/__browser-test/select-alternate":
            before = self.selection.current().generation
            view = self.selection.select(
                chat_profile_id=self.alternate_chat_profile_id,
                embedding_profile_id=self.embedding_profile_id,
                expected_generation=before,
            )
            await JSONResponse({"generation": view.selection.generation})(scope, receive, send)
            return
        if method == "POST" and path == "/__browser-test/second-key":
            with self.database.connection() as connection:
                row = connection.execute(
                    """
                    SELECT source.batch_id, item.item_id
                    FROM analysis_batches AS source
                    JOIN analysis_batch_items AS item ON item.batch_id = source.batch_id
                    WHERE source.source_batch_id IS NULL
                      AND item.repository_slug = 'fixture/fails-once'
                    ORDER BY source.created_at LIMIT 1
                    """
                ).fetchone()
            if row is None:
                await JSONResponse({"error": "source_not_found"}, status_code=409)(
                    scope, receive, send
                )
                return
            generation = self.selection.current().generation
            snapshot, created = self.batches.reanalyze(
                str(row["batch_id"]),
                item_ids=(str(row["item_id"]),),
                idempotency_key="browser-equivalent-second-key",
                model_selection="current",
                confirm_model_change=True,
                expected_selection_generation=generation,
            )
            self.second_key_result = {"batch_id": snapshot.batch_id, "created": created}
            await JSONResponse(self.second_key_result)(scope, receive, send)
            return
        if method == "POST" and re.search(r"/analysis-batches/[^/]+/retry$", path):
            self.requests.append({"operation": "retry", "path": path})
        if method == "POST" and re.search(r"/analysis-batches/[^/]+/reanalyze$", path):
            chunks: list[bytes] = []
            more = True
            while more:
                message = await receive()
                chunks.append(message.get("body", b""))
                more = bool(message.get("more_body", False))
            body = b"".join(chunks)
            try:
                payload = json.loads(body)
            except (TypeError, ValueError):
                payload = {}
            key = str(payload.get("idempotency_key", ""))
            self.requests.append(
                {
                    "operation": "reanalyze",
                    "path": path,
                    "idempotency_key_sha256": hashlib.sha256(key.encode()).hexdigest(),
                    "model_selection": payload.get("model_selection"),
                    "confirm_model_change": payload.get("confirm_model_change"),
                    "expected_selection_generation": payload.get("expected_selection_generation"),
                }
            )
            delivered = False

            async def replay() -> dict[str, object]:
                nonlocal delivered
                if delivered:
                    return {"type": "http.request", "body": b"", "more_body": False}
                delivered = True
                return {"type": "http.request", "body": body, "more_body": False}

            await self.application(scope, replay, send)
            return
        await self.application(scope, receive, send)

    def _state(self) -> dict[str, object]:
        with self.database.connection() as connection:
            batches = [
                dict(row)
                for row in connection.execute(
                    "SELECT batch_id, source_batch_id, analysis_round, state, completed_at, "
                    "analysis_model_pair_json "
                    "FROM analysis_batches ORDER BY created_at"
                ).fetchall()
            ]
            items = [
                dict(row)
                for row in connection.execute(
                    "SELECT item_id, batch_id, repository_slug, resolved_commit_sha, state, "
                    "generation_attempt_count, execution_elapsed_seconds, source_item_id, "
                    "successor_batch_id "
                    "FROM analysis_batch_items ORDER BY created_at, position"
                ).fetchall()
            ]
            receipts = [
                dict(row)
                for row in connection.execute(
                    "SELECT idempotency_key_hash, request_hash, batch_id FROM "
                    "analysis_batch_idempotency_receipts ORDER BY created_at"
                ).fetchall()
            ]
        for batch in batches:
            raw = batch.pop("analysis_model_pair_json", None)
            batch["analysis_model_pair"] = json.loads(raw) if raw else None
        calls = {
            f"{model}|{slug}": count
            for (model, slug), count in sorted(self.chat_controller.calls.items())
        }
        return {
            "batches": batches,
            "items": items,
            "receipts": receipts,
            "reanalyze_requests": self.requests,
            "provider_calls": calls,
            "contribution_calls": self.chat_controller.contribution_calls,
            "contribution_requests": self.chat_controller.contribution_requests,
            "archive_calls": dict(sorted(self.archive_calls.items())),
            "discarded": dict(self.discarded),
            "selection_generation": self.selection.current().generation,
            "second_key_result": self.second_key_result,
        }


def build_application(runtime_root: Path, web_dist: Path, origin: str):
    isolated_web_dist = runtime_root / "web-dist"
    shutil.copytree(web_dist, isolated_web_dist)
    index_path = isolated_web_dist / "index.html"
    index_path.write_text(
        index_path.read_text(encoding="utf-8").replace(
            "<head>", '<head><script src="/browser-acceptance.js"></script>', 1
        ),
        encoding="utf-8",
    )
    (isolated_web_dist / "browser-acceptance.js").write_text(
        r"""
navigator.serviceWorker.register('/browser-fault-sw.js').then(async () => {
  await navigator.serviceWorker.ready;
  if (!navigator.serviceWorker.controller) {
    await new Promise((resolve) => {
      const timeout = setTimeout(resolve, 2000);
      navigator.serviceWorker.addEventListener('controllerchange', () => {
        clearTimeout(timeout);
        resolve();
      }, {once: true});
    });
  }
  if (navigator.serviceWorker.controller) {
    document.documentElement.dataset.browserFaultReady = 'true';
  }
});
document.documentElement.dataset.browserUserAgent = navigator.userAgent;
window.__browserConfirmMode = 'accept';
window.__browserConfirmMessages = [];
window.confirm = (message) => {
  window.__browserConfirmMessages.push(String(message));
  document.querySelector('[data-browser-confirm-messages]').textContent =
    JSON.stringify(window.__browserConfirmMessages, null, 2);
  return window.__browserConfirmMode === 'accept';
};
window.addEventListener('DOMContentLoaded', () => {
  const controls = document.createElement('section');
  controls.setAttribute('aria-label', 'Browser acceptance controls');
  controls.innerHTML = `
    <details open><summary>Browser acceptance observations</summary>
      <button type="button" data-test-action="refresh">Refresh acceptance state</button>
      <button type="button" data-test-action="capture-batch">
        Capture production batch snapshot
      </button>
      <button type="button" data-test-action="start-status-observer">
        Start batch status observation
      </button>
      <button type="button" data-test-action="stop-status-observer">
        Stop batch status observation
      </button>
      <button type="button" data-test-action="release">Release retry provider</button>
      <button type="button" data-test-action="release-contribution">
        Release contribution provider
      </button>
      <button type="button" data-test-action="context-small">
        Use small contribution context
      </button>
      <button type="button" data-test-action="context-normal">
        Restore contribution context
      </button>
      <button type="button" data-test-action="arm-stale">
        Arm stale batch request
      </button>
      <button type="button" data-test-action="release-stale">
        Release held batch response
      </button>
      <button type="button" data-test-action="alternate">
        Simulate second-tab model selection
      </button>
      <button type="button" data-test-action="second-key">Submit equivalent second key</button>
      <button type="button" data-test-action="cancel-confirm">
        Cancel next model confirmation
      </button>
      <button type="button" data-test-action="accept-confirm">Accept model confirmation</button>
      <pre aria-label="Browser acceptance state" data-browser-state>{}</pre>
      <pre aria-label="Production batch snapshots" data-browser-batch-snapshots>[]</pre>
      <pre aria-label="Batch status transitions" data-browser-status-transitions>[]</pre>
      <pre aria-label="Model confirmation messages" data-browser-confirm-messages>[]</pre>
    </details>`;
  document.body.append(controls);
  const action = async (name, path) => {
    await fetch(path, {method: 'POST'});
    if (name !== 'release') await refresh();
  };
  const refresh = async () => {
    const response = await fetch('/__browser-test/state');
    controls.querySelector('[data-browser-state]').textContent =
      JSON.stringify(await response.json(), null, 2);
    controls.dataset.stateVersion = String(
      Number(controls.dataset.stateVersion || '0') + 1
    );
  };
  const captureBatchSnapshot = async () => {
    const stateResponse = await fetch('/__browser-test/state');
    const state = await stateResponse.json();
    const source = state.batches.find((batch) => batch.source_batch_id === null);
    const path = `/api/admin/onboarding/analysis-batches/${encodeURIComponent(source.batch_id)}`;
    const response = await fetch(path);
    const snapshots = JSON.parse(
      controls.querySelector('[data-browser-batch-snapshots]').textContent
    );
    snapshots.push({path, status: response.status, body: await response.json()});
    controls.querySelector('[data-browser-batch-snapshots]').textContent =
      JSON.stringify(snapshots, null, 2);
  };
  let batchStatusObserver = null;
  const readBatchStatus = () =>
    document.querySelector('section[data-batch-status]')?.dataset?.batchStatus ?? null;
  const recordBatchStatus = () => {
    const output = controls.querySelector('[data-browser-status-transitions]');
    const transitions = JSON.parse(output.textContent);
    const status = readBatchStatus();
    if (transitions[transitions.length - 1] !== status) {
      transitions.push(status);
      output.textContent = JSON.stringify(transitions, null, 2);
    }
  };
  const startBatchStatusObservation = () => {
    batchStatusObserver?.disconnect();
    controls.querySelector('[data-browser-status-transitions]').textContent =
      JSON.stringify([readBatchStatus()], null, 2);
    batchStatusObserver = new MutationObserver(recordBatchStatus);
    batchStatusObserver.observe(document.body, {
      attributes: true,
      attributeFilter: ['data-batch-status'],
      childList: true,
      subtree: true,
    });
  };
  controls.addEventListener('click', (event) => {
    const name = event.target?.dataset?.testAction;
    if (name === 'refresh') void refresh();
    if (name === 'capture-batch') void captureBatchSnapshot();
    if (name === 'start-status-observer') startBatchStatusObservation();
    if (name === 'stop-status-observer') batchStatusObserver?.disconnect();
    if (name === 'release') void action(name, '/__browser-test/release-retry');
    if (name === 'release-contribution') {
      void action(name, '/__browser-test/release-contribution');
    }
    if (name === 'context-small') {
      void action(name, '/__browser-test/contribution-context-small');
    }
    if (name === 'context-normal') {
      void action(name, '/__browser-test/contribution-context-normal');
    }
    if (name === 'arm-stale') {
      navigator.serviceWorker.controller?.postMessage({type: 'arm-stale'});
    }
    if (name === 'release-stale') {
      navigator.serviceWorker.controller?.postMessage({type: 'release-stale'});
    }
    if (name === 'alternate') void action(name, '/__browser-test/select-alternate');
    if (name === 'second-key') void action(name, '/__browser-test/second-key');
    if (name === 'cancel-confirm') window.__browserConfirmMode = 'cancel';
    if (name === 'accept-confirm') window.__browserConfirmMode = 'accept';
  });
});
""".strip(),
        encoding="utf-8",
    )
    (isolated_web_dist / "browser-fault-sw.js").write_text(
        r"""
let retryDiscarded = false;
let retryGetDiscarded = false;
let retryBatchPath = null;
let reanalyzeDiscarded = false;
let holdNextBatchGet = false;
let releaseHeldBatchGet = false;
let resolveHeldBatchGet = null;
self.addEventListener('install', () => self.skipWaiting());
self.addEventListener('activate', (event) => event.waitUntil(self.clients.claim()));
self.addEventListener('message', (event) => {
  if (event.data?.type === 'arm-stale') {
    holdNextBatchGet = true;
    releaseHeldBatchGet = false;
  }
  if (event.data?.type === 'release-stale') {
    releaseHeldBatchGet = true;
    resolveHeldBatchGet?.();
  }
});
self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url);
  const isRetry = /\/analysis-batches\/[^/]+\/retry$/.test(url.pathname);
  const isReanalysis = /\/analysis-batches\/[^/]+\/reanalyze$/.test(url.pathname);
  if (!retryDiscarded && event.request.method === 'POST' && isRetry) {
    retryDiscarded = true;
    retryBatchPath = url.pathname.replace(/\/retry$/, '');
    event.respondWith((async () => {
      await fetch(event.request);
      await fetch('/__browser-test/discarded/retry', {method: 'POST'});
      throw new TypeError('browser acceptance: response intentionally discarded');
    })());
    return;
  }
  if (
    retryDiscarded && !retryGetDiscarded &&
    event.request.method === 'GET' && url.pathname === retryBatchPath
  ) {
    retryGetDiscarded = true;
    event.respondWith((async () => {
      const response = await fetch(event.request);
      await fetch('/__browser-test/discarded/retry_get', {method: 'POST'});
      throw new TypeError('browser acceptance: first reconciliation intentionally discarded');
    })());
    return;
  }
  if (
    holdNextBatchGet && event.request.method === 'GET' &&
    url.pathname === retryBatchPath
  ) {
    holdNextBatchGet = false;
    event.respondWith((async () => {
      const response = await fetch(event.request);
      await fetch('/__browser-test/discarded/stale_get_captured', {method: 'POST'});
      await new Promise((resolve) => {
        resolveHeldBatchGet = resolve;
        if (releaseHeldBatchGet) resolve();
      });
      resolveHeldBatchGet = null;
      releaseHeldBatchGet = false;
      await fetch('/__browser-test/discarded/stale_get', {method: 'POST'});
      return response;
    })());
    return;
  }
  if (!reanalyzeDiscarded && event.request.method === 'POST' && isReanalysis) {
    event.respondWith((async () => {
      const response = await fetch(event.request);
      if (!response.ok) return response;
      reanalyzeDiscarded = true;
      await fetch('/__browser-test/discarded/reanalyze', {method: 'POST'});
      throw new TypeError('browser acceptance: response intentionally discarded');
    })());
  }
});
""".strip(),
        encoding="utf-8",
    )
    database = RuntimeDatabase(runtime_root)
    database.initialize()
    auth = AdminSessionService(
        database=database,
        identity_hmac_key=b"browser-acceptance-identity-key-32",
        deployment_profile="loopback_evaluation",
    )
    grant = issue_admin_local_launch_grant(
        database,
        deployment_profile="loopback_evaluation",
    )
    limits = ChatLimits(
        database,
        ip_hash_key=b"browser-acceptance-ip-hash-key-32",
        requests_per_minute=100,
        daily_budget=1000,
        global_concurrency=4,
    )
    chat_controller = FixtureChatController()
    chats = {
        model: FixtureChat(chat_controller, model) for model in ("browser-chat-a", "browser-chat-b")
    }
    runtimes = {
        model: ProviderRuntime(
            chat=chat,
            embedding=FixtureEmbedding(),
            max_attempts=1,
            retry_base_seconds=0,
        )
        for model, chat in chats.items()
    }
    runtime = ProviderRuntime(
        chat=chats["browser-chat-a"],
        embedding=FixtureEmbedding(),
        max_attempts=1,
        retry_base_seconds=0,
    )
    connections = ModelConnectionRegistry(
        database,
        ProtectedModelSecretStore(runtime_root / "secrets" / "model.key"),
    )
    connection = connections.create(
        ModelConnectionInput(
            "Browser fixture",
            "openai_compatible",
            "https://models.example.test/v1",
            "BROWSER_FIXTURE_KEY",
            "replace",
        )
    )
    chat_profiles = ChatProfileRegistry(
        database, connections, lambda profile: chats[profile.model_id]
    )
    chat_profile = chat_profiles.create(
        ChatProfileInput(connection.connection_id, "browser-chat-a")
    )
    chat_profile = chat_profiles.probe(chat_profile.profile_id)
    alternate_chat_profile = chat_profiles.create(
        ChatProfileInput(connection.connection_id, "browser-chat-b")
    )
    alternate_chat_profile = chat_profiles.probe(alternate_chat_profile.profile_id)
    embedding_profiles = EmbeddingProfileRegistry(
        database=database,
        provider_resolver=lambda _profile: runtime.embedding,
        activation_compatible=lambda _profile: True,
    )
    embedding_profile = embedding_profiles.create(
        EmbeddingProfileInput(
            provider="openai_compatible",
            model_id="browser-embedding",
            dimension=3,
            normalized=True,
            query_prefix="query: ",
            passage_prefix="passage: ",
            connection_reference=connection.connection_id,
            connection_revision=connection.revision,
        )
    )
    embedding_profile = embedding_profiles.probe(embedding_profile.profile_id)
    analysis_selection = AnalysisSelectionRegistry(
        database,
        chat_profiles,
        embedding_profiles,
        connections,
    )
    analysis_selection.select(
        chat_profile_id=chat_profile.profile_id,
        embedding_profile_id=embedding_profile.profile_id,
    )
    limiter = GitHubRateLimiter(safety_reserve=0)
    planner = BatchPreflightPlanner(
        resolver=GitHubRESTMetadataResolver(
            transport=FixtureRESTTransport(),
            limiter=limiter,
        ),
        limiter=limiter,
        maximum_generation_attempts=2,
    )
    archive_transport = FixtureArchiveTransport()
    source = GitHubArchiveSource(
        transport=archive_transport,
        limiter=limiter,
        staging_root=runtime_root / "archive-staging",
        limits=ArchiveSafetyLimits(
            max_compressed_bytes=2 * 1024 * 1024,
            max_uncompressed_bytes=4 * 1024 * 1024,
            max_entries=100,
            max_single_file_bytes=1024 * 1024,
        ),
    )
    onboarding = GuidedOnboardingService(
        source_resolver=FixtureSourceResolver(),  # type: ignore[arg-type]
        providers_supplier=lambda: runtime,
        limits_supplier=lambda: limits,
        staging_root=runtime_root / "onboarding-staging",
        provider_timeout_seconds=10,
        analysis_timeout_seconds=30,
        analysis_provider_timeout_seconds=10,
        analysis_generation_attempts=2,
    )
    capacity = BatchCapacity(1, 1, 2, 2, 3)
    gates = BatchStageGates(capacity)
    store = BatchRuntimeStore(database)
    runner = PinnedBatchItemRunner(
        store=store,
        source=source,
        onboarding=onboarding,
        gates=gates,
        runtime_resolver=lambda pair: runtimes[pair.chat_model_id],
    )
    batches = AnalysisBatchService(
        store=store,
        planner=planner,
        provider_ready_supplier=lambda: True,
        capacity=capacity,
        runner=runner,
        stage_gates=gates,
        analysis_timeout_seconds=30,
        analysis_generation_attempts=2,
        analysis_pair_supplier=analysis_selection.frozen_pair,
    )
    operations = AdminOperations(
        github=None,
        database=database,
        public_base_url=origin,
        onboarding=onboarding,
        analysis_batches=batches,
        embedding_profiles=embedding_profiles,
        model_connections=connections,
        chat_profiles=chat_profiles,
        analysis_selection=analysis_selection,
    )
    application = create_app(
        setup_state=None,
        runtime_database=database,
        provider_runtime=runtime,
        provider_adapter="fixture",
        chat_limits=limits,
        web_dist=isolated_web_dist,
        admin_session_service=auth,
        admin_origins=(origin,),
        admin_operations=operations,
        analysis_batch_service=batches,
        analysis_cleanup_seconds=60,
    )
    wrapped = BrowserAcceptanceApp(
        application,
        database=database,
        batches=batches,
        selection=analysis_selection,
        alternate_chat_profile_id=alternate_chat_profile.profile_id,
        embedding_profile_id=embedding_profile.profile_id,
        chat_controller=chat_controller,
        archive_calls=archive_transport.calls,
    )
    return wrapped, grant


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runtime", type=Path, required=True)
    parser.add_argument("--web-dist", type=Path, default=Path("apps/web/dist"))
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    origin = f"http://127.0.0.1:{args.port}"
    app, grant = build_application(args.runtime, args.web_dist.resolve(), origin)
    print(f"BROWSER_URL={origin}/admin#local-launch={grant}", flush=True)
    uvicorn.run(app, host="127.0.0.1", port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
