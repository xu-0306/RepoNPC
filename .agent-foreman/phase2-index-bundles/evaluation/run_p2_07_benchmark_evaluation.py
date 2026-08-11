"""Evaluator-only P2-07 benchmark-oracle falsification probe.

The normal benchmark artifact is produced by the real CLI.  This companion
runner copies the public questions into evaluator storage, changes one ID, and
asserts that the same CLI fails before it can emit a passing score.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[3]
EVALUATION_ROOT = Path(__file__).resolve().parent
ARTIFACT_ROOT = EVALUATION_ROOT / "artifacts"
BENCHMARK = REPO_ROOT / "evals" / "phase2" / "run_benchmark.py"
PUBLIC_QUESTIONS = REPO_ROOT / "evals" / "phase2" / "public" / "questions.json"
CONTROLLER_ORACLE = REPO_ROOT / "evals" / "phase2" / "controller" / "expected-evidence.json"
NORMAL_ARTIFACT = ARTIFACT_ROOT / "p2-07-benchmark-normal.json"
FAULTED_QUESTIONS = ARTIFACT_ROOT / "p2-07-faulted-public-questions.json"
FAULT_REPORT = ARTIFACT_ROOT / "p2-07-benchmark-id-mismatch.json"
UNWRITTEN_SCORE = ARTIFACT_ROOT / "p2-07-benchmark-id-mismatch-score.json"
EVALUATION_RECORD = EVALUATION_ROOT / "fresh-evaluation.json"

NORMAL_COMMAND = (
    "rtk proxy uv --cache-dir D:/RepoNPC/.uv-cache run --offline --no-sync "
    "--python C:/Python314/python.exe --no-managed-python python "
    "evals/phase2/run_benchmark.py --artifacts "
    ".agent-foreman/phase2-index-bundles/evaluation/artifacts/p2-07-benchmark-normal.json"
)
FAULT_COMMAND = (
    "rtk proxy uv --cache-dir D:/RepoNPC/.uv-cache run --offline --no-sync "
    "--python C:/Python314/python.exe --no-managed-python python "
    "evals/phase2/run_benchmark.py --questions "
    ".agent-foreman/phase2-index-bundles/evaluation/artifacts/p2-07-faulted-public-questions.json "
    "--oracle evals/phase2/controller/expected-evidence.json --artifacts "
    ".agent-foreman/phase2-index-bundles/evaluation/artifacts/p2-07-benchmark-id-mismatch-score.json"
)


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected object at {path}")
    return value


def main() -> int:
    ARTIFACT_ROOT.mkdir(parents=True, exist_ok=True)
    normal = _load(NORMAL_ARTIFACT)
    questions = _load(PUBLIC_QUESTIONS)
    entries = questions.get("questions")
    if not isinstance(entries, list) or not entries or not isinstance(entries[0], dict):
        raise ValueError("public questions are not a nonempty object list")
    original_id = entries[0].get("id")
    if not isinstance(original_id, str) or not original_id:
        raise ValueError("first public question has no usable ID")
    faulted_id = "mismatch-" + original_id
    entries[0] = {**entries[0], "id": faulted_id}
    questions["questions"] = entries
    FAULTED_QUESTIONS.write_text(
        json.dumps(questions, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    completed = subprocess.run(
        [
            sys.executable,
            str(BENCHMARK),
            "--questions",
            str(FAULTED_QUESTIONS),
            "--oracle",
            str(CONTROLLER_ORACLE),
            "--artifacts",
            str(UNWRITTEN_SCORE),
        ],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    expected_error = "public questions and controller oracle differ"
    rejected = completed.returncode != 0 and expected_error in (
        completed.stdout + completed.stderr
    ) and not UNWRITTEN_SCORE.exists()
    metrics = {
        "repeatable": normal.get("repeatable"),
        "recall_at_8": normal.get("recall_at_8"),
        "language_parity": normal.get("language_parity"),
        "warm_p95_ms": normal.get("warm_p95_ms"),
        "passed": normal.get("passed"),
        "oracle_isolation": normal.get("oracle_isolation"),
    }
    probe = {
        "probe_id": "PROBE-P2-07-BENCHMARK-ORACLE-ID-MISMATCH",
        "invariant_id": "INV-PHASE2-RETRIEVAL-EVALUATION",
        "setup": "The real Phase 2 benchmark first emitted a normal result from public questions and the separately stored controller expected-path oracle.",
        "fault_injection": "An evaluator-owned copy of the public questions has one ID changed so its ID set differs from the controller oracle.",
        "production_trigger": "The real evals/phase2/run_benchmark.py CLI is invoked with the faulted public copy and unchanged controller oracle.",
        "oracle": "The CLI exits nonzero with the ID-mismatch error and writes no score artifact; it must not emit a passing score.",
        "anti_oracle": "Comparing ID sets in evaluator code alone, or substituting expected paths in public questions, does not count.",
        "normal_command": NORMAL_COMMAND,
        "fault_command": FAULT_COMMAND,
        "normal_artifact_path": NORMAL_ARTIFACT.relative_to(REPO_ROOT).as_posix(),
        "artifact_path": FAULT_REPORT.relative_to(REPO_ROOT).as_posix(),
        "deterministic_result": "passed" if rejected and bool(normal.get("passed")) else "failed",
        "observed": {
            "original_question_id": original_id,
            "faulted_question_id": faulted_id,
            "fault_exit_code": completed.returncode,
            "fault_score_artifact_written": UNWRITTEN_SCORE.exists(),
            "normal_metrics": metrics,
            "controller_separation": "best_effort",
        },
    }
    fault_artifact = {
        **probe,
        "fault_stdout": completed.stdout,
        "fault_stderr": completed.stderr,
    }
    FAULT_REPORT.write_text(
        json.dumps(fault_artifact, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    evaluation = _load(EVALUATION_RECORD)
    p2_07_result = probe["deterministic_result"]
    evaluation["p2_07_evaluation"] = {
        "phase_id": "P2-07",
        "context_freshness": "fresh",
        "model_diversity": "unknown",
        "production_access": "read-only",
        "new_probes": [probe],
        "normal_benchmark": metrics,
        "controller_separation": "best_effort",
        "recommendation": "pass" if p2_07_result == "passed" else "revise",
        "deterministic_result": p2_07_result,
        "findings": [] if p2_07_result == "passed" else [
            {
                "invariant_id": "INV-PHASE2-RETRIEVAL-EVALUATION",
                "evidence_artifact": FAULT_REPORT.relative_to(REPO_ROOT).as_posix(),
                "actual": "benchmark accepted mismatched public and controller IDs or normal benchmark failed",
                "expected": "mismatch is rejected before a passing score is emitted",
            }
        ],
        "phase_completion_claim": "not made",
    }
    EVALUATION_RECORD.write_text(
        json.dumps(evaluation, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "fault_rejected": rejected,
                "normal_metrics": metrics,
                "p2_07_result": p2_07_result,
                "evaluation_path": EVALUATION_RECORD.as_posix(),
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
