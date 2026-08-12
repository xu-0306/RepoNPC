"""Fresh read-only Phase 2 closure falsification probes.

All mutable probe state is confined below this evaluation directory.
"""

from __future__ import annotations

import copy
import hashlib
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np
from fastapi.testclient import TestClient

from evals.phase2.run_benchmark import derive_formal_report, validate_candidate_output
from reponpc.api.public import SetupState
from reponpc.bundles.archive import BundleError, VerifiedBundle, verify_bundle_archive
from reponpc.bundles.index_reader import ReadOnlyIndex
from reponpc.bundles.manager import BundleActivationError, BundleManager
from reponpc.config.models import load_public_config
from reponpc.indexing.index_database import IndexDatabaseBuilder
from reponpc.indexing.publication import PublicationCoordinator, PublicationError
from reponpc.indexing.sources import EmbeddingProviderError, RepositoryBlob, ResolvedRepository
from reponpc.main import create_app
from reponpc.providers.local_sentence_transformers import (
    LocalSentenceTransformersEmbeddingProvider,
)
from reponpc.runtime.database import RuntimeDatabase
from tests.integration.test_bundle_producer_consumer import _bundle
from tests.integration.test_index_build import (
    DeterministicEmbeddingProvider,
    _build,
    _configuration_source,
    _fixture_snapshot,
)

ROOT = Path(__file__).resolve().parents[3]
EVALUATION = Path(__file__).resolve().parent
BASELINE = "83c3dd44f7cc2856dc3b61d9f637337f1a466d3e"
PYTHON = ROOT / ".venv" / "Scripts" / "python.exe"
ENTRYPOINT = ROOT / ".venv" / "Scripts" / "reponpc.exe"
FORMAL = ROOT / ".agent-foreman" / "phase2-closure" / "artifacts" / "formal-benchmark"


def _json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def _record(
    *,
    probe_id: str,
    invariant_id: str,
    setup: str,
    fault: str,
    trigger: str,
    oracle: str,
    anti_oracle: str,
    passed: bool,
    observations: dict[str, object],
    next_action: str | None = None,
) -> dict[str, object]:
    return {
        "probe_id": probe_id,
        "invariant_id": invariant_id,
        "setup": setup,
        "fault_injection": fault,
        "production_trigger": trigger,
        "oracle": oracle,
        "anti_oracle": anti_oracle,
        "status": "passed" if passed else "failed",
        "exit_code": 0 if passed else 1,
        "observations": observations,
        "next_action": next_action,
    }


def probe_spec_first() -> dict[str, object]:
    spec = (ROOT / "docs" / "TECHNICAL_SPEC.md").read_text(encoding="utf-8")
    ac = (ROOT / "docs" / "ACCEPTANCE_CRITERIA.md").read_text(encoding="utf-8")
    decisions = (ROOT / "docs" / "DECISIONS.md").read_text(encoding="utf-8")
    phases = (ROOT / "docs" / "DELIVERY_PHASES.md").read_text(encoding="utf-8")

    def validates(values: tuple[str, str, str, str]) -> bool:
        current_spec, current_ac, current_decisions, current_phases = values
        return all(
            (
                "Status | **Approved**" in current_spec,
                "Version | 0.1.1" in current_spec,
                "Phase 2 closure amendment approved" in current_spec,
                "### 5.5 Executable index CLI" in current_spec,
                "Phase 2 formal retrieval acceptance" in current_spec,
                "AC-009 — Hybrid retrieval meets the committed benchmark" in current_ac,
                "AC-029 — Publication advances the manifest last" in current_ac,
                "ADR-015:" in current_decisions and "- **Status:** Accepted" in current_decisions,
                "optional build-time production `local_sentence_transformers` adapter" in current_phases,
                "host-only oracle/scoring" in current_phases,
            )
        )

    actual = validates((spec, ac, decisions, phases))
    injected_phases = phases.replace(
        "optional build-time production `local_sentence_transformers` adapter",
        "deferred local adapter",
        1,
    )
    mutation_rejected = not validates((spec, ac, decisions, injected_phases))
    passed = actual and mutation_rejected
    return _record(
        probe_id="PROBE-P2C-SPEC-FIRST-001",
        invariant_id="INV-SPEC-FIRST",
        setup="Read the approved normative Phase 2 closure documents at the audited working tree.",
        fault="Remove the Phase 2 local-adapter boundary from an in-memory DELIVERY_PHASES copy.",
        trigger="Run a fresh cross-document closure trace validator over TECHNICAL_SPEC, ACCEPTANCE_CRITERIA, DECISIONS, and DELIVERY_PHASES.",
        oracle="The real documents validate and the mutated contract fails validation.",
        anti_oracle="Implementation existence or passing tests without Approved 0.1.1/ADR-015/AC traceability do not count.",
        passed=passed,
        observations={"actual_documents_valid": actual, "mutated_contract_rejected": mutation_rejected},
    )


