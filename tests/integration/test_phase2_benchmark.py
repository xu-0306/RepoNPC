"""Host-only scoring and Docker oracle-isolation contract for the formal benchmark."""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import subprocess
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any, cast

import pytest

from evals.phase2 import run_benchmark
from evals.phase2.run_benchmark import (
    _manifest_sha256,
    _provider_source_sha256,
    derive_formal_report,
    validate_candidate_output,
)
from reponpc.providers.builtin_artifacts import BuiltinArtifactError, builtin_embedding_identity

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


def _candidate() -> dict[str, Any]:
    questions, expectations = _inputs()
    return {
        "schema_name": "reponpc/phase2-candidate",
        "schema_version": 1,
        "provider": asdict(builtin_embedding_identity()),
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
            **{
                name: importlib.metadata.version(name)
                for name in ("numpy", "onnxruntime", "tokenizers")
            },
            "torch_imported": False,
            "artifact_manifest_sha256": _manifest_sha256(),
            "provider_source_sha256": _provider_source_sha256(),
            "platform": "linux",
        },
    }


def _inspect() -> dict[str, Any]:
    return {
        "HostConfig": {
            "NanoCpus": 4_000_000_000,
            "Memory": 8 * 1024 * 1024 * 1024,
            "NetworkMode": "none",
            "ReadonlyRootfs": True,
        },
        "Mounts": [
            {"Type": "bind", "Destination": "/input", "RW": False},
            {"Type": "bind", "Destination": "/output", "RW": True},
            {"Type": "bind", "Destination": "/model", "RW": False},
            {"Type": "tmpfs", "Destination": "/var/lib/reponpc", "RW": True},
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
    assert "resource_limits_not_verified" in cast(list[str], report["formal_blockers"])
    assert "oracle_isolation_not_enforced" in cast(list[str], report["formal_blockers"])
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
    assert "recall_below_threshold" in cast(list[str], report["formal_blockers"])

    artifact = tmp_path / "must-not-exist.json"
    completed = subprocess.run(
        [
            sys.executable,
            str(ROOT / "evals" / "phase2" / "run_benchmark.py"),
            "--artifacts",
            str(artifact),
            "--model-dir",
            str(tmp_path / "model"),
            "--runtime-image",
            "local-fixture-image",
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
    assert "candidate_runner.py /app/candidate_runner.py" in lowered
    assert "from ${runtime_image}" in lowered
    assert "sentence_transformers" not in lowered and "--extra indexer" not in lowered
    assert "run " not in lowered


def _report(candidate=None, inspect=None) -> dict[str, Any]:
    return cast(
        dict[str, Any],
        derive_formal_report(
            candidate=_candidate() if candidate is None else candidate,
            container_inspect=_inspect() if inspect is None else inspect,
            image_inspect={"Id": "sha256:" + "d" * 64, "RepoDigests": []},
            access_probe={
                "oracle_paths_readable": False,
                "oracle_named_files": [],
                "input_files": ["questions.json", "reponpc.yml", "repository"],
            },
            host_provenance={"host": "fixture"},
            candidate_exit_code=0,
        ),
    )


@pytest.mark.parametrize("field", ["adapter", "model_id", "dimension", "query_prefix"])
def test_wrong_provider_identity_cannot_be_formally_accepted(field: str) -> None:
    candidate = _candidate()
    candidate["provider"][field] = "different"  # type: ignore[index]
    report = _report(candidate)
    assert report["provider_is_production"] is False
    assert "production_provider_not_verified" in report["formal_blockers"]


@pytest.mark.parametrize(
    "field,value",
    [
        ("onnxruntime", "missing"),
        ("tokenizers", "missing"),
        ("torch_imported", True),
        ("artifact_manifest_sha256", "0" * 64),
        ("provider_source_sha256", {}),
    ],
)
def test_missing_or_changed_production_provenance_blocks_acceptance(field, value) -> None:
    candidate = _candidate()
    candidate["provenance"][field] = value  # type: ignore[index]
    assert _report(candidate)["formal_acceptance"] is False


@pytest.mark.parametrize("change", ["writable_model", "missing_model", "extra", "duplicate"])
def test_model_and_input_mounts_are_strictly_isolated(change: str) -> None:
    inspect = _inspect()
    mounts = inspect["Mounts"]
    if change == "writable_model":
        mounts[2]["RW"] = True  # type: ignore[index]
    elif change == "missing_model":
        mounts.pop(2)  # type: ignore[union-attr]
    elif change == "extra":
        mounts.append({"Type": "bind", "Destination": "/owner", "RW": False})  # type: ignore[union-attr]
    else:
        mounts.append(mounts[0])  # type: ignore[union-attr,index]
    assert _report(inspect=inspect)["oracle_isolation_enforced"] is False


def test_invalid_model_fails_before_any_docker_command(tmp_path: Path, monkeypatch) -> None:
    def reject(_):
        raise BuiltinArtifactError("builtin_artifact_invalid")

    def forbidden(*args, **kwargs):
        pytest.fail("invalid artifacts must not reach Docker")

    monkeypatch.setattr(run_benchmark, "verify_builtin_artifacts", reject)
    monkeypatch.setattr(run_benchmark, "_docker", forbidden)
    with pytest.raises(BuiltinArtifactError):
        run_benchmark.run(
            artifacts_path=tmp_path / "report.json",
            model_dir=tmp_path / "unverified-model",
            runtime_image="local-fixture-image",
        )
    assert not (tmp_path / "report.json").exists()


def test_public_inputs_exclude_model_and_oracle(tmp_path: Path) -> None:
    public = tmp_path / "input"
    run_benchmark._prepare_public_mount(public)
    assert sorted(p.name for p in public.iterdir()) == [
        "questions.json",
        "reponpc.yml",
        "repository",
    ]
    assert not list(public.rglob("expected-evidence.json"))
    assert not list(public.rglob("*.onnx"))


def test_candidate_sprite_passes_current_production_verifier() -> None:
    from evals.phase2.candidate_runner import _canonical_fixture_sprite
    from reponpc.cards.assets import validate_sprite

    sprite = _canonical_fixture_sprite()
    assert validate_sprite(sprite).content == sprite
