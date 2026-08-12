"""Host controller for the Docker-isolated formal Phase 2 benchmark."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
import shutil
import subprocess
import tempfile
import uuid
from pathlib import Path
from typing import Any, cast

REPOSITORY_ROOT = Path(__file__).parents[2]
FIXTURE_CONFIG = REPOSITORY_ROOT / "tests" / "fixtures" / "phase2" / "reponpc.yml"
FIXTURE_REPOSITORY = REPOSITORY_ROOT / "tests" / "fixtures" / "repos" / "reponpc-demo"
PUBLIC_QUESTIONS = Path(__file__).parent / "public" / "questions.json"
CONTROLLER_ORACLE = Path(__file__).parent / "controller" / "expected-evidence.json"
DOCKERFILE = Path(__file__).parent / "Dockerfile"
CANDIDATE_RUNNER = Path(__file__).parent / "candidate_runner.py"
DEFAULT_IMAGE_TAG = "reponpc-phase2-benchmark:local"
CPU_NANOSECONDS = 4_000_000_000
MEMORY_BYTES = 8 * 1024 * 1024 * 1024
THRESHOLDS = {"recall_at_8": 0.85, "language_parity": 0.90, "warm_p95_ms": 750.0}
_FORBIDDEN_CANDIDATE_KEYS = {
    "acceptable_paths",
    "expected_path_count",
    "expected_paths",
    "formal_acceptance",
    "formal_blockers",
    "hit",
    "oracle",
    "oracle_isolation_enforced",
    "passed",
    "provider_is_production",
    "reference_host_verified",
    "repeatable",
    "thresholds",
}


def run(
    *,
    artifacts_path: Path,
    warmup_rounds: int = 2,
    measurement_rounds: int = 5,
    image_tag: str = DEFAULT_IMAGE_TAG,
) -> dict[str, object]:
    """Build the candidate image, enforce resources/mounts, then score on the host."""

    questions, _, canonical_inputs = _canonical_inputs()
    if any(
        isinstance(value, bool) or not isinstance(value, int) or value <= 0
        for value in (warmup_rounds, measurement_rounds)
    ):
        raise ValueError("round counts must be positive integers")
    evidence_directory = artifacts_path.parent / "formal-benchmark"
    evidence_directory.mkdir(parents=True, exist_ok=True)
    container_name = f"reponpc-p2-{uuid.uuid4().hex}"
    with tempfile.TemporaryDirectory(prefix="reponpc-p2-formal-") as temporary:
        workspace = Path(temporary)
        build_context = workspace / "build-context"
        public_root = workspace / "public"
        output_root = workspace / "output"
        _prepare_build_context(build_context)
        _prepare_public_mount(public_root)
        output_root.mkdir()
        build = _docker(
            [
                "build",
                "--pull",
                "--file",
                str(build_context / "Dockerfile"),
                "--tag",
                image_tag,
                str(build_context),
            ],
            timeout=3600,
            check=False,
        )
        (evidence_directory / "docker-build.txt").write_text(
            build.stdout + build.stderr, encoding="utf-8"
        )
        if build.returncode != 0:
            raise RuntimeError("formal benchmark image build failed")
        image_inspect = _docker_json(["image", "inspect", image_tag])[0]
        create = _docker(
            [
                "create",
                "--name",
                container_name,
                "--cpus=4",
                "--memory=8g",
                "--network=none",
                "--mount",
                f"type=bind,source={public_root},target=/input,readonly",
                "--mount",
                f"type=bind,source={output_root},target=/output",
                image_tag,
                "--questions",
                "/input/questions.json",
                "--repository",
                "/input/repository",
                "--config",
                "/input/reponpc.yml",
                "--output",
                "/output/candidate.json",
                "--warmup-rounds",
                str(warmup_rounds),
                "--measurement-rounds",
                str(measurement_rounds),
            ],
            timeout=120,
        )
        if not create.stdout.strip():
            raise RuntimeError("formal benchmark container creation failed")
        try:
            created_inspect = _docker_json(["inspect", container_name])[0]
            started = _docker(["start", "--attach", container_name], timeout=3600, check=False)
            (evidence_directory / "candidate-console.txt").write_text(
                started.stdout + started.stderr, encoding="utf-8"
            )
            container_inspect = _docker_json(["inspect", container_name])[0]
            candidate_exit_code = int(container_inspect.get("State", {}).get("ExitCode", -1))
            access_probe = _run_access_probe(
                image_tag=image_tag,
                public_root=public_root,
                output_root=output_root,
            )
            _write_json(evidence_directory / "container-created-inspect.json", created_inspect)
            _write_json(evidence_directory / "container-inspect.json", container_inspect)
            _write_json(evidence_directory / "image-inspect.json", image_inspect)
            _write_json(evidence_directory / "access-probe.json", access_probe)
            candidate_path = output_root / "candidate.json"
            if candidate_exit_code != 0 or not candidate_path.is_file():
                raise RuntimeError("formal benchmark candidate failed")
            candidate = json.loads(candidate_path.read_text(encoding="utf-8"))
            validate_candidate_output(candidate, questions)
            _write_json(evidence_directory / "candidate.json", candidate)
            host_provenance = _host_provenance()
            _write_json(evidence_directory / "provenance.json", host_provenance)
            report = derive_formal_report(
                candidate=candidate,
                container_inspect=container_inspect,
                image_inspect=image_inspect,
                access_probe=access_probe,
                host_provenance=host_provenance,
                candidate_exit_code=candidate_exit_code,
            )
            if report["inputs"] != canonical_inputs:
                raise RuntimeError("formal benchmark canonical inputs changed during execution")
            _write_json(
                evidence_directory / "timings.json",
                {"timings_ns": candidate["timings_ns"]},
            )
            _write_json(artifacts_path, report)
            return report
        finally:
            _docker(["rm", "--force", container_name], timeout=120, check=False)


def validate_candidate_output(candidate: object, questions: list[dict[str, Any]]) -> None:
    """Reject any candidate-supplied oracle, threshold, or pass claim."""

    if not isinstance(candidate, dict) or set(candidate) != {
        "schema_name",
        "schema_version",
        "provider",
        "builds",
        "results",
        "timings_ns",
        "warmup_rounds",
        "measurement_rounds",
        "indexed",
        "provenance",
    }:
        raise ValueError("candidate shape is invalid")
    if candidate["schema_name"] != "reponpc/phase2-candidate" or candidate["schema_version"] != 1:
        raise ValueError("candidate schema is invalid")
    _reject_forbidden_keys(candidate)
    provider = candidate["provider"]
    if not isinstance(provider, dict) or set(provider) != {
        "adapter",
        "model_id",
        "dimension",
        "normalized",
        "query_prefix",
        "passage_prefix",
    }:
        raise ValueError("candidate provider is invalid")
    builds = candidate["builds"]
    if not isinstance(builds, list) or len(builds) != 2:
        raise ValueError("candidate builds are invalid")
    for build in builds:
        if not isinstance(build, dict) or set(build) != {
            "manifest_sha256",
            "archive_sha256",
            "database_sha256",
        }:
            raise ValueError("candidate build observation is invalid")
        if any(
            not isinstance(value, str)
            or len(value) != 64
            or any(character not in "0123456789abcdef" for character in value)
            for value in build.values()
        ):
            raise ValueError("candidate build digest is invalid")
    question_by_id = {str(item["id"]): item for item in questions}
    results = candidate["results"]
    if not isinstance(results, list) or len(results) != len(questions):
        raise ValueError("candidate results are invalid")
    seen: set[str] = set()
    for result in results:
        if not isinstance(result, dict) or set(result) != {
            "id",
            "pair_id",
            "locale",
            "retrieved_evidence_ids",
            "retrieved_paths",
        }:
            raise ValueError("candidate result shape is invalid")
        question_id = result["id"]
        if (
            not isinstance(question_id, str)
            or question_id in seen
            or question_id not in question_by_id
        ):
            raise ValueError("candidate result identity is invalid")
        expected_question = question_by_id[question_id]
        if (
            result["pair_id"] != expected_question["pair_id"]
            or result["locale"] != expected_question["locale"]
        ):
            raise ValueError("candidate public metadata differs")
        for key in ("retrieved_evidence_ids", "retrieved_paths"):
            values = result[key]
            if (
                not isinstance(values, list)
                or len(values) > 8
                or any(not isinstance(value, str) or not value for value in values)
            ):
                raise ValueError("candidate retrieval values are invalid")
        seen.add(question_id)
    timings = candidate["timings_ns"]
    expected_samples = len(questions) * _positive_integer(candidate["measurement_rounds"])
    if (
        not isinstance(timings, list)
        or len(timings) != expected_samples
        or any(
            isinstance(value, bool) or not isinstance(value, int) or value <= 0 for value in timings
        )
    ):
        raise ValueError("candidate timings are invalid")
    _positive_integer(candidate["warmup_rounds"])
    if not isinstance(candidate["indexed"], dict) or not isinstance(candidate["provenance"], dict):
        raise ValueError("candidate metadata is invalid")


def derive_formal_report(
    *,
    candidate: dict[str, object],
    container_inspect: dict[str, object],
    image_inspect: dict[str, object],
    access_probe: dict[str, object],
    host_provenance: dict[str, object],
    candidate_exit_code: int,
) -> dict[str, object]:
    """Derive every acceptance boolean from raw host/candidate observations."""

    questions, expectations, canonical_inputs = _canonical_inputs()
    validate_candidate_output(candidate, questions)
    provider = candidate["provider"]
    expected_provider = {
        "adapter": "local_sentence_transformers",
        "model_id": "intfloat/multilingual-e5-small",
        "dimension": 384,
        "normalized": True,
        "query_prefix": "query: ",
        "passage_prefix": "passage: ",
    }
    provenance = candidate["provenance"]
    provider_is_production = bool(
        provider == expected_provider
        and isinstance(provenance, dict)
        and all(provenance.get(key) for key in ("sentence_transformers", "torch"))
    )
    builds = candidate["builds"]
    repeatable = bool(isinstance(builds, list) and builds[0] == builds[1])
    scored_results: list[dict[str, object]] = []
    candidate_results = cast(list[dict[str, object]], candidate["results"])
    for result in candidate_results:
        expected_paths = expectations[str(result["id"])]
        retrieved_paths = tuple(str(path) for path in cast(list[object], result["retrieved_paths"]))
        scored_results.append(
            {
                **result,
                "hit": any(path in expected_paths for path in retrieved_paths),
                "expected_path_count": len(expected_paths),
            }
        )
    recall = sum(bool(result["hit"]) for result in scored_results) / len(scored_results)
    pair_results = _pair_results(scored_results)
    parity = sum(bool(result["equivalent"]) for result in pair_results) / len(pair_results)
    timings = cast(list[int], candidate["timings_ns"])
    p95_ms = _p95_ms(timings)
    resource_limits_verified, network_disabled, mounts_verified = _container_evidence(
        container_inspect
    )
    probe_clean = bool(
        access_probe.get("oracle_paths_readable") is False
        and access_probe.get("oracle_named_files") == []
        and access_probe.get("input_files") == ["questions.json", "reponpc.yml", "repository"]
    )
    oracle_isolation_enforced = bool(mounts_verified and probe_clean)
    image_id = image_inspect.get("Id")
    image_digest_recorded = isinstance(image_id, str) and image_id.startswith("sha256:")
    reference_host_verified = bool(
        resource_limits_verified
        and network_disabled
        and image_digest_recorded
        and candidate_exit_code == 0
    )
    blockers: list[str] = []
    if not provider_is_production:
        blockers.append("production_provider_not_verified")
    if not oracle_isolation_enforced:
        blockers.append("oracle_isolation_not_enforced")
    if not resource_limits_verified:
        blockers.append("resource_limits_not_verified")
    if not network_disabled:
        blockers.append("candidate_network_not_disabled")
    if not image_digest_recorded or candidate_exit_code != 0:
        blockers.append("reference_host_not_verified")
    if not repeatable:
        blockers.append("build_not_repeatable")
    if recall < THRESHOLDS["recall_at_8"]:
        blockers.append("recall_below_threshold")
    if parity < THRESHOLDS["language_parity"]:
        blockers.append("language_parity_below_threshold")
    if p95_ms > THRESHOLDS["warm_p95_ms"]:
        blockers.append("warm_p95_above_threshold")
    formal_acceptance = not blockers
    return {
        "schema_name": "reponpc/phase2-benchmark",
        "schema_version": 2,
        "inputs": canonical_inputs,
        "oracle_isolation": "enforced" if oracle_isolation_enforced else "failed",
        "provider": provider,
        "provider_is_production": provider_is_production,
        "oracle_isolation_enforced": oracle_isolation_enforced,
        "reference_host_verified": reference_host_verified,
        "reference_host": {
            "target": {"cpu_cores": 4, "memory_gib": 8},
            "image_id": image_id,
            "image_repo_digests": image_inspect.get("RepoDigests", []),
            "container_exit_code": candidate_exit_code,
            "provenance": host_provenance,
            "candidate_provenance": provenance,
        },
        "resource_limits_verified": resource_limits_verified,
        "candidate_network_disabled": network_disabled,
        "mount_isolation_verified": mounts_verified,
        "thresholds": THRESHOLDS,
        "warmup_rounds": candidate["warmup_rounds"],
        "measurement_rounds": candidate["measurement_rounds"],
        "timing_sample_count": len(timings),
        "timing_policy": "untimed_warmup_then_full_measurement_rounds",
        "question_count": len(questions),
        "pair_count": len(pair_results),
        "distinct_expected_path_count": len(
            {path for paths in expectations.values() for path in paths}
        ),
        "indexed": candidate["indexed"],
        "repeatable": repeatable,
        "recall_at_8": recall,
        "language_parity": parity,
        "warm_p95_ms": p95_ms,
        "results": scored_results,
        "pair_results": pair_results,
        "formal_blockers": blockers,
        "formal_acceptance": formal_acceptance,
        "passed": formal_acceptance,
    }


def _prepare_build_context(directory: Path) -> None:
    directory.mkdir()
    for source in (
        REPOSITORY_ROOT / "pyproject.toml",
        REPOSITORY_ROOT / "uv.lock",
        REPOSITORY_ROOT / "README.md",
    ):
        shutil.copy2(source, directory / source.name)
    shutil.copytree(
        REPOSITORY_ROOT / "src",
        directory / "src",
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
    )
    shutil.copy2(DOCKERFILE, directory / "Dockerfile")
    shutil.copy2(CANDIDATE_RUNNER, directory / "candidate_runner.py")


def _prepare_public_mount(directory: Path) -> None:
    directory.mkdir()
    shutil.copytree(FIXTURE_REPOSITORY, directory / "repository")
    shutil.copy2(FIXTURE_CONFIG, directory / "reponpc.yml")
    shutil.copy2(PUBLIC_QUESTIONS, directory / "questions.json")


def _run_access_probe(*, image_tag: str, public_root: Path, output_root: Path):
    probe = (
        "import json,os; from pathlib import Path; "
        "checks=[Path('/controller/expected-evidence.json'),Path('/oracle/expected-evidence.json'),"
        "Path('/input/expected-evidence.json')]; "
        "named=[str(p) for root in (Path('/app'),Path('/input')) for p in root.rglob('*') "
        "if p.name=='expected-evidence.json']; "
        "print(json.dumps({'oracle_paths_readable':any(p.exists() and os.access(p,os.R_OK) "
        "for p in checks),'oracle_named_files':named,'input_files':sorted(p.name for p in "
        "Path('/input').iterdir())}))"
    )
    result = _docker(
        [
            "run",
            "--rm",
            "--cpus=4",
            "--memory=8g",
            "--network=none",
            "--mount",
            f"type=bind,source={public_root},target=/input,readonly",
            "--mount",
            f"type=bind,source={output_root},target=/output",
            "--entrypoint",
            "/app/.venv/bin/python",
            image_tag,
            "-c",
            probe,
        ],
        timeout=300,
    )
    value = json.loads(result.stdout)
    if not isinstance(value, dict):
        raise RuntimeError("oracle access probe returned invalid output")
    return value


def _container_evidence(container: dict[str, object]) -> tuple[bool, bool, bool]:
    host = container.get("HostConfig")
    mounts = container.get("Mounts")
    if not isinstance(host, dict) or not isinstance(mounts, list):
        return False, False, False
    resources = bool(host.get("NanoCpus") == CPU_NANOSECONDS and host.get("Memory") == MEMORY_BYTES)
    network = host.get("NetworkMode") == "none"
    observed: dict[str, tuple[object, object]] = {}
    for mount in mounts:
        if isinstance(mount, dict) and isinstance(mount.get("Destination"), str):
            observed[mount["Destination"]] = (mount.get("Type"), mount.get("RW"))
    mount_isolation = observed == {"/input": ("bind", False), "/output": ("bind", True)}
    return resources, network, mount_isolation


def _pair_results(results: list[dict[str, object]]) -> list[dict[str, object]]:
    pairs: dict[str, list[dict[str, object]]] = {}
    for result in results:
        pairs.setdefault(str(result["pair_id"]), []).append(result)
    paired: list[dict[str, object]] = []
    for pair_id, members in sorted(pairs.items()):
        if len(members) != 2 or {member["locale"] for member in members} != {"en", "zh-TW"}:
            raise ValueError("question pairs are invalid")
        paired.append(
            {
                "pair_id": pair_id,
                "equivalent": all(bool(member["hit"]) for member in members),
                "both_hit": all(bool(member["hit"]) for member in members),
            }
        )
    return paired


def _validate_public_and_oracle(
    questions: list[dict[str, Any]], expectations: dict[str, tuple[str, ...]]
) -> None:
    ids: set[str] = set()
    pairs: dict[str, list[str]] = {}
    for item in questions:
        if set(item) != {"id", "pair_id", "locale", "question"}:
            raise ValueError("question shape is invalid")
        question_id = item["id"]
        pair_id = item["pair_id"]
        locale = item["locale"]
        if (
            not isinstance(question_id, str)
            or not question_id
            or question_id in ids
            or not isinstance(pair_id, str)
            or not pair_id
            or locale not in {"en", "zh-TW"}
            or not isinstance(item["question"], str)
            or not item["question"].strip()
        ):
            raise ValueError("question metadata is invalid")
        ids.add(question_id)
        pairs.setdefault(pair_id, []).append(locale)
    if ids != set(expectations):
        raise ValueError("public questions and host oracle differ")
    if any(not paths or any(not path for path in paths) for paths in expectations.values()):
        raise ValueError("host expectations are invalid")
    if any(sorted(locales) != ["en", "zh-TW"] for locales in pairs.values()):
        raise ValueError("every pair requires both locales")
    if len(pairs) < 10 or len({path for paths in expectations.values() for path in paths}) < 5:
        raise ValueError("formal corpus is too small")


def _reject_forbidden_keys(value: object) -> None:
    if isinstance(value, dict):
        for key, nested in value.items():
            if str(key).casefold() in _FORBIDDEN_CANDIDATE_KEYS:
                raise ValueError("candidate contains host-only fields")
            _reject_forbidden_keys(nested)
    elif isinstance(value, list):
        for nested in value:
            _reject_forbidden_keys(nested)


def _positive_integer(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError("value must be a positive integer")
    return value


def _p95_ms(timings_ns: list[int]) -> float:
    ordered = sorted(timings_ns)
    index = max(0, math.ceil(len(ordered) * 0.95) - 1)
    return ordered[index] / 1_000_000


def _host_provenance() -> dict[str, object]:
    docker_version = _docker(["version", "--format", "{{json .}}"], timeout=120)
    return {
        "python": platform.python_version(),
        "platform": platform.platform(aliased=True),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "docker": json.loads(docker_version.stdout),
    }


def _docker_json(arguments: list[str]):
    result = _docker(arguments, timeout=120)
    value = json.loads(result.stdout)
    if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
        raise RuntimeError("Docker inspection returned invalid JSON")
    return value


def _docker(
    arguments: list[str],
    *,
    timeout: int,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        ["docker", *arguments],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
    )
    if check and completed.returncode != 0:
        raise RuntimeError("Docker command failed")
    return completed


def _canonical_inputs() -> tuple[list[dict[str, Any]], dict[str, tuple[str, ...]], dict[str, str]]:
    question_bytes = PUBLIC_QUESTIONS.read_bytes()
    oracle_bytes = CONTROLLER_ORACLE.read_bytes()
    question_payload = json.loads(question_bytes)
    oracle_payload = json.loads(oracle_bytes)
    questions = question_payload.get("questions")
    oracle_records = oracle_payload.get("expectations")
    if not isinstance(questions, list) or not all(isinstance(item, dict) for item in questions):
        raise ValueError("questions must be an object list")
    if not isinstance(oracle_records, list) or not all(
        isinstance(item, dict) for item in oracle_records
    ):
        raise ValueError("expectations must be an object list")
    expectations = {
        str(item["id"]): tuple(str(path) for path in item["acceptable_paths"])
        for item in oracle_records
    }
    _validate_public_and_oracle(questions, expectations)
    return (
        questions,
        expectations,
        {
            "questions_path": PUBLIC_QUESTIONS.relative_to(REPOSITORY_ROOT).as_posix(),
            "questions_sha256": hashlib.sha256(question_bytes).hexdigest(),
            "oracle_path": CONTROLLER_ORACLE.relative_to(REPOSITORY_ROOT).as_posix(),
            "oracle_sha256": hashlib.sha256(oracle_bytes).hexdigest(),
        },
    )


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the formal RepoNPC Phase 2 benchmark.")
    parser.add_argument("--artifacts", type=Path, required=True)
    parser.add_argument("--warmup-rounds", type=int, default=2)
    parser.add_argument("--measurement-rounds", type=int, default=5)
    parser.add_argument("--image-tag", default=DEFAULT_IMAGE_TAG)
    args = parser.parse_args()
    report = run(
        artifacts_path=args.artifacts,
        warmup_rounds=args.warmup_rounds,
        measurement_rounds=args.measurement_rounds,
        image_tag=args.image_tag,
    )
    if not bool(report["formal_acceptance"]):
        raise SystemExit("phase2 formal benchmark did not pass")


if __name__ == "__main__":
    main()