def probe_cli_entrypoint() -> dict[str, object]:
    with tempfile.TemporaryDirectory(prefix="cli-", dir=EVALUATION) as raw:
        workspace = Path(raw)
        env = os.environ.copy()
        env["REPONPC_PORT"] = "not-an-integer"
        env["PYTHONDONTWRITEBYTECODE"] = "1"

        def run(*args: str) -> subprocess.CompletedProcess[str]:
            return subprocess.run(
                [str(ENTRYPOINT), *args],
                cwd=ROOT,
                env=env,
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )

        help_result = run("--help")
        validate_result = run("config", "validate", str(ROOT / "reponpc.example.yml"))
        index_result = run("index", "publish", "--bundle-dir", str(workspace / "empty"))
        serve_result = run("serve")
        combined_nonserve = "\n".join(
            help_result.stdout
            + help_result.stderr
            + validate_result.stdout
            + validate_result.stderr
            + index_result.stdout
            + index_result.stderr
        )
        stable_pointer_absent = not list(workspace.rglob("stable-manifest.json"))
        passed = bool(
            help_result.returncode == 0
            and validate_result.returncode == 0
            and "configuration valid" in validate_result.stdout
            and index_result.returncode != 0
            and "reponpc: build_receipt_invalid" in index_result.stderr
            and "deployment environment is invalid" not in combined_nonserve
            and serve_result.returncode != 0
            and "deployment environment is invalid" in (serve_result.stdout + serve_result.stderr)
            and stable_pointer_absent
        )
        return _record(
            probe_id="PROBE-P2C-CLI-ENTRYPOINT-001",
            invariant_id="INV-CLI-ENTRYPOINT",
            setup="Invoke the installed .venv console executable with a deliberately invalid startup-only REPONPC_PORT.",
            fault="Inject invalid deployment startup state and an empty publication directory.",
            trigger="Run --help, config validate, index publish, and serve through the installed reponpc.exe boundary.",
            oracle="Help/config bypass startup, index dispatch returns its own safe error without pointer mutation, and serve alone observes startup validation.",
            anti_oracle="Calling reponpc.cli.main directly or mocking run_server does not prove installed console dispatch.",
            passed=passed,
            observations={
                "help_exit": help_result.returncode,
                "config_exit": validate_result.returncode,
                "index_exit": index_result.returncode,
                "serve_exit": serve_result.returncode,
                "index_stderr": index_result.stderr.strip(),
                "serve_startup_error": "deployment environment is invalid" in (serve_result.stdout + serve_result.stderr),
                "stable_pointer_absent": stable_pointer_absent,
            },
        )


