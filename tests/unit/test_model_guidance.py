"""Synthetic catalog records exercise the leaf; none are live-model evidence."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import FrozenInstanceError, replace
from datetime import date
from pathlib import Path
from typing import Any

import pytest
import yaml

from reponpc.admin.model_guidance import (
    CatalogModel,
    HardwareProfile,
    ModelGuidanceError,
    estimate_model_suitability,
    load_model_catalog,
    parse_model_catalog,
)


def _record() -> dict[str, Any]:
    # Deliberately invented IDs, sizes, license and evidence references.
    return {
        "model_id": "unseen-maker/orbit:3b",
        "parameter_count": 3_000_000_000,
        "last_reviewed": "2026-10-03",
        "source_url": "https://models.example.invalid/orbit",
        "license_id": "Fixture-License-1.0",
        "license_url": "https://models.example.invalid/orbit/LICENSE",
        "quantizations": [
            {
                "quantization_id": "invented-q4",
                "bits_per_weight": 4,
                "download_bytes": 1_600_000_000,
                "memory_overhead_bytes": 500_000_000,
                "envelope_evidence": {
                    "evidence_kind": "live_provider",
                    "envelope_version": 2,
                    "provider": "ollama",
                    "model_revision": "fixture-revision-123",
                    "tested_on": "2026-10-02",
                    "report_reference": "release-evidence/a7/fictional-fixture.json",
                    "tested_locales": ["zh-TW", "en"],
                    "cases_passed": 12,
                    "cases_total": 12,
                },
            },
        ],
    }


def _catalog(record: dict[str, Any] | None = None) -> str:
    return yaml.safe_dump(
        {"schema_version": 1, "models": [_record() if record is None else record]}
    )


def _model() -> CatalogModel:
    return parse_model_catalog(_catalog()).models[0]


def _hardware(**changes: Any) -> HardwareProfile:
    return HardwareProfile(
        **{
            "host_ram_bytes": 16_000_000_000,
            "free_memory_bytes": 8_000_000_000,
            "free_disk_bytes": 12_000_000_000,
            **changes,
        }
    )


def test_packaged_catalog_is_honestly_empty() -> None:
    catalog = load_model_catalog()
    assert catalog.schema_version == 1
    assert catalog.models == ()


def test_loader_dates_and_all_record_facts_are_preserved(tmp_path: Path) -> None:
    text = _catalog()
    path = tmp_path / "catalog.yml"
    path.write_text(text, encoding="utf-8")
    catalog = load_model_catalog(path)
    assert catalog == parse_model_catalog(text)
    model = catalog.models[0]
    assert model.last_reviewed == date(2026, 10, 3)
    assert model.quantizations[0].envelope_evidence.tested_on == date(2026, 10, 2)
    assert model.quantizations[0].envelope_evidence.envelope_version == 2
    assert model.source_url == _record()["source_url"]
    assert model.license_id == "Fixture-License-1.0"


@pytest.mark.parametrize(
    "bits,weight_bytes",
    [(2, 750_000_000), (4, 1_500_000_000), (8, 3_000_000_000), (16, 6_000_000_000)],
)
def test_memory_comes_from_parameters_bits_and_explicit_overhead(
    bits: int, weight_bytes: int
) -> None:
    record = _record()
    record["quantizations"][0]["bits_per_weight"] = bits
    model = parse_model_catalog(_catalog(record)).models[0]
    result = estimate_model_suitability(model, model.quantizations[0], _hardware())
    assert result.weight_bytes == weight_bytes
    assert result.estimated_memory_bytes == weight_bytes + 500_000_000
    assert result.required_disk_bytes == 1_600_000_000
    assert result.grade == "suitable"
    assert result.speed_estimate_tokens_per_second is None


def test_rounds_weight_bits_up_to_whole_bytes() -> None:
    model = replace(_model(), parameter_count=9)
    result = estimate_model_suitability(model, model.quantizations[0], _hardware())
    assert result.weight_bytes == 5


@pytest.mark.parametrize(
    "memory,disk,grade,reason",
    [
        (2_400_000_000, 1_920_000_000, "suitable", None),
        (2_399_999_999, 1_920_000_000, "marginal", "MEMORY_HEADROOM_LOW"),
        (2_400_000_000, 1_919_999_999, "marginal", "DISK_HEADROOM_LOW"),
        (2_000_000_000, 1_600_000_000, "marginal", "MEMORY_HEADROOM_LOW"),
        (1_999_999_999, 1_600_000_000, "not_recommended", "FREE_MEMORY_INSUFFICIENT"),
        (2_000_000_000, 1_599_999_999, "not_recommended", "FREE_DISK_INSUFFICIENT"),
        (0, 0, "not_recommended", "FREE_MEMORY_INSUFFICIENT"),
    ],
)
def test_capacity_and_headroom_boundaries(
    memory: int, disk: int, grade: str, reason: str | None
) -> None:
    model = _model()
    result = estimate_model_suitability(
        model, model.quantizations[0], _hardware(free_memory_bytes=memory, free_disk_bytes=disk)
    )
    assert result.grade == grade
    if reason is not None:
        assert reason in result.reason_codes


@pytest.mark.parametrize(
    "field,reason",
    [
        ("host_ram_bytes", "HOST_RAM_UNKNOWN"),
        ("free_memory_bytes", "FREE_MEMORY_UNKNOWN"),
        ("free_disk_bytes", "FREE_DISK_UNKNOWN"),
    ],
)
def test_unknown_required_hardware_is_not_zero_or_suitable(field: str, reason: str) -> None:
    model = _model()
    result = estimate_model_suitability(model, model.quantizations[0], _hardware(**{field: None}))
    assert result.grade == "unknown"
    assert reason in result.reason_codes
    assert "FREE_MEMORY_INSUFFICIENT" not in result.reason_codes
    assert "FREE_DISK_INSUFFICIENT" not in result.reason_codes


def test_unknown_retains_observed_failures_without_claiming_complete_estimate() -> None:
    model = _model()
    result = estimate_model_suitability(
        model, model.quantizations[0], _hardware(host_ram_bytes=None, free_disk_bytes=0)
    )
    assert result.grade == "unknown"
    assert "HOST_RAM_UNKNOWN" in result.reason_codes
    assert "FREE_DISK_INSUFFICIENT" in result.reason_codes


def test_known_total_memory_shortage_is_not_recommended() -> None:
    model = _model()
    result = estimate_model_suitability(
        model,
        model.quantizations[0],
        _hardware(host_ram_bytes=1_000_000_000, free_memory_bytes=500_000_000),
    )
    assert result.grade == "not_recommended"
    assert "TOTAL_MEMORY_INSUFFICIENT" in result.reason_codes


def test_multiple_quantizations_and_parameter_counts_are_data_driven() -> None:
    record = _record()
    second = deepcopy(record["quantizations"][0])
    second.update(quantization_id="unseen-fp16", bits_per_weight=16, download_bytes=6_200_000_000)
    record["quantizations"].append(second)
    model = parse_model_catalog(_catalog(record)).models[0]
    small, large = (
        estimate_model_suitability(model, quantization, _hardware(free_memory_bytes=3_000_000_000))
        for quantization in model.quantizations
    )
    assert small.grade == "suitable"
    assert large.grade == "not_recommended"
    assert large.required_disk_bytes == 6_200_000_000
    doubled = replace(model, parameter_count=6_000_000_000)
    result = estimate_model_suitability(doubled, doubled.quantizations[0], _hardware())
    assert result.weight_bytes == 3_000_000_000
    assert result.estimated_memory_bytes == 3_500_000_000


def test_gpu_uses_free_vram_and_target_bandwidth_observation() -> None:
    model = _model()
    hardware = _hardware(
        gpu_vram_bytes=8_000_000_000,
        gpu_free_vram_bytes=1_000_000_000,
        gpu_memory_bandwidth_bytes_per_second=100_000_000_000.0,
    )
    result = estimate_model_suitability(
        model, model.quantizations[0], hardware, execution_target="gpu"
    )
    assert result.grade == "not_recommended"
    assert result.available_memory_bytes == 1_000_000_000
    assert "FREE_MEMORY_INSUFFICIENT" in result.reason_codes
    assert "BANDWIDTH_UNKNOWN" not in result.reason_codes
    assert result.speed_estimate_tokens_per_second is None
    unknown = estimate_model_suitability(
        model,
        model.quantizations[0],
        replace(hardware, gpu_free_vram_bytes=None),
        execution_target="gpu",
    )
    assert unknown.grade == "unknown"
    assert unknown.available_memory_bytes is None
    assert "FREE_VRAM_UNKNOWN" in unknown.reason_codes
    suitable = estimate_model_suitability(
        model,
        model.quantizations[0],
        replace(hardware, gpu_free_vram_bytes=4_000_000_000),
        execution_target="gpu",
    )
    assert suitable.grade == "suitable"


def test_missing_bandwidth_does_not_invent_throughput_or_prevent_memory_estimate() -> None:
    model = _model()
    result = estimate_model_suitability(model, model.quantizations[0], _hardware())
    assert result.grade == "suitable"
    assert result.speed_estimate_tokens_per_second is None
    assert "BANDWIDTH_UNKNOWN" in result.reason_codes
    assert "SPEED_ESTIMATE_UNAVAILABLE" in result.reason_codes


def test_estimate_is_pure_and_name_independent(monkeypatch: pytest.MonkeyPatch) -> None:
    def forbidden_read(*args: object, **kwargs: object) -> None:
        raise AssertionError("estimator must not read runtime or hardware")

    model = _model()
    hardware = _hardware()
    before = deepcopy((model, hardware))
    monkeypatch.setattr(Path, "read_text", forbidden_read)
    reference = estimate_model_suitability(model, model.quantizations[0], hardware)
    for model_id in ("brand-new/nebula:7b", "timeout-error/not-downloaded", "arbitrary-secret-key"):
        renamed = replace(model, model_id=model_id)
        assert estimate_model_suitability(renamed, renamed.quantizations[0], hardware) == reference
    assert (model, hardware) == before
    with pytest.raises(FrozenInstanceError):
        hardware.free_disk_bytes = 0  # type: ignore[misc]


@pytest.mark.parametrize("value", [-1, 1.5, True, "1024", float("nan"), 2**64])
def test_invalid_capacity_is_rejected(value: Any) -> None:
    with pytest.raises(ModelGuidanceError):
        _hardware(free_disk_bytes=value)


@pytest.mark.parametrize("value", [0, -1, True, "100", float("nan"), float("inf"), 10**1000])
def test_invalid_bandwidth_is_rejected(value: Any) -> None:
    with pytest.raises(ModelGuidanceError):
        _hardware(host_memory_bandwidth_bytes_per_second=value)


def test_impossible_observations_and_unrelated_quantization_are_rejected() -> None:
    with pytest.raises(ModelGuidanceError):
        _hardware(host_ram_bytes=1, free_memory_bytes=2)
    with pytest.raises(ModelGuidanceError):
        _hardware(gpu_vram_bytes=1, gpu_free_vram_bytes=2)
    model = _model()
    unrelated = replace(model.quantizations[0], quantization_id="other-variant")
    with pytest.raises(ModelGuidanceError):
        estimate_model_suitability(model, unrelated, _hardware())
    with pytest.raises(ModelGuidanceError):
        estimate_model_suitability(
            model,
            model.quantizations[0],
            _hardware(),
            execution_target="cloud",  # type: ignore[arg-type]
        )


@pytest.mark.parametrize(
    "field,value",
    [
        ("evidence_kind", "deterministic_fixture"),
        ("envelope_version", 1),
        ("envelope_version", True),
        ("provider", "unrecognized"),
        ("provider", []),
        ("model_revision", ""),
        ("tested_on", "2026-02-30"),
        ("tested_on", "tomorrow"),
        ("report_reference", "https://example.invalid/report"),
        ("report_reference", "release-evidence/../private"),
        ("report_reference", "release-evidence//report"),
        ("tested_locales", ["en"]),
        ("tested_locales", ["en", "en"]),
        ("tested_locales", ["en", None]),
        ("cases_passed", 11),
        ("cases_total", 0),
    ],
)
def test_malformed_or_nonlive_envelope_evidence_is_rejected(field: str, value: Any) -> None:
    record = _record()
    record["quantizations"][0]["envelope_evidence"][field] = value
    with pytest.raises(ModelGuidanceError):
        parse_model_catalog(_catalog(record))


@pytest.mark.parametrize(
    "section,field",
    [
        ("model", "last_reviewed"),
        ("model", "license_id"),
        ("quantization", "envelope_evidence"),
        ("evidence", "model_revision"),
        ("evidence", "report_reference"),
    ],
)
def test_missing_fields_fail_closed(section: str, field: str) -> None:
    record = _record()
    target = record if section == "model" else record["quantizations"][0]
    if section == "evidence":
        target = target["envelope_evidence"]
    del target[field]
    with pytest.raises(ModelGuidanceError):
        parse_model_catalog(_catalog(record))


@pytest.mark.parametrize("section", ["model", "quantization", "evidence"])
def test_unknown_fields_fail_closed(section: str) -> None:
    record = _record()
    target = record if section == "model" else record["quantizations"][0]
    if section == "evidence":
        target = target["envelope_evidence"]
    target["unexpected"] = "unrelated text does not affect numeric decisions"
    with pytest.raises(ModelGuidanceError):
        parse_model_catalog(_catalog(record))


@pytest.mark.parametrize(
    "text",
    [
        "",
        "[",
        "schema_version: true\nmodels: []",
        "schema_version: 2\nmodels: []",
        "schema_version: 1\nmodels: {}",
        "schema_version: 1\nmodels: []\nmodels: []",
        "!!python/object/apply:builtins.print ['no execution']",
    ],
)
def test_bad_yaml_and_schema_are_rejected(text: str) -> None:
    with pytest.raises(ModelGuidanceError):
        parse_model_catalog(text)


def test_duplicate_nested_keys_and_ids_are_rejected() -> None:
    text = _catalog().replace(
        "parameter_count: 3000000000", "parameter_count: 3000000000\n  parameter_count: 1"
    )
    with pytest.raises(ModelGuidanceError):
        parse_model_catalog(text)
    with pytest.raises(ModelGuidanceError):
        parse_model_catalog(yaml.safe_dump({"schema_version": 1, "models": [_record(), _record()]}))
    record = _record()
    record["quantizations"].append(deepcopy(record["quantizations"][0]))
    with pytest.raises(ModelGuidanceError):
        parse_model_catalog(_catalog(record))


@pytest.mark.parametrize(
    "field,value",
    [
        ("parameter_count", 0),
        ("parameter_count", "3b"),
        ("parameter_count", True),
        ("last_reviewed", "2026-10-01"),
        ("source_url", "https://user:credential@example.invalid/a"),
        ("license_url", "file:///license"),
        ("quantizations", []),
    ],
)
def test_invalid_model_facts_are_rejected(field: str, value: Any) -> None:
    record = _record()
    record[field] = value
    with pytest.raises(ModelGuidanceError):
        parse_model_catalog(_catalog(record))


@pytest.mark.parametrize(
    "field,value",
    [
        ("bits_per_weight", 0),
        ("bits_per_weight", 65),
        ("bits_per_weight", 4.0),
        ("download_bytes", 0),
        ("memory_overhead_bytes", -1),
    ],
)
def test_invalid_quantization_facts_are_rejected(field: str, value: Any) -> None:
    record = _record()
    record["quantizations"][0][field] = value
    with pytest.raises(ModelGuidanceError):
        parse_model_catalog(_catalog(record))


def test_catalog_load_failure_has_safe_error_without_path(tmp_path: Path) -> None:
    with pytest.raises(ModelGuidanceError, match="catalog cannot be read as UTF-8") as caught:
        load_model_catalog(tmp_path / "unreadable-private-path.yml")
    assert "private-path" not in str(caught.value)
    path = tmp_path / "not-utf8.yml"
    path.write_bytes(b"\xff")
    with pytest.raises(ModelGuidanceError):
        load_model_catalog(path)


def test_authored_catalog_limits_fail_closed() -> None:
    with pytest.raises(ModelGuidanceError):
        parse_model_catalog(" " * 1_048_577)
    with pytest.raises(ModelGuidanceError):
        parse_model_catalog(yaml.safe_dump({"schema_version": 1, "models": [_record()] * 65}))
    record = _record()
    record["quantizations"] *= 17
    with pytest.raises(ModelGuidanceError):
        parse_model_catalog(_catalog(record))


@pytest.mark.parametrize("passed", range(12))
def test_partial_live_suite_never_qualifies_even_with_both_locales(passed: int) -> None:
    record = _record()
    evidence = record["quantizations"][0]["envelope_evidence"]
    evidence["tested_locales"] = ["en", "zh-TW"]
    evidence["cases_passed"] = passed
    with pytest.raises(ModelGuidanceError):
        parse_model_catalog(_catalog(record))
