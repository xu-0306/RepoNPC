from __future__ import annotations

import json

import pytest

from evals.phase2 import run_benchmark
from evals.phase2.run_benchmark import (
    FixtureEmbeddingProvider,
    _pair_results,
    _retrieve,
    _validate_inputs,
)


def _valid() -> tuple[list[dict[str, str]], dict[str, tuple[str, ...]]]:
    questions = []
    expectations: dict[str, tuple[str, ...]] = {}
    for number in range(10):
        for locale in ("en", "zh-TW"):
            identifier = f"q{number}-{locale}"
            questions.append(
                {
                    "id": identifier,
                    "pair_id": f"p{number}",
                    "locale": locale,
                    "question": "question",
                }
            )
            expectations[identifier] = (f"src/{number % 5}.py",)
    return questions, expectations


def test_fixture_identity_is_truthful() -> None:
    identity = FixtureEmbeddingProvider().identity()
    assert (identity.adapter, identity.model_id) == (
        "deterministic_fixture",
        "sha256-token-hash-v1",
    )


def test_pair_parity_requires_both_hits_not_path_overlap() -> None:
    result = _pair_results(
        [
            {"pair_id": "p", "locale": "en", "hit": True, "retrieved_paths": ["wrong"]},
            {"pair_id": "p", "locale": "zh-TW", "hit": False, "retrieved_paths": ["wrong"]},
        ]
    )[0]
    assert result["equivalent"] is False and result["both_hit"] is False


def test_valid_synthetic_inputs_pass() -> None:
    questions, expectations = _valid()
    _validate_inputs(questions, expectations)


@pytest.mark.parametrize(
    "kind",
    ["duplicate", "locale", "question", "pair", "mismatch", "paths", "pairing", "pairs", "targets"],
)
def test_invalid_inputs_fail(kind: str) -> None:
    questions, expectations = _valid()
    if kind == "duplicate":
        questions[1]["id"] = questions[0]["id"]
    elif kind == "locale":
        questions[0]["locale"] = "fr"
    elif kind == "question":
        questions[0]["question"] = ""
    elif kind == "pair":
        questions[0]["pair_id"] = ""
    elif kind == "mismatch":
        expectations.pop(next(iter(expectations)))
    elif kind == "paths":
        expectations[next(iter(expectations))] = ("",)
    elif kind == "pairing":
        questions[1]["locale"] = "en"
    elif kind == "pairs":
        questions = questions[:18]
        expectations = {q["id"]: expectations[q["id"]] for q in questions}
    else:
        expectations = {key: ("one.py",) for key in expectations}
    with pytest.raises(ValueError):
        _validate_inputs(questions, expectations)


def test_retrieve_warmup_and_measurement_round_accounting() -> None:
    questions, expectations = _valid()
    questions = questions[:10]
    expectations = {item["id"]: expectations[item["id"]] for item in questions}

    class Index:
        def __init__(self) -> None:
            self.calls = 0

        def hybrid_candidates(self, *args: object, **kwargs: object) -> list[str]:
            self.calls += 1
            return []

        def evidence(self, evidence_id: str) -> None:
            return None

    class Verified:
        def __init__(self) -> None:
            self.index = Index()

    verified = Verified()
    _, warmup_timings = _retrieve(
        verified, FixtureEmbeddingProvider(), questions, expectations, timed=False
    )
    assert warmup_timings == []
    verified.index.calls = 0
    results, timings = _retrieve(
        verified, FixtureEmbeddingProvider(), questions, expectations, rounds=5, timed=True
    )
    assert verified.index.calls == 50
    assert len(timings) == 50
    assert len(results) == 10


@pytest.mark.parametrize(
    ("warmup_rounds", "measurement_rounds"),
    [(True, 1), (1, False), (0, 1), (-1, 1), (1, 0), (1, -1)],
)
def test_run_rejects_invalid_round_counts_before_building_or_writing_artifacts(
    tmp_path, monkeypatch, warmup_rounds: int, measurement_rounds: int
) -> None:
    questions, expectations = _valid()
    questions_path = tmp_path / "questions.json"
    oracle_path = tmp_path / "oracle.json"
    artifacts_path = tmp_path / "artifacts" / "benchmark.json"
    questions_path.write_text(
        json.dumps({"schema_version": 1, "questions": questions}), encoding="utf-8"
    )
    oracle_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "expectations": [
                    {"id": identifier, "acceptable_paths": list(paths)}
                    for identifier, paths in expectations.items()
                ],
            }
        ),
        encoding="utf-8",
    )
    build_called = False

    def fail_if_called(*args: object, **kwargs: object) -> None:
        nonlocal build_called
        build_called = True
        raise AssertionError("bundle build must not run for invalid round counts")

    monkeypatch.setattr(run_benchmark, "_build_verified_bundle", fail_if_called)

    with pytest.raises(ValueError) as captured:
        run_benchmark.run(
            questions_path=questions_path,
            oracle_path=oracle_path,
            artifacts_path=artifacts_path,
            warmup_rounds=warmup_rounds,
            measurement_rounds=measurement_rounds,
        )

    assert str(captured.value) == "round counts must be positive"
    assert build_called is False
    assert artifacts_path.exists() is False


def test_real_pipeline_report_contract(tmp_path) -> None:
    artifacts_path = tmp_path / "benchmark.json"
    report = run_benchmark.run(
        questions_path=run_benchmark.PUBLIC_QUESTIONS,
        oracle_path=run_benchmark.CONTROLLER_ORACLE,
        artifacts_path=artifacts_path,
        warmup_rounds=2,
        measurement_rounds=2,
    )

    assert report["question_count"] == 20
    assert report["pair_count"] == 10
    assert report["distinct_expected_path_count"] == 6
    assert report["timing_sample_count"] == 40
    indexed = report["indexed"]
    assert isinstance(indexed, dict)
    assert isinstance(indexed["evidence_records"], int) and indexed["evidence_records"] > 0
    assert isinstance(indexed["sources"], int) and indexed["sources"] > 0
    assert indexed["repositories"] == 1
    assert report["provider"] == {
        "adapter": "deterministic_fixture",
        "model_id": "sha256-token-hash-v1",
        "dimension": 384,
        "normalized": True,
        "query_prefix": "query: ",
        "passage_prefix": "passage: ",
    }
    assert report["provider_is_production"] is False
    host = report["reference_host"]
    assert isinstance(host, dict)
    assert all(host.get(key) for key in ("python", "platform", "numpy", "machine", "processor"))
    assert isinstance(host.get("logical_cpu_count"), int)
    assert host["target"] == {"cpu_cores": 4, "memory_gib": 8}
    assert report["oracle_isolation"] == "best_effort"
    assert report["oracle_isolation_enforced"] is False
    assert report["reference_host_verified"] is False
    assert report["formal_blockers"] == [
        "fixture_provider_nonproduction",
        "oracle_isolation_not_enforced",
        "reference_host_not_verified",
    ]
    assert report["formal_acceptance"] is False
    assert report["passed"] is False
    assert isinstance(report["harness_thresholds_met"], bool)
    pair_results = report["pair_results"]
    assert isinstance(pair_results, list)
    for pair in pair_results:
        assert isinstance(pair, dict)
        assert pair["equivalent"] == pair["both_hit"]
    assert json.loads(artifacts_path.read_text(encoding="utf-8")) == report