def probe_embedding_production() -> dict[str, object]:
    calls: list[dict[str, object]] = []

    class FakeModel:
        def __init__(self, mode: str) -> None:
            self.mode = mode

        def encode(self, texts: list[str], **kwargs: object) -> np.ndarray:
            calls.append({"texts": texts, "kwargs": kwargs, "mode": self.mode})
            if self.mode == "encode_error":
                raise RuntimeError("CANARY-UPSTREAM-BODY")
            dtype = np.float64 if self.mode == "float64" else np.float32
            width = 383 if self.mode == "wrong_width" else 384
            result = np.zeros((len(texts), width), dtype=dtype)
            if result.size:
                result[:, 0] = 1
            if self.mode == "nan":
                result[0, 0] = np.nan
            return result

    failures: dict[str, str] = {}
    for mode in ("float64", "wrong_width", "nan", "encode_error"):
        loads: list[tuple[object, ...]] = []

        def factory(*args: object, **kwargs: object) -> FakeModel:
            loads.append((*args, kwargs))
            return FakeModel(mode)

        provider = LocalSentenceTransformersEmbeddingProvider(
            model_id="intfloat/multilingual-e5-small",
            dimension=384,
            normalized=True,
            query_prefix="query: ",
            passage_prefix="passage: ",
        )
        with patch(
            "reponpc.providers.local_sentence_transformers.import_module",
            return_value=SimpleNamespace(SentenceTransformer=factory),
        ):
            try:
                provider.embed_query(["probe"])
            except EmbeddingProviderError as exc:
                failures[mode] = exc.code
                assert "CANARY" not in str(exc)
            else:
                failures[mode] = "not_rejected"
        assert len(loads) == 1

    identity = LocalSentenceTransformersEmbeddingProvider(
        model_id="intfloat/multilingual-e5-small",
        dimension=384,
        normalized=True,
        query_prefix="query: ",
        passage_prefix="passage: ",
    ).identity()
    passed = bool(
        failures
        == {
            "float64": "embedding_output_invalid",
            "wrong_width": "embedding_output_invalid",
            "nan": "embedding_output_invalid",
            "encode_error": "embedding_encode_failed",
        }
        and identity.adapter == "local_sentence_transformers"
        and all(call["texts"] == ["query: probe"] for call in calls)
        and all(call["kwargs"].get("normalize_embeddings") is True for call in calls)  # type: ignore[union-attr]
    )
    return _record(
        probe_id="PROBE-P2C-EMBEDDING-PRODUCTION-001",
        invariant_id="INV-EMBEDDING-PRODUCTION",
        setup="Inject one fake SentenceTransformer implementation behind the production lazy-load boundary.",
        fault="Return float64, wrong-width, NaN, and upstream-error outputs while recording model/encode calls.",
        trigger="Call production LocalSentenceTransformersEmbeddingProvider.embed_query.",
        oracle="Every invalid output fails with a stable safe code, exact query prefix/normalization is used, and only the configured model is loaded once.",
        anti_oracle="A fixture provider or checking identity fields without invoking encode does not count.",
        passed=passed,
        observations={"failures": failures, "model_encode_call_count": len(calls), "identity": identity.__dict__ if hasattr(identity, "__dict__") else {"adapter": identity.adapter, "model_id": identity.model_id, "dimension": identity.dimension}},
    )


