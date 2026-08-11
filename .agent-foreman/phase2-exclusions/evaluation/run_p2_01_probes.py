"""Independent falsification probes for the frozen P2-01 classifier contract.

This evaluator-owned runner is intentionally separate from the production test
suite.  It imports the public P2-01 classifier and writes only its three JSON
probe artifacts beside this file.
"""

from __future__ import annotations

import builtins
import io
import json
import os
import pathlib
import socket
import urllib.request
from dataclasses import fields
from inspect import signature
from pathlib import Path
from typing import Any, Callable

from reponpc.indexing.exclusions import (
    ExclusionDecision,
    ExclusionPolicy,
    ExclusionReason,
    SourceEntryKind,
    SourceMetadata,
    classify_source,
)


ARTIFACT_DIRECTORY = Path(__file__).parent
COMMAND = (
    "rtk proxy uv --cache-dir D:/RepoNPC/.uv-cache run --offline --no-sync "
    "--python C:/Python314/python.exe --no-managed-python python "
    ".agent-foreman/phase2-exclusions/evaluation/run_p2_01_probes.py"
)


def _metadata(
    *,
    size_bytes: int = 4,
    repository_text_bytes_before: int = 0,
    corpus_text_bytes_before: int = 0,
    entry_kind: SourceEntryKind = SourceEntryKind.REGULAR_FILE,
    has_high_confidence_secret: bool = False,
) -> SourceMetadata:
    return SourceMetadata(
        entry_kind=entry_kind,
        size_bytes=size_bytes,
        repository_text_bytes_before=repository_text_bytes_before,
        corpus_text_bytes_before=corpus_text_bytes_before,
        has_high_confidence_secret=has_high_confidence_secret,
    )


def _policy(
    *,
    repository_exclude_patterns: tuple[str, ...] = (),
    global_exclude_patterns: tuple[str, ...] = (),
    max_file_bytes: int = 8,
    max_repository_text_bytes: int = 100,
    max_corpus_text_bytes: int = 100,
) -> ExclusionPolicy:
    return ExclusionPolicy(
        include_patterns=("**",),
        repository_exclude_patterns=repository_exclude_patterns,
        global_exclude_patterns=global_exclude_patterns,
        max_file_bytes=max_file_bytes,
        max_repository_text_bytes=max_repository_text_bytes,
        max_corpus_text_bytes=max_corpus_text_bytes,
    )


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _purity_probe() -> dict[str, Any]:
    """Tripwire common I/O boundaries during a real classifier invocation."""

    expected_parameters = ("path", "metadata", "policy")
    expected_metadata_fields = (
        "entry_kind",
        "size_bytes",
        "is_binary",
        "is_decodable",
        "has_high_confidence_secret",
        "repository_text_bytes_before",
        "corpus_text_bytes_before",
    )
    _assert(tuple(signature(classify_source).parameters) == expected_parameters, "API changed")
    _assert(
        tuple(field.name for field in fields(SourceMetadata)) == expected_metadata_fields,
        "metadata unexpectedly accepts a source body",
    )
    _assert(
        tuple(field.name for field in fields(ExclusionDecision)) == ("include", "reason_code"),
        "decision unexpectedly exposes a source body",
    )

    canary = "EVALUATOR_SOURCE_BODY_CANARY_DO_NOT_LEAK"
    candidate = _metadata()
    rules = _policy()
    observed_boundaries: list[str] = []
    originals: list[tuple[object, str, Callable[..., Any]]] = []

    def tripwire(name: str) -> Callable[..., Any]:
        def denied(*args: object, **kwargs: object) -> Any:
            del args, kwargs
            observed_boundaries.append(name)
            raise AssertionError(f"classifier attempted forbidden boundary: {name}")

        return denied

    targets: tuple[tuple[object, str], ...] = (
        (builtins, "open"),
        (io, "open"),
        (os, "stat"),
        (pathlib.Path, "open"),
        (socket, "create_connection"),
        (urllib.request, "urlopen"),
    )
    for target, attribute in targets:
        original = getattr(target, attribute)
        originals.append((target, attribute, original))
        setattr(target, attribute, tripwire(f"{target.__name__}.{attribute}"))

    try:
        decision = classify_source(f".env.{canary}", candidate, rules)
    finally:
        for target, attribute, original in reversed(originals):
            setattr(target, attribute, original)

    _assert(not observed_boundaries, "classifier crossed a forbidden I/O boundary")
    _assert(decision == ExclusionDecision(False, ExclusionReason.ENVIRONMENT_FILE), "wrong result")
    _assert(canary not in repr(decision), "decision leaked the canary")
    return {
        "probe_id": "P2-01-PROBE-PURITY",
        "invariant_id": "INV-EXCLUSION-PURITY",
        "command": COMMAND,
        "setup": "Construct only value metadata and immutable policy, then install I/O and network tripwires after imports.",
        "fault_injection": "Pass an environment-style path containing a source-body canary while open, stat, socket connection, and URL-open boundaries raise if reached.",
        "production_trigger": "Call classify_source(path, metadata, policy) through its public module API.",
        "oracle": "The call returns ENVIRONMENT_FILE, triggers no boundary, preserves the exact three-argument/body-free API, and its decision representation omits the canary.",
        "anti_oracle": "Signature or dataclass inspection alone does not count; this probe invokes the production classifier with active tripwires.",
        "observations": {
            "decision": decision.reason_code.value,
            "include": decision.include,
            "tripwire_hits": observed_boundaries,
            "return_contains_canary": canary in repr(decision),
        },
        "exit_code": 0,
        "deterministic_result": "passed",
    }


