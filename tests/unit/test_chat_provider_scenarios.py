"""Strict, non-secret contract checks for the Phase 3 chat mock fixture."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest

REPOSITORY_ROOT = Path(__file__).parents[2]
FIXTURE_PATH = REPOSITORY_ROOT / "tests" / "fixtures" / "providers" / "chat_scenarios.json"

EXPECTED_SCENARIOS = {
    "openai_success_structured_usage": ("openai_compatible", 200, "json"),
    "openai_success_null_usage": ("openai_compatible", 200, "json"),
    "ollama_success": ("ollama", 200, "json"),
    "authentication_401": ("openai_compatible", 401, "json"),
    "rate_limit_429": ("openai_compatible", 429, "json"),
    "timeout_504": ("openai_compatible", 504, "text"),
    "unavailable_503": ("openai_compatible", 503, "json"),
    "malformed_json_body": ("openai_compatible", 200, "malformed_json"),
    "context_overflow_422": ("openai_compatible", 422, "json"),
}
ALLOWED_PROVIDERS = frozenset({"openai_compatible", "ollama"})
ALLOWED_STATUSES = frozenset({200, 401, 422, 429, 503, 504})
ALLOWED_BODY_TYPES = frozenset({"json", "text", "malformed_json"})
SCENARIO_KEYS = frozenset({"id", "provider", "status", "body_type", "body"})

# Usage fields are intentionally allowed: they are accounting values, not secrets.
SECRET_KEY_PATTERN = re.compile(
    r"(?i)(?:api[_ -]?key|authorization|cookie|csrf|password|secret|"
    r"private[_ -]?key|credential|access[_ -]?token|bearer)"
)
SECRET_VALUE_PATTERNS = (
    re.compile(r"(?i)\b(?:sk|rk|pk)-[A-Za-z0-9_-]{16,}\b"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b"),
    re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._-]{12,}"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
)
URL_PATTERN = re.compile(r"(?i)\b(?:https?|ftp|file|ssh)://")


def _load_fixture() -> dict[str, Any]:
    with FIXTURE_PATH.open(encoding="utf-8") as fixture_file:
        payload = json.load(fixture_file)
    assert isinstance(payload, dict)
    return payload


def _walk(value: Any) -> list[tuple[str | None, Any]]:
    """Return every mapping key/value and sequence value for safety checks."""

    found: list[tuple[str | None, Any]] = []
    if isinstance(value, Mapping):
        for key, child in value.items():
            found.append((str(key), child))
            found.extend(_walk(child))
    elif isinstance(value, list):
        for child in value:
            found.extend(_walk(child))
    return found


def test_fixture_has_only_the_version_and_scenario_list() -> None:
    payload = _load_fixture()

    assert set(payload) == {"schema_version", "scenarios"}
    assert payload["schema_version"] == 1
    assert isinstance(payload["scenarios"], list)


def test_scenarios_have_strict_unique_shape_and_bounded_values() -> None:
    scenarios = _load_fixture()["scenarios"]
    assert scenarios

    seen_ids: set[str] = set()
    for scenario in scenarios:
        assert isinstance(scenario, dict)
        assert set(scenario) == SCENARIO_KEYS
        scenario_id = scenario["id"]
        assert isinstance(scenario_id, str) and scenario_id
        assert scenario_id not in seen_ids
        seen_ids.add(scenario_id)

        assert scenario["provider"] in ALLOWED_PROVIDERS
        status = scenario["status"]
        assert isinstance(status, int) and not isinstance(status, bool)
        assert status in ALLOWED_STATUSES
        body_type = scenario["body_type"]
        assert body_type in ALLOWED_BODY_TYPES
        if body_type == "json":
            assert isinstance(scenario["body"], dict)
        elif body_type == "malformed_json":
            assert isinstance(scenario["body"], str) and scenario["body"]
            with pytest.raises(json.JSONDecodeError):
                json.loads(scenario["body"])
        else:
            assert isinstance(scenario["body"], str) and scenario["body"]


def test_fixture_contains_exact_required_scenarios() -> None:
    scenarios = {scenario["id"]: scenario for scenario in _load_fixture()["scenarios"]}

    assert set(scenarios) == set(EXPECTED_SCENARIOS)
    for scenario_id, (provider, status, body_type) in EXPECTED_SCENARIOS.items():
        scenario = scenarios[scenario_id]
        assert (scenario["provider"], scenario["status"], scenario["body_type"]) == (
            provider,
            status,
            body_type,
        )


def test_success_scenarios_cover_structured_output_and_nullable_usage() -> None:
    scenarios = {scenario["id"]: scenario for scenario in _load_fixture()["scenarios"]}
    structured = scenarios["openai_success_structured_usage"]["body"]
    null_usage = scenarios["openai_success_null_usage"]["body"]

    assert structured["id"].startswith("fixture-")
    assert isinstance(structured["choices"], list)
    assert isinstance(structured["choices"][0]["message"]["content"], dict)
    assert structured["usage"] == {"prompt_tokens": 11, "completion_tokens": 7}
    assert null_usage["usage"] is None


def test_fixture_values_are_recognizable_fake_data_and_have_no_secret_or_url() -> None:
    payload = _load_fixture()
    serialized = json.dumps(payload, sort_keys=True)
    assert "fixture-" in serialized

    for key, value in _walk(payload):
        if key is not None:
            assert not SECRET_KEY_PATTERN.search(key), key
        if isinstance(value, str):
            assert not URL_PATTERN.search(value), value
            assert not any(pattern.search(value) for pattern in SECRET_VALUE_PATTERNS), value