def probe_formal_benchmark() -> dict[str, object]:
    questions_payload = _json(ROOT / "evals" / "phase2" / "public" / "questions.json")
    assert isinstance(questions_payload, dict)
    questions = questions_payload["questions"]
    candidate = _json(FORMAL / "candidate.json")
    assert isinstance(candidate, dict) and isinstance(questions, list)

    with tempfile.TemporaryDirectory(prefix="formal-cli-", dir=EVALUATION) as raw:
        rejected_artifact = Path(raw) / "must-not-exist.json"
        override = subprocess.run(
            [
                str(PYTHON),
                str(ROOT / "evals" / "phase2" / "run_benchmark.py"),
                "--oracle",
                str(ROOT / "evals" / "phase2" / "controller" / "expected-evidence.json"),
                "--artifacts",
                str(rejected_artifact),
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        oracle_override_rejected = bool(
            override.returncode == 2
            and "unrecognized arguments: --oracle" in override.stderr
            and not rejected_artifact.exists()
        )

    injected = copy.deepcopy(candidate)
    injected["indexed"]["formal_acceptance"] = True  # type: ignore[index]
    host_field_rejected = False
    try:
        validate_candidate_output(injected, questions)
    except ValueError:
        host_field_rejected = True

    colluding = copy.deepcopy(candidate)
    for result in colluding["results"]:  # type: ignore[index]
        forged_path = f"attacker/{result['id']}.txt"
        result["retrieved_paths"] = [forged_path]
        result["retrieved_evidence_ids"] = ["E_attacker_controlled"]
    colluding["timings_ns"] = [1 for _ in colluding["timings_ns"]]  # type: ignore[index]
    validate_candidate_output(colluding, questions)
    common = {
        "container_inspect": _json(FORMAL / "container-inspect.json"),
        "image_inspect": _json(FORMAL / "image-inspect.json"),
        "access_probe": _json(FORMAL / "access-probe.json"),
        "host_provenance": _json(FORMAL / "provenance.json"),
        "candidate_exit_code": 0,
    }
    legitimate_report = derive_formal_report(candidate=candidate, **common)  # type: ignore[arg-type]
    attacker_report = derive_formal_report(candidate=colluding, **common)  # type: ignore[arg-type]
    questions_path = ROOT / "evals" / "phase2" / "public" / "questions.json"
    oracle_path = ROOT / "evals" / "phase2" / "controller" / "expected-evidence.json"
    expected_inputs = {
        "questions_path": "evals/phase2/public/questions.json",
        "questions_sha256": hashlib.sha256(questions_path.read_bytes()).hexdigest(),
        "oracle_path": "evals/phase2/controller/expected-evidence.json",
        "oracle_sha256": hashlib.sha256(oracle_path.read_bytes()).hexdigest(),
    }
    canonical_digests_verified = legitimate_report.get("inputs") == expected_inputs
    dockerfile = (ROOT / "evals" / "phase2" / "Dockerfile").read_text(encoding="utf-8")
    dockerfile_oracle_free = "expected-evidence" not in dockerfile and "controller" not in dockerfile
    attacker_fails_canonical = bool(
        attacker_report["formal_acceptance"] is False
        and attacker_report["recall_at_8"] == 0.0
    )
    passed = bool(
        oracle_override_rejected
        and host_field_rejected
        and dockerfile_oracle_free
        and attacker_fails_canonical
        and legitimate_report["formal_acceptance"] is True
        and canonical_digests_verified
    )
    return _record(
        probe_id="PROBE-P2C-FORMAL-BENCHMARK-001",
        invariant_id="INV-FORMAL-BENCHMARK",
        setup="Reuse the recorded real container/image/access evidence and canonical controller files; do not run Docker.",
        fault="Pass --oracle at the real controller CLI, inject a forbidden candidate host field, and replace every candidate retrieved path with attacker-controlled misses.",
        trigger="Invoke the real argparse boundary, then call production validate_candidate_output and canonical derive_formal_report.",
        oracle="CLI rejects --oracle without producing an artifact; attacker paths remain Recall@8=0/formal=false; legitimate report records exact canonical input digests; host-only fields are rejected.",
        anti_oracle="Removing the CLI flag text without proving canonical scoring/digest provenance or candidate-field rejection does not count.",
        passed=passed,
        observations={
            "oracle_override_exit": override.returncode,
            "oracle_override_rejected": oracle_override_rejected,
            "override_artifact_absent": not rejected_artifact.exists(),
            "host_only_field_rejected": host_field_rejected,
            "dockerfile_oracle_free": dockerfile_oracle_free,
            "legitimate_formal_acceptance": legitimate_report["formal_acceptance"],
            "canonical_digests_verified": canonical_digests_verified,
            "reported_inputs": legitimate_report.get("inputs"),
            "attacker_oracle_acceptance": attacker_report["formal_acceptance"],
            "attacker_recall_at_8": attacker_report["recall_at_8"],
            "attacker_fails_canonical": attacker_fails_canonical,
        },
        next_action=None,
    )


def probe_profile_bilingual() -> dict[str, object]:
    with tempfile.TemporaryDirectory(prefix="profile-", dir=EVALUATION) as raw:
        workspace = Path(raw)
        bundle, provider = _bundle(workspace / "bundle")
        verified = verify_bundle_archive(
            archive_path=bundle.archive_path,
            staging_directory=workspace / "stage",
            expected_outer_sha256=bundle.archive_sha256,
            expected_embedding=provider.identity(),
            max_bundle_bytes=2 * 1024 * 1024,
        )
        try:
            app = create_app(
                setup_state=SetupState(
                    index_ready=True,
                    index_version=bundle.manifest.bundle_id,
                    public_directory=verified.directory / "public",
                )
            )
            with TestClient(app) as client:
                zh = client.get("/api/public/profile?locale=zh-TW")
                en = client.get("/api/public/profile?locale=en")
            valid_route = bool(
                zh.status_code == en.status_code == 200
                and zh.json()["locale"] == "zh-TW"
                and en.json()["locale"] == "en"
                and zh.json()["profile"]["headline"] != en.json()["profile"]["headline"]
                and "locales" not in zh.json()
            )
        finally:
            verified.close()

        profile = json.loads(
            (workspace / "stage" / "public" / "profile.json").read_text(encoding="utf-8")
        ) if (workspace / "stage" / "public" / "profile.json").exists() else None
        # Re-read canonical producer bytes from the verified bundle before it was closed/moved.
        if profile is None:
            # The stage remains after close; this branch is defensive.
            raise AssertionError("verified public profile disappeared")
        del profile["locales"]["en"]
        from reponpc.indexing.public_profile import PublicProfileError, parse_public_profile_bytes

        locale_fault_rejected = False
        try:
            parse_public_profile_bytes(json.dumps(profile).encode("utf-8"))
        except PublicProfileError:
            locale_fault_rejected = True
        passed = valid_route and locale_fault_rejected
        return _record(
            probe_id="PROBE-P2C-PROFILE-BILINGUAL-001",
            invariant_id="INV-PROFILE-BILINGUAL",
            setup="Build production profile bytes into a real archive, verify it, and expose that same verified public directory through the real FastAPI route.",
            fault="Delete the en locale from the produced schema in memory and pass it to the production profile parser.",
            trigger="Run build_bundle -> verify_bundle_archive -> GET /api/public/profile for both locales, plus the schema parser fault boundary.",
            oracle="Both real locale routes return distinct complete payloads; a missing locale is rejected.",
            anti_oracle="Independent producer snapshots or route fixtures that never cross archive verification do not count.",
            passed=passed,
            observations={"valid_route": valid_route, "missing_en_rejected": locale_fault_rejected, "zh_status": zh.status_code, "en_status": en.status_code},
        )


class RecordingPublisher:
    def __init__(self, fail_at: str | None = None) -> None:
        self.fail_at = fail_at
        self.events: list[str] = []

    def _event(self, name: str) -> None:
        self.events.append(name)
        if self.fail_at == name:
            raise PublicationError(f"injected_{name}")

    def create_immutable_release(self, *, tag: str, name: str) -> int:
        self._event("create")
        return 7

    def upload_immutable_asset(self, *, release_id: int, name: str, content: bytes) -> str:
        self._event("upload")
        return "https://github.com/fixture/repo/releases/download/tag/asset.tar.zst"

    def verify_asset(self, *, asset_url: str, size: int, sha256: str) -> None:
        self._event("verify")

    def update_stable_manifest_last(self, *, content: bytes) -> None:
        self._event("update")


def probe_publication_last() -> dict[str, object]:
    with tempfile.TemporaryDirectory(prefix="publication-", dir=EVALUATION) as raw:
        bundle, _ = _bundle(Path(raw) / "bundle")
        failure_events: dict[str, list[str]] = {}
        for point in ("create", "upload", "verify"):
            publisher = RecordingPublisher(point)
            try:
                PublicationCoordinator(publisher).publish_immutable(
                    bundle, now=datetime(2026, 8, 12, tzinfo=UTC)
                )
            except PublicationError:
                pass
            failure_events[point] = publisher.events

        immutable = RecordingPublisher()
        result = PublicationCoordinator(immutable).publish_immutable(
            bundle, now=datetime(2026, 8, 12, tzinfo=UTC)
        )
        manifest_fail = RecordingPublisher("verify")
        try:
            PublicationCoordinator(manifest_fail).publish_manifest(result.stable_manifest)
        except PublicationError:
            pass
        manifest_success = RecordingPublisher()
        PublicationCoordinator(manifest_success).publish_manifest(result.stable_manifest)
        passed = bool(
            all("update" not in events for events in failure_events.values())
            and immutable.events == ["create", "upload", "verify"]
            and manifest_fail.events == ["verify"]
            and manifest_success.events == ["verify", "update"]
        )
        return _record(
            probe_id="PROBE-P2C-PUBLICATION-LAST-001",
            invariant_id="INV-PUBLICATION-LAST",
            setup="Use a real built bundle with a recording ReleasePublisher at the production coordinator boundary.",
            fault="Fail create, upload, initial verification, and final re-verification one at a time.",
            trigger="Call PublicationCoordinator.publish_immutable and publish_manifest.",
            oracle="No pre-manifest failure records update; successful immutable publication stops before update; final command re-verifies then updates exactly once.",
            anti_oracle="Workflow step order text without exercising failure callbacks does not prove publication-last behavior.",
            passed=passed,
            observations={"failure_events": failure_events, "immutable_success": immutable.events, "manifest_verify_failure": manifest_fail.events, "manifest_success": manifest_success.events},
        )


def probe_repository_metadata() -> dict[str, object]:
    with tempfile.TemporaryDirectory(prefix="metadata-", dir=EVALUATION) as raw:
        workspace = Path(raw)
        provider = DeterministicEmbeddingProvider()
        result = _build(workspace / "index", provider=provider)
        connection = sqlite3.connect(result.database_path)
        try:
            rows = connection.execute(
                """
                SELECT s.path, s.source_type, e.evidence_class, e.start_line, e.end_line
                FROM sources s JOIN evidence e ON e.source_id = s.source_id
                ORDER BY s.path, e.start_line
                """
            ).fetchall()
            policy = json.loads(
                connection.execute(
                    "SELECT value FROM bundle_meta WHERE key='retrieval_policy'"
                ).fetchone()[0]
            )
        finally:
            connection.close()
        metadata_rows = [row for row in rows if row[0] == "pyproject.toml"]
        owner_rows = [row for row in rows if row[0] == "reponpc.yml"]
        passed = bool(
            metadata_rows
            and all(row[1] == "repository_metadata" and row[2] == "REPOSITORY_FACT" for row in metadata_rows)
            and all(row[3] >= 1 and row[4] >= row[3] for row in metadata_rows)
            and owner_rows
            and all(row[1] == "owner_assertion" and row[2] == "OWNER_ASSERTION" for row in owner_rows)
            and "repository_metadata" in policy["enabled_sources"]
            and policy["source_weights"]["repository_metadata"] == 0.9
        )
        record = _record(
            probe_id="PROBE-P2C-REPOSITORY-METADATA-001",
            invariant_id="INV-REPOSITORY-METADATA",
            setup="Build the real fixture through IndexDatabaseBuilder and inspect the resulting immutable SQLite producer output and retrieval policy.",
            fault="Use the root pyproject.toml boundary that was previously misclassified while also checking owner-authored role/summary/claims.",
            trigger="Run the production index database builder and query its sources/evidence/bundle_meta tables.",
            oracle="Root pyproject.toml is line-addressable REPOSITORY_FACT/repository_metadata, owner config remains OWNER_ASSERTION, and the configured category/weight is present.",
            anti_oracle="A consumer-only weight or classifier unit call without a produced database row does not count.",
            passed=passed,
            observations={"metadata_rows": metadata_rows, "owner_row_count": len(owner_rows), "enabled_sources": policy["enabled_sources"], "repository_metadata_weight": policy["source_weights"].get("repository_metadata")},
        )
        return record


def probe_last_known_good() -> dict[str, object]:
    with tempfile.TemporaryDirectory(prefix="lkg-", dir=EVALUATION) as raw:
        workspace = Path(raw)
        bundle, provider = _bundle(workspace / "bundle")
        verified = verify_bundle_archive(
            archive_path=bundle.archive_path,
            staging_directory=workspace / "stage-a",
            expected_outer_sha256=bundle.archive_sha256,
            expected_embedding=provider.identity(),
            max_bundle_bytes=2 * 1024 * 1024,
        )
        second_stage = workspace / "stage-b"
        shutil.copytree(verified.directory, second_stage)
        second_index = ReadOnlyIndex.open(
            second_stage / "index.sqlite", expected_embedding=provider.identity()
        )
        second_manifest = replace(
            verified.manifest,
            bundle_id="20260812T120000Z-" + "b" * 12,
        )
        second = VerifiedBundle(second_stage, second_manifest, second_index)
        runtime = RuntimeDatabase(workspace / "runtime")
        runtime.initialize()
        manager = BundleManager(
            data_directory=workspace / "runtime",
            runtime_database=runtime,
            expected_embedding=provider.identity(),
        )
        manager.activate(verified)
        before = manager.status()
        pointer = workspace / "runtime" / "bundles" / "active.json"
        pointer_before = pointer.read_bytes()
        injected = False
        try:
            manager.activate(
                second,
                before_pointer_swap=lambda: (_ for _ in ()).throw(RuntimeError("fault")),
            )
        except BundleActivationError:
            injected = True
        after = manager.status()
        passed = bool(
            injected
            and before.active_bundle_id == bundle.manifest.bundle_id
            and after.active_bundle_id == before.active_bundle_id
            and after.previous_bundle_id == before.previous_bundle_id
            and pointer.read_bytes() == pointer_before
            and not (workspace / "runtime" / "bundles" / "validated" / second_manifest.bundle_id).exists()
        )
        record = _record(
            probe_id="PROBE-P2C-LAST-KNOWN-GOOD-001",
            invariant_id="INV-LAST-KNOWN-GOOD",
            setup="Activate a real verified bundle A in BundleManager, then stage a second valid index handle as candidate B.",
            fault="Raise immediately before the atomic pointer swap for candidate B.",
            trigger="Call production BundleManager.activate twice through the real runtime SQLite/pointer boundary.",
            oracle="The callback failure rejects B, leaves active/pointer at A, preserves previous state, and removes B's promoted directory.",
            anti_oracle="Rejecting a candidate before activation or externally resetting a fixture afterward does not prove rollback at the side-effect boundary.",
            passed=passed,
            observations={"fault_observed": injected, "before": before.__dict__ if hasattr(before, "__dict__") else {"active": before.active_bundle_id, "previous": before.previous_bundle_id}, "after": after.__dict__ if hasattr(after, "__dict__") else {"active": after.active_bundle_id, "previous": after.previous_bundle_id}, "pointer_unchanged": pointer.read_bytes() == pointer_before},
        )
        if manager._active is not None:
            manager._active.index.close()
        if manager._previous is not None and manager._previous is not manager._active:
            manager._previous.index.close()
        return record


PROBES = {
    "spec_first": probe_spec_first,
    "cli_entrypoint": probe_cli_entrypoint,
    "embedding_production": probe_embedding_production,
    "formal_benchmark": probe_formal_benchmark,
    "profile_bilingual": probe_profile_bilingual,
    "publication_last": probe_publication_last,
    "repository_metadata": probe_repository_metadata,
    "last_known_good": probe_last_known_good,
}


def main() -> None:
    if len(sys.argv) != 3 or sys.argv[1] not in PROBES:
        raise SystemExit("usage: fresh_probes.py PROBE ARTIFACT")
    name, artifact_text = sys.argv[1], sys.argv[2]
    artifact = Path(artifact_text).resolve()
    if EVALUATION not in artifact.parents:
        raise SystemExit("artifact must stay in evaluation directory")
    try:
        result = PROBES[name]()
    except Exception as exc:
        result = {
            "probe_id": f"PROBE-ERROR-{name}",
            "invariant_id": "unknown",
            "status": "error",
            "exit_code": 2,
            "error_type": type(exc).__name__,
            "error": str(exc),
        }
    result["baseline_commit"] = BASELINE
    result["artifact_path"] = artifact.relative_to(ROOT).as_posix()
    result["command"] = (
        f"rtk proxy .venv/Scripts/python.exe "
        f".agent-foreman/phase2-closure/evaluation/fresh_probes.py {name} "
        f"{artifact.relative_to(ROOT).as_posix()}"
    )
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_text(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    raise SystemExit(int(result["exit_code"]))


if __name__ == "__main__":
    main()
