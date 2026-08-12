"""Host-only scoring and Docker oracle-isolation contract for the formal benchmark."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

from evals.phase2.run_benchmark import derive_formal_report, validate_candidate_output

ROOT = Path(__file__).parents[2]
QUESTIONS = ROOT / "evals" / "phase2" / "public" / "questions.json"
ORACLE = ROOT / "evals" / "phase2" / "controller" / "expected-evidence.json"


def _inputs():
    questions = json.loads(QUESTIONS.read_text(encoding="utf-8"))["questions"]
    expectations = {
        item["id"]: tuple(item["acceptable_paths"])
        for item in json.loads(ORACLE.read_text(encoding="utf-8"))["expectations"]
    }
    return questions, expectations


def _candidate() -> dict[str, object]:
    questions, expectations = _inputs()
    return {
        "schema_name": "reponpc/phase2-candidate",
        "schema_version": 1,
        "provider": {
            "adapter": "local_sentence_transformers",
            "model_id": "intfloat/multilingual-e5-small",
            "dimension": 384,
            "normalized": True,
            "query_prefix": "query: ",
            "passage_prefix": "passage: ",
        },
        "builds": [
            {
                "manifest_sha256": "a" * 64,
                "archive_sha256": "b" * 64,
                "database_sha256": "c" * 64,
            },
            {
                "manifest_sha256": "a" * 64,
                "archive_sha256": "b" * 64,
                "database_sha256": "c" * 64,
            },
        ],
        "results": [
            {
                "id": item["id"],
                "pair_id": item["pair_id"],
                "locale": item["locale"],
                "retrieved_evidence_ids": [f"evidence-{index}"],
                "retrieved_paths": [expectations[item["id"]][0]],
            }
            for index, item in enumerate(questions)
        ],
        "timings_ns": [1_000_000] * (len(questions) * 5),
        "warmup_rounds": 2,
        "measurement_rounds": 5,
        "indexed": {"repositories": 1, "sources": 10, "evidence_records": 20},
        "provenance": {
            "python": "3.14.7",
            "numpy": "2.4.3",
            "sentence_transformers": "5.7.0",
            "torch": "2.13.0",
            "platform": "linux",
        },
    }


def _inspect() -> dict[str, object]:
    return {
        "HostConfig": {
            "NanoCpus": 4_000_000_000,
            "Memory": 8 * 1024 * 1024 * 1024,
            "NetworkMode": "none",
        },
        "Mounts": [
            {"Type": "bind", "Destination": "/input", "RW": False},
            {"Type": "bind", "Destination": "/output", "RW": True},
        ],
        "State": {"ExitCode": 0},
    }


def test_host_derives_formal_acceptance_from_raw_candidate_and_docker_evidence() -> None:
    questions, _ = _inputs()
    candidate = _candidate()
    validate_candidate_output(candidate, questions)

    report = derive_formal_report(
        candidate=candidate,
        container_inspect=_inspect(),
        image_inspect={"Id": "sha256:" + "d" * 64, "RepoDigests": []},
        access_probe={
            "oracle_paths_readable": False,
            "oracle_named_files": [],
            "input_files": ["questions.json", "reponpc.yml", "repository"],
        },
        host_provenance={"docker": "fixture", "host": "fixture"},
        candidate_exit_code=0,
    )

    assert report["provider_is_production"] is True
    assert report["oracle_isolation_enforced"] is True
    assert report["reference_host_verified"] is True
    assert report["repeatable"] is True
    assert report["recall_at_8"] == 1.0
    assert report["language_parity"] == 1.0
    assert report["formal_blockers"] == []
    assert report["formal_acceptance"] is True
    assert report["inputs"] == {
        "questions_path": "evals/phase2/public/questions.json",
        "questions_sha256": hashlib.sha256(QUESTIONS.read_bytes()).hexdigest(),
        "oracle_path": "evals/phase2/controller/expected-evidence.json",
        "oracle_sha256": hashlib.sha256(ORACLE.read_bytes()).hexdigest(),
    }


def test_candidate_cannot_supply_oracle_or_acceptance_booleans() -> None:
    questions, _ = _inputs()
    candidate = _candidate()
    candidate["formal_acceptance"] = True

    with pytest.raises(ValueError):
        validate_candidate_output(candidate, questions)


def test_missing_limit_or_probe_evidence_blocks_host_acceptance() -> None:
    inspect = _inspect()
    inspect["HostConfig"]["Memory"] = 1024  # type: ignore[index]

    report = derive_formal_report(
        candidate=_candidate(),
        container_inspect=inspect,
        image_inspect={"Id": "sha256:" + "d" * 64, "RepoDigests": []},
        access_probe={"oracle_paths_readable": True, "oracle_named_files": ["forbidden"]},
        host_provenance={"docker": "fixture", "host": "fixture"},
        candidate_exit_code=0,
    )

    assert report["formal_acceptance"] is False
    assert "resource_limits_not_verified" in report["formal_blockers"]
    assert "oracle_isolation_not_enforced" in report["formal_blockers"]
    assert report["oracle_isolation"] == "failed"


def test_formal_controller_hard_binds_reviewed_questions_and_oracle(tmp_path: Path) -> None:
    candidate = _candidate()
    for result in candidate["results"]:  # type: ignore[union-attr]
        result["retrieved_paths"] = ["attacker-selected.md"]

    report = derive_formal_report(
        candidate=candidate,
        container_inspect=_inspect(),
        image_inspect={"Id": "sha256:" + "d" * 64, "RepoDigests": []},
        access_probe={
            "oracle_paths_readable": False,
            "oracle_named_files": [],
            "input_files": ["questions.json", "reponpc.yml", "repository"],
        },
        host_provenance={"docker": "fixture", "host": "fixture"},
        candidate_exit_code=0,
    )

    assert report["recall_at_8"] == 0.0
    assert report["formal_acceptance"] is False
    assert "recall_below_threshold" in report["formal_blockers"]

    artifact = tmp_path / "must-not-exist.json"
    completed = subprocess.run(
        [
            sys.executable,
            str(ROOT / "evals" / "phase2" / "run_benchmark.py"),
            "--artifacts",
            str(artifact),
            "--oracle",
            str(tmp_path / "attacker-oracle.json"),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    assert completed.returncode == 2
    assert "unrecognized arguments: --oracle" in completed.stderr
    assert not artifact.exists()


def test_benchmark_image_never_copies_controller_or_oracle() -> None:
    dockerfile = (ROOT / "evals" / "phase2" / "Dockerfile").read_text(encoding="utf-8")
    lowered = dockerfile.casefold()

    assert "controller" not in lowered
    assert "expected-evidence" not in lowered
    assert "copy candidate_runner.py" in lowered
    assert "--extra indexer" in dockerfile
