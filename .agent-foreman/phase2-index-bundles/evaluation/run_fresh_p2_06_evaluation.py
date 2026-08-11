"""Fresh read-only P2-06 falsification probes.

This evaluator intentionally writes only its own artifacts below ``evaluation``.
It invokes production boundaries with deterministic fixture inputs, records both
successful controls and failures, and never repairs application code.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Mapping
from unittest.mock import patch

from fastapi.testclient import TestClient

from reponpc.bundles import archive as archive_module
from reponpc.bundles.archive import BundleError, build_bundle, verify_bundle_archive
from reponpc.bundles.manager import BundleActivationError, BundleManager
from reponpc.bundles.manifest import StableManifest, bundle_id_for
from reponpc.bundles.updater import BundleUpdater, HttpResponse
from reponpc.indexing.github import GitHubSourceResolver, SourceResolutionError
from reponpc.indexing.publication import PublicationCoordinator, PublicationError
from reponpc.main import create_app
from reponpc.runtime.database import RuntimeDatabase

# ``python path/to/probe.py`` sets sys.path to the probe directory, while the
# fixture package deliberately lives at the repository root.
REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tests.integration.test_bundle_activation import _bundle_at, _verified
from tests.integration.test_bundle_producer_consumer import (
    _configuration_source,
    _fixture_snapshot,
    _public_files,
)
from tests.integration.test_index_build import DeterministicEmbeddingProvider, _build


EVALUATION_ROOT = Path(__file__).resolve().parent
ARTIFACT_ROOT = EVALUATION_ROOT / "artifacts"
COMMAND = (
    "rtk proxy uv --cache-dir D:/RepoNPC/.uv-cache run --offline --no-sync "
    "--python C:/Python314/python.exe --no-managed-python python "
    ".agent-foreman/phase2-index-bundles/evaluation/run_fresh_p2_06_evaluation.py"
)
SUPPORTING_TEST_COMMAND = (
    "rtk proxy uv --cache-dir D:/RepoNPC/.uv-cache run --offline --no-sync "
    "--python C:/Python314/python.exe --no-managed-python pytest --basetemp "
    "D:/RepoNPC/.agent-foreman/phase2-index-bundles/evaluation/.pytest-tmp "
    "-p no:cacheprovider tests/integration/test_github_resolution.py "
    "tests/security/test_bundle_validation.py "
    "tests/integration/test_bundle_producer_consumer.py "
    "tests/integration/test_bundle_activation.py tests/integration/test_bundle_updater.py "
    "tests/integration/test_bundle_updater_lifecycle.py "
    "tests/integration/test_publication_last.py -q"
)
PLAN_ID = "REPONPC-P2-06-INDEX-BUNDLES-20260810"


@dataclass(slots=True)
class RecordingTransport:
    """Production updater transport seam that records only safe request metadata."""

    responses: list[HttpResponse]
    calls: list[tuple[str, dict[str, str]]] = field(default_factory=list)

    def get(self, url: str, *, headers: Mapping[str, str], max_bytes: int) -> HttpResponse:
        self.calls.append((url, dict(headers)))
        if not self.responses:
            raise AssertionError("unexpected updater request")
        result = self.responses.pop(0)
        if len(result.body) > max_bytes:
            raise AssertionError("probe response exceeded production byte bound")
        return result


@dataclass(slots=True)
class RecordingPublisher:
    """Publication boundary double which makes stable-manifest mutation observable."""

    fail_at: str | None = None
    events: list[str] = field(default_factory=list)
    stable_content: bytes = b'{"prior":"stable"}'

    def _fail(self, stage: str) -> None:
        if self.fail_at == stage:
            raise OSError(stage)

    def create_immutable_release(self, *, tag: str, name: str) -> int:
        self.events.append("release")
        self._fail("release")
        return 91

    def upload_immutable_asset(self, *, release_id: int, name: str, content: bytes) -> str:
        self.events.append("upload")
        self._fail("upload")
        if release_id != 91 or not name.endswith(".tar.zst") or not content:
            raise AssertionError("publication coordinator supplied an invalid immutable asset")
        return "https://github.com/fixture-owner/demo/releases/download/index/asset.tar.zst"

    def verify_asset(self, *, asset_url: str, size: int, sha256: str) -> None:
        self.events.append("verify")
        self._fail("verify")
        if not asset_url.startswith("https://github.com/") or size <= 0 or len(sha256) != 64:
            raise AssertionError("publication coordinator supplied an invalid verification request")

    def update_stable_manifest_last(self, *, content: bytes) -> None:
        self.events.append("stable")
        self._fail("stable")
        self.stable_content = content


def _artifact_path(probe_id: str) -> Path:
    return ARTIFACT_ROOT / f"{probe_id.lower()}.json"


def _record_probe(
    *,
    probe_id: str,
    invariant_id: str,
    setup: str,
    fault_injection: str,
    production_trigger: str,
    oracle: str,
    anti_oracle: str,
    deterministic_result: str,
    observed: dict[str, Any],
) -> dict[str, Any]:
    artifact = _artifact_path(probe_id)
    record = {
        "probe_id": probe_id,
        "invariant_id": invariant_id,
        "setup": setup,
        "fault_injection": fault_injection,
        "production_trigger": production_trigger,
        "oracle": oracle,
        "anti_oracle": anti_oracle,
        "command": COMMAND,
        "expected_exit_code": 0,
        "exit_code": 0,
        "deterministic_result": deterministic_result,
        "artifact_path": artifact.relative_to(Path.cwd()).as_posix(),
        "observed": observed,
    }
    artifact.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return record


def _close_probe_manager(manager: BundleManager) -> None:
    """Release evaluator-held SQLite handles so its private temp tree is removable."""

    closed: set[int] = set()
    for live in (manager._active, manager._previous):
        if live is not None and id(live.index) not in closed:
            try:
                live.index.close()
            except sqlite3.Error:
                pass
            closed.add(id(live.index))


def _remove_evaluator_temp_tree(path: Path) -> None:
    """Best-effort cleanup after Windows releases SQLite reader handles."""

    for attempt in range(5):
        shutil.rmtree(path, ignore_errors=True)
        if not path.exists():
            return
        if attempt < 4:
            time.sleep(0.05)


def _resolver_responses(*, commit_sha: str, html_url: str) -> dict[str, dict[str, object]]:
    return {
        "/repos/fixture-owner/demo": {"default_branch": "main", "html_url": html_url},
        "/repos/fixture-owner/demo/commits/main": {"sha": commit_sha},
        f"/repos/fixture-owner/demo/git/trees/{commit_sha}?recursive=1": {
            "truncated": False,
            "tree": [],
        },
    }


def probe_source_ref_immutability() -> dict[str, Any]:
    valid_sha = "d" * 40

    def valid_get(_self: GitHubSourceResolver, path: str) -> dict[str, object]:
        return _resolver_responses(
            commit_sha=valid_sha,
            html_url="https://github.com/fixture-owner/demo",
        )[path]

    with patch.object(GitHubSourceResolver, "_get_json", valid_get):
        valid = GitHubSourceResolver().resolve(slug="fixture-owner/demo", ref=None)

    def bad_sha_get(_self: GitHubSourceResolver, path: str) -> dict[str, object]:
        return _resolver_responses(
            commit_sha="e" * 39,
            html_url="https://github.com/fixture-owner/demo",
        )[path]

    with patch.object(GitHubSourceResolver, "_get_json", bad_sha_get):
        try:
            GitHubSourceResolver().resolve(slug="fixture-owner/demo", ref=None)
            bad_sha_code = "accepted"
        except SourceResolutionError as error:
            bad_sha_code = error.code

    def bad_host_get(_self: GitHubSourceResolver, path: str) -> dict[str, object]:
        return _resolver_responses(
            commit_sha=valid_sha,
            html_url="https://untrusted.example/fixture-owner/demo",
        )[path]

    with patch.object(GitHubSourceResolver, "_get_json", bad_host_get):
        try:
            GitHubSourceResolver().resolve(slug="fixture-owner/demo", ref=None)
            bad_host_code = "accepted"
        except SourceResolutionError as error:
            bad_host_code = error.code

    passed = (
        valid.commit_sha == valid_sha
        and bad_sha_code == "github_commit_invalid"
        and bad_host_code == "github_host_not_allowed"
    )
    return _record_probe(
        probe_id="PROBE-P2-06-SOURCE-REF",
        invariant_id="INV-SOURCE-REF-IMMUTABLE",
        setup="Production GitHubSourceResolver with a deterministic API-response boundary.",
        fault_injection="A 39-character commit SHA and an untrusted repository HTML host.",
        production_trigger="GitHubSourceResolver.resolve() resolves the default branch through metadata, commit, and tree paths.",
        oracle="A valid response returns the exact 40-character SHA; both faults fail closed with safe source-resolution codes.",
        anti_oracle="Constructing ResolvedRepository directly is excluded; this calls the resolver's public resolution path.",
        deterministic_result="passed" if passed else "failed",
        observed={
            "valid_commit_sha": valid.commit_sha,
            "bad_sha_code": bad_sha_code,
            "bad_host_code": bad_host_code,
        },
    )


def probe_archive_safety() -> dict[str, Any]:
    # This is intentionally side-effect free: on Windows, extracting the accepted
    # drive-qualified member could write outside the evaluation sandbox.
    drive_member = "C:/outside-evaluation.txt"
    drive_accepted = archive_module._safe_member_name(drive_member)
    traversal_rejected = not archive_module._safe_member_name("../runtime.sqlite")
    link_like_rejected = not archive_module._safe_member_name("public\\character.png")
    passed = traversal_rejected and link_like_rejected and not drive_accepted
    return _record_probe(
        probe_id="PROBE-P2-06-ARCHIVE-SAFETY",
        invariant_id="INV-BUNDLE-ARCHIVE-SAFETY",
        setup="Production archive member-name validator evaluated under the repository's Windows runtime target.",
        fault_injection="A Windows drive-qualified archive member name (C:/outside-evaluation.txt).",
        production_trigger="archive._safe_member_name(), the guard called before _stage_safe_members constructs staging / member.name.",
        oracle="Traversal, backslash, and every drive-qualified/absolute member must be rejected before extraction.",
        anti_oracle="The probe does not extract the malicious member or write outside the evaluator-owned directory; ../runtime.sqlite and a backslash path remain rejection controls.",
        deterministic_result="passed" if passed else "failed",
        observed={
            "drive_member": drive_member,
            "drive_member_accepted": drive_accepted,
            "traversal_rejected": traversal_rejected,
            "backslash_path_rejected": link_like_rejected,
        },
    )


def probe_compatibility_readonly(case_root: Path) -> dict[str, Any]:
    provider = DeterministicEmbeddingProvider()
    incompatible_root = case_root / "compatibility"
    index_result = _build(incompatible_root / "index", provider=provider)
    configuration = _configuration_source()
    repository = _fixture_snapshot()
    built_at = datetime(2026, 8, 10, 12, 8, tzinfo=UTC)
    incompatible_id = bundle_id_for(
        built_at=built_at,
        configuration_bytes=configuration.content.encode("utf-8"),
        repositories=((repository.slug, repository.commit_sha),),
        embedding=provider.identity(),
        parser_chunker_version="fresh-evaluation-v1",
    )
    incompatible = build_bundle(
        index_result=index_result,
        configuration_source=configuration,
        repositories=(repository,),
        bundle_id=incompatible_id,
        built_at=built_at,
        public_files=_public_files(),
        output_path=incompatible_root / f"reponpc-index-{incompatible_id}.tar.zst",
        application_minimum="0.2.0",
        application_maximum_exclusive="0.3.0",
    )
    try:
        verify_bundle_archive(
            archive_path=incompatible.archive_path,
            staging_directory=incompatible_root / "stage-incompatible",
            expected_outer_sha256=incompatible.archive_sha256,
            expected_embedding=provider.identity(),
            max_bundle_bytes=1024 * 1024,
        )
        incompatible_code = "accepted"
    except BundleError as error:
        incompatible_code = error.code

    valid_bundle, _ = _bundle_at(case_root / "readonly-valid", 9)
    verified = verify_bundle_archive(
        archive_path=valid_bundle.archive_path,
        staging_directory=case_root / "readonly-stage",
        expected_outer_sha256=valid_bundle.archive_sha256,
        expected_embedding=provider.identity(),
        max_bundle_bytes=1024 * 1024,
    )
    try:
        try:
            verified.index._connection.execute("DELETE FROM evidence")
            write_error = "write_succeeded"
        except sqlite3.OperationalError:
            write_error = "sqlite_operational_error"
        smoke_ids = verified.index.lexical_candidates("hybrid retrieval", limit=1)
    finally:
        verified.close()
    passed = incompatible_code == "bundle_application_incompatible" and bool(smoke_ids) and write_error == "sqlite_operational_error"
    return _record_probe(
        probe_id="PROBE-P2-06-COMPATIBILITY-READONLY",
        invariant_id="INV-BUNDLE-COMPATIBILITY-READONLY",
        setup="Real index builder, bundle serializer, staged verifier, and ReadOnlyIndex consumer using the checked-in fixture corpus.",
        fault_injection="A syntactically valid bundle declares application compatibility 0.2.0 <= app < 0.3.0, excluding the running 0.1.0 application.",
        production_trigger="verify_bundle_archive() followed by the real ReadOnlyIndex lexical query and attempted SQLite mutation.",
        oracle="The incompatible candidate is rejected before activation; a valid candidate queries successfully and SQLite refuses DELETE.",
        anti_oracle="Reading manifest JSON alone or opening SQLite without the production verifier does not count.",
        deterministic_result="passed" if passed else "failed",
        observed={
            "incompatible_code": incompatible_code,
            "valid_smoke_candidate_count": len(smoke_ids),
            "write_attempt": write_error,
        },
    )


def probe_activation_last_known_good(case_root: Path) -> dict[str, Any]:
    runtime = RuntimeDatabase(case_root / "activation-runtime")
    runtime.initialize()
    candidate_a, provider = _verified(case_root, "activation-a", 10)
    manager = BundleManager(
        data_directory=case_root / "activation-data",
        runtime_database=runtime,
        expected_embedding=provider.identity(),
    )
    manager.activate(candidate_a)
    active_a = manager.status().active_bundle_id

    candidate_b, _ = _verified(case_root, "activation-b", 11)
    with manager.acquire() as in_flight_a:
        manager.activate(candidate_b)
        in_flight_survived = bool(in_flight_a.lexical_candidates("hybrid retrieval", limit=1))
        active_b = manager.status().active_bundle_id

    candidate_c, _ = _verified(case_root, "activation-c", 12)
    try:
        manager.activate(
            candidate_c,
            before_pointer_swap=lambda: (_ for _ in ()).throw(RuntimeError("fault before swap")),
        )
        pre_swap_code = "accepted"
    except BundleActivationError as error:
        pre_swap_code = error.code
    after_fault_active = manager.status().active_bundle_id

    restarted = BundleManager(
        data_directory=case_root / "activation-data",
        runtime_database=runtime,
        expected_embedding=provider.identity(),
    )
    restarted_active = restarted.status().active_bundle_id
    passed = (
        active_a is not None
        and active_b is not None
        and active_b != active_a
        and in_flight_survived
        and pre_swap_code == "bundle_pointer_swap_failed"
        and after_fault_active == active_b
        and restarted_active == active_b
    )
    record = _record_probe(
        probe_id="PROBE-P2-06-ACTIVATION-LKG",
        invariant_id="INV-ACTIVATION-LAST-KNOWN-GOOD",
        setup="A real RuntimeDatabase, verified A/B/C bundles, and a production BundleManager using one persistent data directory.",
        fault_injection="A fault immediately before pointer replacement, followed by a fresh manager process model over the persisted runtime and validated-bundle directory.",
        production_trigger="BundleManager.activate(), acquire() for an in-flight A reader, then a fresh BundleManager construction.",
        oracle="A remains queryable while B activates; pre-swap fault retains B; restart reconstructs B as the active last-known-good bundle.",
        anti_oracle="A direct ReadOnlyIndex query bypassing BundleManager leasing/pointer state does not count.",
        deterministic_result="passed" if passed else "failed",
        observed={
            "active_a": active_a,
            "active_b": active_b,
            "in_flight_a_survived": in_flight_survived,
            "pre_swap_code": pre_swap_code,
            "active_after_pre_swap_fault": after_fault_active,
            "fresh_manager_active": restarted_active,
            "persisted_runtime_active": runtime.bundle_state().active_bundle_id,
        },
    )
    _close_probe_manager(manager)
    _close_probe_manager(restarted)
    return record


def probe_polling_host_304_lifecycle(case_root: Path) -> dict[str, Any]:
    seed_bundle, provider = _bundle_at(case_root / "poll-seed", 13)
    stable = StableManifest(
        bundle_id=seed_bundle.manifest.bundle_id,
        release_tag="index-fresh-evaluation",
        asset_url="https://example.test/reponpc-index.tar.zst",
        asset_size=seed_bundle.archive_size,
        asset_sha256=seed_bundle.archive_sha256,
        published_at="2026-08-10T12:14:00Z",
    )
    transport = RecordingTransport(
        [
            HttpResponse(200, {"ETag": '"fresh-v1"'}, stable.canonical_bytes()),
            HttpResponse(200, {}, seed_bundle.archive_path.read_bytes()),
            HttpResponse(304, {}, b""),
        ]
    )
    runtime = RuntimeDatabase(case_root / "poll-runtime")
    runtime.initialize()
    manager = BundleManager(
        data_directory=case_root / "poll-data",
        runtime_database=runtime,
        expected_embedding=provider.identity(),
    )
    updater = BundleUpdater(
        manifest_url="https://example.test/stable-manifest.json",
        transport=transport,
        manager=manager,
        runtime_database=runtime,
        expected_embedding=provider.identity(),
        max_bundle_bytes=1024 * 1024,
        allowed_hosts=frozenset({"example.test"}),
        data_directory=case_root / "poll-data",
    )
    application = create_app(
        runtime_database=runtime,
        bundle_manager=manager,
        bundle_updater=updater,
        bundle_poll_seconds=3600,
    )
    with TestClient(application) as client:
        status = client.get("/api/public/status").json()
        lifecycle_active = manager.status().active_bundle_id
        not_modified = updater.poll_once()
    calls_after_304 = len(transport.calls)
    etag_on_304 = transport.calls[-1][1].get("If-None-Match")

    hostile = StableManifest(
        bundle_id=seed_bundle.manifest.bundle_id,
        release_tag="index-hostile",
        asset_url="https://untrusted.example/reponpc-index.tar.zst",
        asset_size=seed_bundle.archive_size,
        asset_sha256=seed_bundle.archive_sha256,
        published_at="2026-08-10T12:15:00Z",
    )
    hostile_transport = RecordingTransport([HttpResponse(200, {"ETag": '"hostile"'}, hostile.canonical_bytes())])
    hostile_updater = BundleUpdater(
        manifest_url="https://example.test/stable-manifest.json",
        transport=hostile_transport,
        manager=manager,
        runtime_database=runtime,
        expected_embedding=provider.identity(),
        max_bundle_bytes=1024 * 1024,
        allowed_hosts=frozenset({"example.test"}),
        data_directory=case_root / "poll-data",
    )
    hostile_result = hostile_updater.poll_once()
    hostile_active = manager.status().active_bundle_id
    passed = (
        lifecycle_active == stable.bundle_id
        and status["index"]["ready"] is True
        and not_modified == "not_modified"
        and calls_after_304 == 3
        and etag_on_304 == '"fresh-v1"'
        and hostile_result == "rejected"
        and len(hostile_transport.calls) == 1
        and hostile_active == stable.bundle_id
    )
    record = _record_probe(
        probe_id="PROBE-P2-06-POLLING-HOST-304-LIFECYCLE",
        invariant_id="INV-POLLING-NETWORK-BOUNDARY",
        setup="Actual FastAPI lifespan with a real BundleUpdater/BundleManager/RuntimeDatabase and bounded recording transport.",
        fault_injection="A 304 response after activation and a stable manifest whose asset points to an unallowlisted host.",
        production_trigger="create_app() lifespan starts the production poller; BundleUpdater.poll_once() performs the conditional and hostile checks.",
        oracle="Lifespan activates the valid candidate; 304 sends only the manifest request with If-None-Match; hostile asset performs no asset request and retains active state.",
        anti_oracle="Instantiating the updater without starting the app lifespan, or treating a 304 as a successful asset download, does not count.",
        deterministic_result="passed" if passed else "failed",
        observed={
            "lifecycle_active": lifecycle_active,
            "status_index": status["index"],
            "not_modified_result": not_modified,
            "calls_after_304": calls_after_304,
            "etag_on_304": etag_on_304,
            "hostile_result": hostile_result,
            "hostile_request_count": len(hostile_transport.calls),
            "hostile_active": hostile_active,
            "hostile_safe_error": runtime.bundle_state().safe_update_error,
        },
    )
    _close_probe_manager(manager)
    return record


def probe_publication_last(case_root: Path) -> dict[str, Any]:
    bundle, _ = _bundle_at(case_root / "publication-bundle", 14)
    successful = RecordingPublisher()
    result = PublicationCoordinator(successful).publish(
        bundle,
        now=datetime(2026, 8, 10, 12, 16, tzinfo=UTC),
    )
    failures: dict[str, dict[str, Any]] = {}
    for stage in ("release", "upload", "verify"):
        publisher = RecordingPublisher(fail_at=stage)
        prior = publisher.stable_content
        try:
            PublicationCoordinator(publisher).publish(
                bundle,
                now=datetime(2026, 8, 10, 12, 16, tzinfo=UTC),
            )
            code = "accepted"
        except PublicationError as error:
            code = error.code
        failures[stage] = {
            "code": code,
            "events": publisher.events,
            "stable_unchanged": publisher.stable_content == prior,
        }
    passed = (
        successful.events == ["release", "upload", "verify", "stable"]
        and successful.stable_content == result.stable_manifest.canonical_bytes()
        and all(
            value["code"] == "bundle_publication_failed"
            and value["stable_unchanged"]
            and "stable" not in value["events"]
            for value in failures.values()
        )
    )
    return _record_probe(
        probe_id="PROBE-P2-06-PUBLICATION-LAST",
        invariant_id="INV-PUBLICATION-LAST",
        setup="Production PublicationCoordinator with a mutation-recording immutable-release boundary and a real built bundle.",
        fault_injection="Independent OSError injection at release creation, immutable asset upload, and availability/checksum verification.",
        production_trigger="PublicationCoordinator.publish() invokes the release, upload, verify, and final stable-manifest sequence.",
        oracle="Success is exactly release -> upload -> verify -> stable; every preceding fault preserves prior stable bytes and never invokes stable mutation.",
        anti_oracle="A publisher method invoked directly outside PublicationCoordinator does not count as publication ordering evidence.",
        deterministic_result="passed" if passed else "failed",
        observed={
            "success_events": successful.events,
            "success_stable_matches_result": successful.stable_content == result.stable_manifest.canonical_bytes(),
            "preceding_failure_results": failures,
        },
    )


def run_supporting_tests() -> dict[str, Any]:
    """Run existing focused gates without granting them authority over new probes."""

    test_paths = [
        "tests/integration/test_github_resolution.py",
        "tests/security/test_bundle_validation.py",
        "tests/integration/test_bundle_producer_consumer.py",
        "tests/integration/test_bundle_activation.py",
        "tests/integration/test_bundle_updater.py",
        "tests/integration/test_bundle_updater_lifecycle.py",
        "tests/integration/test_publication_last.py",
    ]
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "--basetemp",
            str(EVALUATION_ROOT / ".pytest-tmp"),
            "-p",
            "no:cacheprovider",
            *test_paths,
            "-q",
        ],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    artifact = ARTIFACT_ROOT / "supporting-focused-tests.txt"
    artifact.write_text(
        "command:\n"
        + SUPPORTING_TEST_COMMAND
        + "\n\nstdout:\n"
        + completed.stdout
        + "\nstderr:\n"
        + completed.stderr,
        encoding="utf-8",
    )
    _remove_evaluator_temp_tree(EVALUATION_ROOT / ".pytest-tmp")
    return {
        "gate_ids": [
            "GATE-P2-06-SOURCE-INDEX",
            "GATE-P2-06-PRODUCER-CONSUMER",
            "GATE-P2-06-BUNDLE-NEGATIVES",
            "GATE-P2-06-ACTIVATION-ROLLBACK",
            "GATE-P2-06-POLLING-LIFECYCLE",
            "GATE-P2-06-PUBLICATION-LAST",
        ],
        "command": SUPPORTING_TEST_COMMAND,
        "exit_code": completed.returncode,
        "result": "passed" if completed.returncode == 0 else "failed",
        "artifact_path": artifact.relative_to(Path.cwd()).as_posix(),
        "authority": "supporting deterministic evidence; it does not replace fresh probe outcomes",
    }


def main() -> int:
    ARTIFACT_ROOT.mkdir(parents=True, exist_ok=True)
    work_root = Path(tempfile.mkdtemp(prefix="fresh-p2-06-", dir=ARTIFACT_ROOT))
    try:
        probes = [
            probe_source_ref_immutability(),
            probe_archive_safety(),
            probe_compatibility_readonly(work_root),
            probe_activation_last_known_good(work_root),
            probe_polling_host_304_lifecycle(work_root),
            probe_publication_last(work_root),
        ]
    finally:
        _remove_evaluator_temp_tree(work_root)

    supporting = run_supporting_tests()
    failed = [probe for probe in probes if probe["deterministic_result"] != "passed"]
    deterministic_failed = bool(failed) or supporting["result"] != "passed"
    findings: list[dict[str, str]] = []
    failed_ids = {str(probe["probe_id"]) for probe in failed}
    if "PROBE-P2-06-ARCHIVE-SAFETY" in failed_ids:
        findings.append(
            {
                "severity": "high",
                "invariant_id": "INV-BUNDLE-ARCHIVE-SAFETY",
                "location": "src/reponpc/bundles/archive.py:_safe_member_name",
                "evidence": "The production archive member-name guard accepted a Windows drive-qualified path.",
                "impact": "A drive-qualified tar member is not rejected before extraction.",
            }
        )
    if "PROBE-P2-06-ACTIVATION-LKG" in failed_ids:
        findings.append(
            {
                "severity": "high",
                "invariant_id": "INV-ACTIVATION-LAST-KNOWN-GOOD",
                "location": "src/reponpc/bundles/manager.py:BundleManager.__init__",
                "evidence": "A fresh manager did not reconstruct its persisted active bundle.",
                "impact": "A process restart loses the last-known-good active bundle.",
            }
        )
    evaluation = {
        "schema_name": "agent-foreman/evaluation",
        "schema_version": "1.0",
        "profile": "full",
        "plan_id": PLAN_ID,
        "phase_id": "P2-06",
        "context_freshness": "fresh",
        "model_diversity": "unknown",
        "production_access": "read-only",
        "evaluation_write_scope": ".agent-foreman/phase2-index-bundles/evaluation/",
        "new_probes": probes,
        "supporting_evidence": [supporting],
        "recommendation": "revise" if deterministic_failed else "pass",
        "deterministic_result": "failed" if deterministic_failed else "passed",
        "findings": findings,
        "phase_completion_claim": "not made",
    }
    evaluation_path = EVALUATION_ROOT / "fresh-evaluation.json"
    evaluation_path.write_text(
        json.dumps(evaluation, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({"evaluation_path": evaluation_path.as_posix(), "failed_probe_ids": [item["probe_id"] for item in failed]}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
