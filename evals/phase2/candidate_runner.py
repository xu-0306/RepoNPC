"""Oracle-blind Docker candidate for the formal Phase 2 retrieval benchmark."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import platform
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

from reponpc.bundles.archive import build_bundle, verify_bundle_archive
from reponpc.bundles.manifest import bundle_id_for
from reponpc.config.models import load_public_config
from reponpc.indexing.exclusions import SourceEntryKind
from reponpc.indexing.index_database import IndexDatabaseBuilder
from reponpc.indexing.public_profile import build_public_profile_bytes
from reponpc.indexing.sources import RepositoryBlob, ResolvedConfiguration, ResolvedRepository
from reponpc.providers.local_sentence_transformers import (
    LocalSentenceTransformersEmbeddingProvider,
)

FIXTURE_SHA = "a" * 40
BUILT_AT = datetime(2026, 8, 10, 12, 0, tzinfo=UTC)
MAX_BUNDLE_BYTES = 536_870_912


def run(
    *,
    questions_path: Path,
    repository_path: Path,
    config_path: Path,
    output_path: Path,
    warmup_rounds: int,
    measurement_rounds: int,
) -> dict[str, object]:
    """Build twice and emit only raw retrieval observations, never an oracle verdict."""

    questions = _load_questions(questions_path)
    if any(
        isinstance(value, bool) or not isinstance(value, int) or value <= 0
        for value in (warmup_rounds, measurement_rounds)
    ):
        raise ValueError("round counts must be positive integers")
    config = load_public_config(config_path)
    configured = config.retrieval.embedding
    provider = LocalSentenceTransformersEmbeddingProvider(
        model_id=configured.model,
        dimension=configured.dimension,
        normalized=configured.normalized,
        query_prefix=configured.query_prefix,
        passage_prefix=configured.passage_prefix,
    )
    with tempfile.TemporaryDirectory(prefix="reponpc-p2-candidate-") as temporary:
        workspace = Path(temporary)
        first, first_build = _build_verified(
            workspace / "first", config_path, repository_path, provider
        )
        second, second_build = _build_verified(
            workspace / "second", config_path, repository_path, provider
        )
        try:
            for _ in range(warmup_rounds):
                _retrieve(first, provider, questions, timed=False)
            results: list[dict[str, object]] = []
            timings: list[int] = []
            for round_index in range(measurement_rounds):
                round_results, round_timings = _retrieve(first, provider, questions, timed=True)
                if round_index == 0:
                    results = round_results
                timings.extend(round_timings)
        finally:
            first.close()
            second.close()

    identity = provider.identity()
    report: dict[str, object] = {
        "schema_name": "reponpc/phase2-candidate",
        "schema_version": 1,
        "provider": {
            "adapter": identity.adapter,
            "model_id": identity.model_id,
            "dimension": identity.dimension,
            "normalized": identity.normalized,
            "query_prefix": identity.query_prefix,
            "passage_prefix": identity.passage_prefix,
        },
        "builds": [first_build, second_build],
        "results": results,
        "timings_ns": timings,
        "warmup_rounds": warmup_rounds,
        "measurement_rounds": measurement_rounds,
        "indexed": dict(first.manifest.statistics),
        "provenance": {
            "python": platform.python_version(),
            "numpy": np.__version__,
            "sentence_transformers": importlib.metadata.version("sentence-transformers"),
            "torch": importlib.metadata.version("torch"),
            "platform": platform.platform(aliased=True),
        },
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    return report


def _build_verified(
    workspace: Path,
    config_path: Path,
    repository_path: Path,
    provider: LocalSentenceTransformersEmbeddingProvider,
):
    workspace.mkdir(parents=True, exist_ok=True)
    config = load_public_config(config_path)
    config_content = config_path.read_text(encoding="utf-8")
    configuration = ResolvedConfiguration(
        repository_slug="fixture-owner/reponpc-demo",
        commit_sha=FIXTURE_SHA,
        path="reponpc.yml",
        content=config_content,
        github_html_url="https://github.com/fixture-owner/reponpc-demo",
    )
    repository = ResolvedRepository(
        slug="fixture-owner/reponpc-demo",
        commit_sha=FIXTURE_SHA,
        default_branch="main",
        github_html_url="https://github.com/fixture-owner/reponpc-demo",
        blobs=tuple(
            RepositoryBlob(
                path=path.relative_to(repository_path).as_posix(),
                entry_kind=SourceEntryKind.REGULAR_FILE,
                size_bytes=path.stat().st_size,
                content=path.read_bytes(),
            )
            for path in sorted(repository_path.rglob("*"))
            if path.is_file()
        ),
    )
    index_result = IndexDatabaseBuilder(provider).build(
        config=config,
        configuration_source=configuration,
        repositories=(repository,),
        output_path=workspace / "index.sqlite",
    )
    bundle_id = bundle_id_for(
        built_at=BUILT_AT,
        configuration_bytes=config_content.encode("utf-8"),
        repositories=((repository.slug, repository.commit_sha),),
        embedding=provider.identity(),
        parser_chunker_version="p2-02-v1",
    )
    public_files = _public_files(
        config_path=config_path,
        bundle_id=bundle_id,
        repository_count=index_result.repository_count,
    )
    bundle = build_bundle(
        index_result=index_result,
        configuration_source=configuration,
        repositories=(repository,),
        bundle_id=bundle_id,
        built_at=BUILT_AT,
        public_files=public_files,
        output_path=workspace / f"reponpc-index-{bundle_id}.tar.zst",
    )
    verified = verify_bundle_archive(
        archive_path=bundle.archive_path,
        staging_directory=workspace / "stage",
        expected_outer_sha256=bundle.archive_sha256,
        expected_embedding=provider.identity(),
        max_bundle_bytes=MAX_BUNDLE_BYTES,
    )
    build_observation = {
        "manifest_sha256": hashlib.sha256(bundle.manifest.canonical_bytes()).hexdigest(),
        "archive_sha256": bundle.archive_sha256,
        "database_sha256": _file_sha256(index_result.database_path),
    }
    return verified, build_observation


def _public_files(*, config_path: Path, bundle_id: str, repository_count: int) -> dict[str, bytes]:
    config = load_public_config(config_path)
    return {
        "public/profile.json": build_public_profile_bytes(
            config=config,
            index_version=bundle_id,
            built_at=BUILT_AT,
            repository_count=repository_count,
        ),
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


def _retrieve(
    verified,
    provider: LocalSentenceTransformersEmbeddingProvider,
    questions: list[dict[str, str]],
    *,
    timed: bool,
) -> tuple[list[dict[str, object]], list[int]]:
    results: list[dict[str, object]] = []
    timings: list[int] = []
    for item in questions:
        started = time.perf_counter_ns()
        query_vector = provider.embed_query([item["question"]])[0]
        evidence_ids = verified.index.hybrid_candidates(
            item["question"],
            query_vector=query_vector,
            lexical_limit=8,
            vector_limit=8,
            final_limit=8,
        )
        if timed:
            timings.append(time.perf_counter_ns() - started)
        records = [
            evidence
            for evidence_id in evidence_ids
            if (evidence := verified.index.evidence(evidence_id)) is not None
        ]
        results.append(
            {
                "id": item["id"],
                "pair_id": item["pair_id"],
                "locale": item["locale"],
                "retrieved_evidence_ids": [record.evidence_id for record in records],
                "retrieved_paths": [record.path for record in records],
            }
        )
    return results, timings


def _load_questions(path: Path) -> list[dict[str, str]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    records = payload.get("questions")
    if not isinstance(records, list):
        raise ValueError("questions must be a list")
    validated: list[dict[str, str]] = []
    ids: set[str] = set()
    for item in records:
        if not isinstance(item, dict) or set(item) != {"id", "pair_id", "locale", "question"}:
            raise ValueError("question shape is invalid")
        if any(not isinstance(item[key], str) or not item[key] for key in item):
            raise ValueError("question values are invalid")
        if item["id"] in ids or item["locale"] not in {"zh-TW", "en"}:
            raise ValueError("question identity is invalid")
        ids.add(item["id"])
        validated.append({key: str(value) for key, value in item.items()})
    return validated


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(64 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the oracle-blind Phase 2 candidate.")
    parser.add_argument("--questions", type=Path, required=True)
    parser.add_argument("--repository", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--warmup-rounds", type=int, default=2)
    parser.add_argument("--measurement-rounds", type=int, default=5)
    args = parser.parse_args()
    run(
        questions_path=args.questions,
        repository_path=args.repository,
        config_path=args.config,
        output_path=args.output,
        warmup_rounds=args.warmup_rounds,
        measurement_rounds=args.measurement_rounds,
    )


if __name__ == "__main__":
    main()