def _mandatory_precedence_probe() -> dict[str, Any]:
    """Attempt to re-include unsafe files with later negated policy rules."""

    rules = _policy(
        global_exclude_patterns=(".env*", "!.env.production"),
        repository_exclude_patterns=(
            "keys/**",
            "!keys/id_rsa",
            "node_modules/**",
            "!node_modules/**",
            "static/**",
            "!static/app.min.js",
        ),
    )
    cases: tuple[tuple[str, SourceMetadata, ExclusionReason], ...] = (
        (".env.production", _metadata(), ExclusionReason.ENVIRONMENT_FILE),
        ("keys/id_rsa", _metadata(), ExclusionReason.CREDENTIAL_OR_KEY),
        ("node_modules/pkg/index.py", _metadata(), ExclusionReason.DEPENDENCY_OR_VENDOR),
        ("static/app.min.js", _metadata(), ExclusionReason.MINIFIED_OR_SOURCE_MAP),
        ("src/normal.py", _metadata(has_high_confidence_secret=True), ExclusionReason.HIGH_CONFIDENCE_SECRET),
        ("src/link.py", _metadata(entry_kind=SourceEntryKind.SYMLINK), ExclusionReason.SYMLINK),
    )
    observed: dict[str, str] = {}
    for path, candidate, expected in cases:
        decision = classify_source(path, candidate, rules)
        _assert(decision == ExclusionDecision(False, expected), f"{path} was re-included")
        observed[path] = decision.reason_code.value
    return {
        "probe_id": "P2-01-PROBE-MANDATORY-PRECEDENCE",
        "invariant_id": "INV-MANDATORY-EXCLUSIONS",
        "command": COMMAND,
        "setup": "Use a broad ** include and a regular-file metadata fixture for each unsafe candidate, plus secret and symlink metadata cases.",
        "fault_injection": "Install global/repository exclusions followed by negated rules that would re-include the exact .env, key, dependency, and minified targets if policy precedence ran first.",
        "production_trigger": "Call classify_source for every unsafe candidate through the public module API.",
        "oracle": "Every candidate skips with its mandatory stable reason rather than ELIGIBLE, GLOBAL_EXCLUDED, or REPOSITORY_EXCLUDED.",
        "anti_oracle": "A policy with no matching include/exclude pattern would only prove a default skip; this probe uses ** plus later negated re-inclusion rules for each path category.",
        "observations": observed,
        "exit_code": 0,
        "deterministic_result": "passed",
    }


def _cumulative_budget_probe() -> dict[str, Any]:
    """Exercise repository and corpus limits using individually valid files."""

    repository_rules = _policy(max_repository_text_bytes=10)
    corpus_rules = _policy(max_corpus_text_bytes=10)
    repository_cases = (
        ("src/one.py", _metadata(repository_text_bytes_before=0), ExclusionReason.ELIGIBLE),
        ("src/two.py", _metadata(repository_text_bytes_before=4), ExclusionReason.ELIGIBLE),
        (
            "src/three.py",
            _metadata(repository_text_bytes_before=8),
            ExclusionReason.REPOSITORY_TEXT_BUDGET_EXCEEDED,
        ),
    )
    corpus_cases = (
        ("src/one.py", _metadata(corpus_text_bytes_before=0), ExclusionReason.ELIGIBLE),
        ("src/two.py", _metadata(corpus_text_bytes_before=4), ExclusionReason.ELIGIBLE),
        (
            "src/three.py",
            _metadata(corpus_text_bytes_before=8),
            ExclusionReason.CORPUS_TEXT_BUDGET_EXCEEDED,
        ),
    )

    def run_sequence(
        cases: tuple[tuple[str, SourceMetadata, ExclusionReason], ...],
        rules: ExclusionPolicy,
    ) -> list[str]:
        observed: list[str] = []
        for path, candidate, expected in cases:
            _assert(candidate.size_bytes <= rules.max_file_bytes, "fixture is not individually valid")
            decision = classify_source(path, candidate, rules)
            _assert(decision.reason_code is expected, f"wrong budget decision for {path}")
            observed.append(decision.reason_code.value)
        return observed

    repository_results = run_sequence(repository_cases, repository_rules)
    corpus_results = run_sequence(corpus_cases, corpus_rules)
    return {
        "probe_id": "P2-01-PROBE-CUMULATIVE-BUDGET",
        "invariant_id": "INV-EXCLUSION-BUDGETS",
        "command": COMMAND,
        "setup": "Set a per-file limit of 8 bytes and repository/corpus limits of 10 bytes, then declare two prior admitted 4-byte files in the third candidate metadata.",
        "fault_injection": "Supply a third 4-byte candidate after an 8-byte prior total, so every candidate remains below the per-file limit while the aggregate would reach 12 bytes.",
        "production_trigger": "Call classify_source sequentially for repository-budget and corpus-budget metadata sequences.",
        "oracle": "The first two candidates are ELIGIBLE and the third returns the exact repository or corpus budget-exceeded code before admission.",
        "anti_oracle": "A single oversized file only proves the file limit; this probe uses three individually valid candidates and exercises both aggregate counters.",
        "observations": {
            "repository_sequence": repository_results,
            "corpus_sequence": corpus_results,
            "all_fixture_sizes_bytes": [4, 4, 4],
        },
        "exit_code": 0,
        "deterministic_result": "passed",
    }


def main() -> None:
    probes = (
        ("probe-purity.json", _purity_probe),
        ("probe-mandatory-precedence.json", _mandatory_precedence_probe),
        ("probe-cumulative-budget.json", _cumulative_budget_probe),
    )
    for filename, probe in probes:
        payload = probe()
        (ARTIFACT_DIRECTORY / filename).write_text(
            json.dumps(payload, ensure_ascii=True, indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"{payload['probe_id']}: {payload['deterministic_result']}")


if __name__ == "__main__":
    main()
