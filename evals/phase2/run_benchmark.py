"""Deterministic Phase 2 retrieval benchmark with a separate reviewed oracle.

The public questions deliberately contain no expected paths or evidence IDs.
The small controller oracle is kept outside fixtures and reports
``oracle_isolation=best_effort`` because this shared developer workspace does
not provide a mount-level read deny policy.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import platform
import re
import tempfile
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

from reponpc.bundles.archive import build_bundle, verify_bundle_archive
from reponpc.bundles.manifest import bundle_id_for
from reponpc.config.models import load_public_config
from reponpc.indexing.exclusions import SourceEntryKind
from reponpc.indexing.index_database import IndexDatabaseBuilder
from reponpc.indexing.sources import (
    EmbeddingIdentity,
    RepositoryBlob,
    ResolvedConfiguration,
    ResolvedRepository,
)

REPOSITORY_ROOT = Path(__file__).parents[2]
FIXTURE_CONFIG = REPOSITORY_ROOT / "tests" / "fixtures" / "phase2" / "reponpc.yml"
FIXTURE_REPOSITORY = REPOSITORY_ROOT / "tests" / "fixtures" / "repos" / "reponpc-demo"
PUBLIC_QUESTIONS = Path(__file__).parent / "public" / "questions.json"
CONTROLLER_ORACLE = Path(__file__).parent / "controller" / "expected-evidence.json"
FIXTURE_SHA = "a" * 40
BUILT_AT = datetime(2026, 8, 10, 12, 0, tzinfo=UTC)


@dataclass(frozen=True, slots=True)
class FixtureEmbeddingProvider:
    """Non-network deterministic evaluation provider, never a production adapter."""

    def identity(self) -> EmbeddingIdentity:
        return EmbeddingIdentity(
            adapter="deterministic_fixture",
            model_id="sha256-token-hash-v1",
            dimension=384,
            normalized=True,
            query_prefix="query: ",
            passage_prefix="passage: ",
        )

    def embed_passages(self, texts: list[str]) -> np.ndarray:
        return self._embed(texts)

    def embed_query(self, question: str) -> np.ndarray:
        return self._embed([self.identity().query_prefix + question])[0]

    def _embed(self, texts: list[str]) -> np.ndarray:
        result = np.zeros((len(texts), self.identity().dimension), dtype=np.float32)
        for row, text in enumerate(texts):
            for token in re.findall(r"[\w-]+", text.casefold(), flags=re.UNICODE):
                digest = hashlib.sha256(token.encode("utf-8")).digest()
                result[row, int.from_bytes(digest[:2], "big") % self.identity().dimension] += 1.0
            norm = np.linalg.norm(result[row])
            if norm > 0:
                result[row] /= norm
        return result


def run(
    *,
    questions_path: Path,
    oracle_path: Path,
    artifacts_path: Path,
    warmup_rounds: int = 2,
    measurement_rounds: int = 5,
) -> dict[str, object]:
    """Build twice, retrieve through the verified immutable consumer, and score it."""

    questions = _load_records(questions_path, "questions")
    expectations = {
        str(item["id"]): tuple(str(path) for path in item["acceptable_paths"])
        for item in _load_records(oracle_path, "expectations")
    }
    _validate_inputs(questions, expectations)
    if any(isinstance(value, bool) or value <= 0 for value in (warmup_rounds, measurement_rounds)):
        raise ValueError("round counts must be positive")

    provider = FixtureEmbeddingProvider()
    with tempfile.TemporaryDirectory(prefix="reponpc-p2-eval-") as temporary:
        workspace = Path(temporary)
        first, first_bundle = _build_verified_bundle(workspace / "first", provider)
        second, second_bundle = _build_verified_bundle(workspace / "second", provider)
        try:
            repeatable = _repeatability(first, first_bundle, second, second_bundle)
            for _ in range(warmup_rounds):
                _retrieve(first, provider, questions, expectations, timed=False)
            results, timings = _retrieve(
                first, provider, questions, expectations, rounds=measurement_rounds
            )
        finally:
            first.close()
            second.close()

    recall = sum(bool(item["hit"]) for item in results) / len(results)
    pair_results = _pair_results(results)
    parity = sum(bool(item["equivalent"]) for item in pair_results) / len(pair_results)
    p95_ms = _p95_ms(timings)
    harness_thresholds_met = bool(
        repeatable and recall >= 0.85 and parity >= 0.90 and p95_ms <= 750.0
    )
    identity = provider.identity()
    report: dict[str, object] = {
        "schema_name": "reponpc/phase2-benchmark",
        "schema_version": 1,
        "oracle_isolation": "best_effort",
        "provider": {
            "adapter": identity.adapter,
            "model_id": identity.model_id,
            "dimension": identity.dimension,
            "normalized": identity.normalized,
            "query_prefix": identity.query_prefix,
            "passage_prefix": identity.passage_prefix,
        },
        "provider_is_production": False,
        "oracle_isolation_enforced": False,
        "reference_host_verified": False,
        "reference_host": {
            "python": platform.python_version(),
            "platform": platform.platform(aliased=True),
            "numpy": np.__version__,
            "machine": platform.machine(),
            "processor": platform.processor(),
            "logical_cpu_count": os.cpu_count(),
            "target": {"cpu_cores": 4, "memory_gib": 8},
        },
        "thresholds": {"recall_at_8": 0.85, "language_parity": 0.90, "warm_p95_ms": 750.0},
        "warmup_rounds": warmup_rounds,
        "measurement_rounds": measurement_rounds,
        "timing_sample_count": len(timings),
        "timing_policy": "untimed_warmup_then_full_measurement_rounds",
        "question_count": len(questions),
        "pair_count": len(pair_results),
        "distinct_expected_path_count": len(
            {path for values in expectations.values() for path in values}
        ),
        "indexed": dict(first.manifest.statistics),
        "repeatable": repeatable,
        "recall_at_8": recall,
        "language_parity": parity,
        "warm_p95_ms": p95_ms,
        "results": results,
        "pair_results": pair_results,
        "harness_thresholds_met": harness_thresholds_met,
        "formal_blockers": [
            "fixture_provider_nonproduction",
            "oracle_isolation_not_enforced",
            "reference_host_not_verified",
        ],
        "formal_acceptance": False,
        "passed": False,
    }
    artifacts_path.parent.mkdir(parents=True, exist_ok=True)
    artifacts_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return report


def _build_verified_bundle(workspace: Path, provider: FixtureEmbeddingProvider):
    workspace.mkdir(parents=True, exist_ok=True)
    configuration = ResolvedConfiguration(
        repository_slug="fixture-owner/reponpc-demo",
        commit_sha=FIXTURE_SHA,
        path="reponpc.yml",
        content=FIXTURE_CONFIG.read_text(encoding="utf-8"),
        github_html_url="https://github.com/fixture-owner/reponpc-demo",
    )
    repository = ResolvedRepository(
        slug="fixture-owner/reponpc-demo",
        commit_sha=FIXTURE_SHA,
        default_branch="main",
        github_html_url="https://github.com/fixture-owner/reponpc-demo",
        blobs=tuple(
            RepositoryBlob(
                path=path.relative_to(FIXTURE_REPOSITORY).as_posix(),
                entry_kind=SourceEntryKind.REGULAR_FILE,
                size_bytes=path.stat().st_size,
                content=path.read_bytes(),
            )
            for path in sorted(FIXTURE_REPOSITORY.rglob("*"))
            if path.is_file()
        ),
    )
    index_result = IndexDatabaseBuilder(provider).build(
        config=_fixture_config(provider),
        configuration_source=configuration,
        repositories=(repository,),
        output_path=workspace / "index.sqlite",
    )
    bundle_id = bundle_id_for(
        built_at=BUILT_AT,
        configuration_bytes=configuration.content.encode("utf-8"),
        repositories=((repository.slug, repository.commit_sha),),
        embedding=provider.identity(),
        parser_chunker_version="p2-02-v1",
    )
    bundle = build_bundle(
        index_result=index_result,
        configuration_source=configuration,
        repositories=(repository,),
        bundle_id=bundle_id,
        built_at=BUILT_AT,
        public_files=_public_files(),
        output_path=workspace / f"reponpc-index-{bundle_id}.tar.zst",
    )
    verified = verify_bundle_archive(
        archive_path=bundle.archive_path,
        staging_directory=workspace / "stage",
        expected_outer_sha256=bundle.archive_sha256,
        expected_embedding=provider.identity(),
        max_bundle_bytes=1024 * 1024,
    )
    return verified, bundle


def _public_files() -> dict[str, bytes]:
    return {
        "public/profile.json": b'{"schema_version":1}',
        "public/character.png": b"\x89PNG\r\n\x1a\nfixture",
        **{
            f"public/card-{theme}-{locale}.{extension}": (
                b"<svg xmlns='http://www.w3.org/2000/svg'/>"
                if extension == "svg"
                else b"GIF89a"
                if extension == "gif"
                else b"\x89PNG\r\n\x1a\nfixture"
            )
            for theme in ("light", "dark")
            for locale in ("zh-TW", "en")
            for extension in ("svg", "gif", "png")
        },
    }


def _fixture_config(provider: FixtureEmbeddingProvider):
    config = load_public_config(FIXTURE_CONFIG)
    identity = provider.identity()
    embedding = config.retrieval.embedding.model_copy(
        update={"adapter": identity.adapter, "model": identity.model_id}
    )
    return config.model_copy(
        update={"retrieval": config.retrieval.model_copy(update={"embedding": embedding})}
    )


def _repeatability(first, first_bundle, second, second_bundle) -> bool:
    return (
        first.manifest.canonical_bytes() == second.manifest.canonical_bytes()
        and first_bundle.archive_sha256 == second_bundle.archive_sha256
        and first_bundle.archive_path.read_bytes() == second_bundle.archive_path.read_bytes()
    )


def _retrieve(
    verified,
    provider: FixtureEmbeddingProvider,
    questions: list[dict[str, Any]],
    expectations: dict[str, tuple[str, ...]],
    rounds: int = 1,
    timed: bool = True,
) -> tuple[list[dict[str, object]], list[int]]:
    results: list[dict[str, object]] = []
    timings: list[int] = []
    for item in questions * rounds:
        question = str(item["question"])
        started = time.perf_counter_ns()
        evidence_ids = verified.index.hybrid_candidates(
            question,
            query_vector=provider.embed_query(question),
            lexical_limit=8,
            vector_limit=8,
            final_limit=8,
        )
        if timed:
            timings.append(time.perf_counter_ns() - started)
        paths = tuple(
            evidence.path
            for evidence_id in evidence_ids
            if (evidence := verified.index.evidence(evidence_id)) is not None
        )
        expected_paths = expectations[str(item["id"])]
        results.append(
            {
                "id": str(item["id"]),
                "pair_id": str(item["pair_id"]),
                "locale": str(item["locale"]),
                "hit": any(path in expected_paths for path in paths),
                "retrieved_paths": list(paths),
                "expected_path_count": len(expected_paths),
            }
        )
    return results[: len(questions)], timings


def _pair_results(results: list[dict[str, object]]) -> list[dict[str, object]]:
    by_pair: dict[str, list[dict[str, object]]] = {}
    for result in results:
        by_pair.setdefault(str(result["pair_id"]), []).append(result)
    paired: list[dict[str, object]] = []
    for pair_id, members in sorted(by_pair.items()):
        if len(members) != 2 or {member["locale"] for member in members} != {"en", "zh-TW"}:
            raise ValueError("every parity pair must contain one en and one zh-TW question")
        paired.append(
            {
                "pair_id": pair_id,
                "equivalent": all(bool(member["hit"]) for member in members),
                "both_hit": all(bool(member["hit"]) for member in members),
            }
        )
    return paired


def _validate_inputs(
    questions: list[dict[str, Any]], expectations: dict[str, tuple[str, ...]]
) -> None:
    ids: set[str] = set()
    pairs: dict[str, list[str]] = {}
    for item in questions:
        question_id = item.get("id")
        pair_id = item.get("pair_id")
        locale = item.get("locale")
        question = item.get("question")
        if not isinstance(question_id, str) or not question_id or question_id in ids:
            raise ValueError("question IDs must be unique nonempty strings")
        if not isinstance(pair_id, str) or not pair_id or locale not in {"en", "zh-TW"}:
            raise ValueError("question pair metadata is invalid")
        if not isinstance(question, str) or not question.strip():
            raise ValueError("question text is invalid")
        ids.add(question_id)
        pairs.setdefault(pair_id, []).append(locale)
    if ids != set(expectations):
        raise ValueError("public questions and controller oracle differ")
    if any(
        not paths or any(not isinstance(path, str) or not path for path in paths)
        for paths in expectations.values()
    ):
        raise ValueError("acceptable paths are invalid")
    if any(sorted(locales) != ["en", "zh-TW"] for locales in pairs.values()):
        raise ValueError("every pair requires one en and one zh-TW")
    if len(pairs) < 10:
        raise ValueError("at least ten question pairs are required")
    if len({path for paths in expectations.values() for path in paths}) < 5:
        raise ValueError("at least five distinct acceptable paths are required")


def _p95_ms(timings_ns: list[int]) -> float:
    ordered = sorted(timings_ns)
    index = max(0, math.ceil(len(ordered) * 0.95) - 1)
    return ordered[index] / 1_000_000


def _load_records(path: Path, key: str) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    records = payload.get(key)
    if not isinstance(records, list) or not all(isinstance(item, dict) for item in records):
        raise ValueError(f"{key} must be a JSON object list")
    return records


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the deterministic RepoNPC Phase 2 benchmark.")
    parser.add_argument("--questions", type=Path, default=PUBLIC_QUESTIONS)
    parser.add_argument("--oracle", type=Path, default=CONTROLLER_ORACLE)
    parser.add_argument("--artifacts", type=Path, required=True)
    parser.add_argument("--warmup-rounds", type=int, default=2)
    parser.add_argument("--measurement-rounds", type=int, default=5)
    args = parser.parse_args()
    report = run(
        questions_path=args.questions,
        oracle_path=args.oracle,
        artifacts_path=args.artifacts,
        warmup_rounds=args.warmup_rounds,
        measurement_rounds=args.measurement_rounds,
    )
    if not bool(report["passed"]):
        raise SystemExit("phase2 benchmark thresholds not met")


if __name__ == "__main__":
    main()
