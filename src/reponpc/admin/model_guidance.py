"""Owner-only catalog facts and pure resource estimates; never probe or select a model.

Catalog evidence is an authored record of a live envelope-v2 test, not proof
created by this loader. Runtime capability testing is still required. Estimates
cover weights plus the catalog's explicit overhead, not measured performance or
a guarantee that a provider can load a model at every context length.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path, PurePosixPath
from typing import Literal
from urllib.parse import urlsplit

import yaml

SuitabilityGrade = Literal["suitable", "marginal", "not_recommended", "unknown"]
ExecutionTarget = Literal["cpu", "gpu"]
_MODEL_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:/-]{0,255}\Z")
_MAX_INTEGER = 2**63 - 1


class ModelGuidanceError(ValueError):
    """Safe, content-free validation failure for this internal guidance leaf."""


@dataclass(frozen=True, slots=True)
class EnvelopeEvidence:
    evidence_kind: Literal["live_provider"]
    envelope_version: Literal[2]
    provider: Literal["ollama", "openai_compatible", "vllm"]
    model_revision: str
    tested_on: date
    report_reference: str
    tested_locales: tuple[str, ...]
    cases_passed: int
    cases_total: int

    def __post_init__(self) -> None:
        if (
            self.evidence_kind != "live_provider"
            or type(self.envelope_version) is not int
            or self.envelope_version != 2
            or not isinstance(self.provider, str)
            or self.provider not in {"ollama", "openai_compatible", "vllm"}
            or type(self.tested_on) is not date
            or type(self.tested_locales) is not tuple
            or any(not isinstance(locale, str) for locale in self.tested_locales)
            or sorted(self.tested_locales) != ["en", "zh-TW"]
        ):
            raise ModelGuidanceError("invalid live envelope evidence")
        _identifier(self.model_revision)
        _integer(self.cases_total, minimum=1)
        _integer(self.cases_passed, minimum=1)
        if self.cases_passed != self.cases_total:
            raise ModelGuidanceError("envelope evidence must record all cases passing")
        if not isinstance(self.report_reference, str):
            raise ModelGuidanceError("invalid evidence report reference")
        parts = self.report_reference.split("/")
        if (
            len(self.report_reference) > 256
            or len(parts) < 2
            or parts[0] != "release-evidence"
            or any(part in {"", ".", ".."} for part in parts)
            or "\\" in self.report_reference
            or ":" in self.report_reference
            or PurePosixPath(self.report_reference).is_absolute()
            or any(ord(character) < 32 for character in self.report_reference)
        ):
            raise ModelGuidanceError("invalid evidence report reference")


@dataclass(frozen=True, slots=True)
class ModelQuantization:
    quantization_id: str
    bits_per_weight: int
    download_bytes: int
    memory_overhead_bytes: int
    envelope_evidence: EnvelopeEvidence

    def __post_init__(self) -> None:
        _identifier(self.quantization_id)
        _integer(self.bits_per_weight, minimum=1)
        if self.bits_per_weight > 64:
            raise ModelGuidanceError("invalid bits per weight")
        _integer(self.download_bytes, minimum=1)
        _integer(self.memory_overhead_bytes, minimum=0)
        if not isinstance(self.envelope_evidence, EnvelopeEvidence):
            raise ModelGuidanceError("live envelope evidence is required")


@dataclass(frozen=True, slots=True)
class CatalogModel:
    model_id: str
    parameter_count: int
    last_reviewed: date
    source_url: str
    license_id: str
    license_url: str
    quantizations: tuple[ModelQuantization, ...]

    def __post_init__(self) -> None:
        _identifier(self.model_id)
        _integer(self.parameter_count, minimum=1)
        _public_url(self.source_url)
        _public_url(self.license_url)
        _identifier(self.license_id)
        if type(self.last_reviewed) is not date:
            raise ModelGuidanceError("invalid catalog review date")
        if (
            type(self.quantizations) is not tuple
            or not self.quantizations
            or len(self.quantizations) > 16
            or any(not isinstance(item, ModelQuantization) for item in self.quantizations)
        ):
            raise ModelGuidanceError("catalog quantizations must be a non-empty tuple")
        if len({item.quantization_id for item in self.quantizations}) != len(self.quantizations):
            raise ModelGuidanceError("duplicate quantization id")
        if any(
            item.envelope_evidence.tested_on > self.last_reviewed for item in self.quantizations
        ):
            raise ModelGuidanceError("catalog review precedes envelope evidence")


@dataclass(frozen=True, slots=True)
class ModelCatalog:
    models: tuple[CatalogModel, ...]
    schema_version: Literal[1] = 1

    def __post_init__(self) -> None:
        if type(self.schema_version) is not int or self.schema_version != 1:
            raise ModelGuidanceError("unsupported catalog schema")
        if (
            type(self.models) is not tuple
            or len(self.models) > 64
            or any(not isinstance(model, CatalogModel) for model in self.models)
        ):
            raise ModelGuidanceError("invalid catalog models")
        if len({model.model_id for model in self.models}) != len(self.models):
            raise ModelGuidanceError("duplicate catalog model id")


@dataclass(frozen=True, slots=True)
class HardwareProfile:
    """Supplied observations in bytes; None means unknown, while zero is known."""

    host_ram_bytes: int | None = None
    free_memory_bytes: int | None = None
    free_disk_bytes: int | None = None
    gpu_vram_bytes: int | None = None
    gpu_free_vram_bytes: int | None = None
    host_memory_bandwidth_bytes_per_second: float | None = None
    gpu_memory_bandwidth_bytes_per_second: float | None = None

    def __post_init__(self) -> None:
        for value in (
            self.host_ram_bytes,
            self.free_memory_bytes,
            self.free_disk_bytes,
            self.gpu_vram_bytes,
            self.gpu_free_vram_bytes,
        ):
            if value is not None:
                _integer(value, minimum=0)
        for free, total in (
            (self.free_memory_bytes, self.host_ram_bytes),
            (self.gpu_free_vram_bytes, self.gpu_vram_bytes),
        ):
            if free is not None and total is not None and free > total:
                raise ModelGuidanceError("free memory exceeds total memory")
        for bandwidth_value in (
            self.host_memory_bandwidth_bytes_per_second,
            self.gpu_memory_bandwidth_bytes_per_second,
        ):
            if bandwidth_value is not None and (
                type(bandwidth_value) not in {int, float}
                or not 0 < bandwidth_value <= 10**15
                or not math.isfinite(bandwidth_value)
            ):
                raise ModelGuidanceError("bandwidth must be finite and positive")


@dataclass(frozen=True, slots=True)
class ModelSuitability:
    grade: SuitabilityGrade
    reason_codes: tuple[str, ...]
    execution_target: ExecutionTarget
    weight_bytes: int
    estimated_memory_bytes: int
    required_disk_bytes: int
    available_memory_bytes: int | None
    available_disk_bytes: int | None
    speed_estimate_tokens_per_second: None = None


class _UniqueKeyLoader(yaml.SafeLoader):
    """Same safe, duplicate-key-rejecting pattern as the packaged scene registry."""


def _unique_mapping(
    loader: _UniqueKeyLoader, node: yaml.MappingNode, deep: bool = False
) -> dict[str, object]:
    loader.flatten_mapping(node)
    result: dict[str, object] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if not isinstance(key, str) or key in result:
            raise ModelGuidanceError("catalog mapping keys must be unique strings")
        result[key] = loader.construct_object(value_node, deep=deep)
    return result


_UniqueKeyLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _unique_mapping)


def parse_model_catalog(text: str) -> ModelCatalog:
    """Parse a closed authored YAML schema; metadata reads perform no live test."""
    if not isinstance(text, str) or len(text) > 1_048_576:
        raise ModelGuidanceError("catalog text must be bounded")
    try:
        raw = yaml.load(text, Loader=_UniqueKeyLoader)
    except (yaml.YAMLError, RecursionError):
        raise ModelGuidanceError("catalog YAML is malformed") from None
    root = _mapping(raw, {"schema_version", "models"})
    if type(root["schema_version"]) is not int or root["schema_version"] != 1:
        raise ModelGuidanceError("unsupported catalog schema")
    models = []
    for item in _list(root["models"]):
        entry = _mapping(
            item,
            {
                "model_id",
                "parameter_count",
                "last_reviewed",
                "source_url",
                "license_id",
                "license_url",
                "quantizations",
            },
        )
        quantizations = []
        for quantization in _list(entry["quantizations"], maximum=16):
            values = _mapping(
                quantization,
                {
                    "quantization_id",
                    "bits_per_weight",
                    "download_bytes",
                    "memory_overhead_bytes",
                    "envelope_evidence",
                },
            )
            evidence = _mapping(
                values["envelope_evidence"], set(EnvelopeEvidence.__dataclass_fields__)
            )
            evidence["tested_on"] = _date(evidence["tested_on"])
            evidence["tested_locales"] = tuple(_list(evidence["tested_locales"], maximum=2))
            values["envelope_evidence"] = EnvelopeEvidence(**evidence)  # type: ignore[arg-type]
            quantizations.append(ModelQuantization(**values))  # type: ignore[arg-type]
        entry["last_reviewed"] = _date(entry["last_reviewed"])
        entry["quantizations"] = tuple(quantizations)
        models.append(CatalogModel(**entry))  # type: ignore[arg-type]
    return ModelCatalog(tuple(models))


def load_model_catalog(path: str | Path | None = None) -> ModelCatalog:
    """Read UTF-8 catalog data only; None uses the packaged catalog."""
    try:
        content = Path(path) if path is not None else Path(__file__).with_name("model_catalog.yml")
        text = content.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        raise ModelGuidanceError("catalog cannot be read as UTF-8") from None
    return parse_model_catalog(text)


def estimate_model_suitability(
    model: CatalogModel,
    quantization: ModelQuantization,
    hardware: HardwareProfile,
    *,
    execution_target: ExecutionTarget = "cpu",
) -> ModelSuitability:
    """Estimate full CPU/GPU residency with 20% memory and download-disk headroom.

    GPU estimates require *free* VRAM, never assume total VRAM is available,
    and describe full offload only. Loading/staging and partial offload are not
    modeled. Any missing relevant capacity gives unknown, even if another known
    capacity fails; reason codes preserve that failure. Bandwidth alone cannot
    establish throughput, so speed remains unavailable even when it is supplied.
    """
    if execution_target not in {"cpu", "gpu"}:
        raise ModelGuidanceError("invalid execution target")
    if quantization not in model.quantizations:
        raise ModelGuidanceError("quantization does not belong to this catalog model")
    weights = (model.parameter_count * quantization.bits_per_weight + 7) // 8
    memory = weights + quantization.memory_overhead_bytes
    if execution_target == "cpu":
        total, available = hardware.host_ram_bytes, hardware.free_memory_bytes
        bandwidth = hardware.host_memory_bandwidth_bytes_per_second
        total_unknown, free_unknown = "HOST_RAM_UNKNOWN", "FREE_MEMORY_UNKNOWN"
    else:
        total, available = hardware.gpu_vram_bytes, hardware.gpu_free_vram_bytes
        bandwidth = hardware.gpu_memory_bandwidth_bytes_per_second
        total_unknown, free_unknown = "GPU_VRAM_UNKNOWN", "FREE_VRAM_UNKNOWN"
    reasons = []
    if total is None:
        reasons.append(total_unknown)
    if available is None:
        reasons.append(free_unknown)
    if hardware.free_disk_bytes is None:
        reasons.append("FREE_DISK_UNKNOWN")
    incomplete = bool(reasons)
    if total is not None and total < memory:
        reasons.append("TOTAL_MEMORY_INSUFFICIENT")
    if available is not None and available < memory:
        reasons.append("FREE_MEMORY_INSUFFICIENT")
    if (
        hardware.free_disk_bytes is not None
        and hardware.free_disk_bytes < quantization.download_bytes
    ):
        reasons.append("FREE_DISK_INSUFFICIENT")
    if incomplete:
        grade: SuitabilityGrade = "unknown"
    elif reasons:
        grade = "not_recommended"
    else:
        assert available is not None and hardware.free_disk_bytes is not None
        if available * 5 < memory * 6:
            reasons.append("MEMORY_HEADROOM_LOW")
        if hardware.free_disk_bytes * 5 < quantization.download_bytes * 6:
            reasons.append("DISK_HEADROOM_LOW")
        grade = "marginal" if reasons else "suitable"
    if bandwidth is None:
        reasons.append("BANDWIDTH_UNKNOWN")
    reasons.append("SPEED_ESTIMATE_UNAVAILABLE")
    return ModelSuitability(
        grade=grade,
        reason_codes=tuple(reasons),
        execution_target=execution_target,
        weight_bytes=weights,
        estimated_memory_bytes=memory,
        required_disk_bytes=quantization.download_bytes,
        available_memory_bytes=available,
        available_disk_bytes=hardware.free_disk_bytes,
    )


def _mapping(value: object, keys: set[str]) -> dict[str, object]:
    if not isinstance(value, dict) or set(value) != keys:
        raise ModelGuidanceError("catalog mapping has missing or unknown fields")
    return dict(value)


def _list(value: object, *, maximum: int = 64) -> list[object]:
    if not isinstance(value, list) or len(value) > maximum:
        raise ModelGuidanceError("catalog field must be a bounded list")
    return value


def _integer(value: object, *, minimum: int) -> None:
    if type(value) is not int or not minimum <= value <= _MAX_INTEGER:
        raise ModelGuidanceError("catalog and hardware numbers must be valid integers")


def _identifier(value: object) -> None:
    if not isinstance(value, str) or not _MODEL_ID.fullmatch(value):
        raise ModelGuidanceError("invalid catalog identifier")


def _public_url(value: object) -> None:
    # An authored public source/license link is data, never an egress target.
    if (
        not isinstance(value, str)
        or len(value) > 512
        or any(character.isspace() or ord(character) < 32 for character in value)
    ):
        raise ModelGuidanceError("invalid public catalog URL")
    try:
        parsed = urlsplit(value)
        valid = (
            parsed.scheme == "https"
            and parsed.hostname is not None
            and parsed.username is None
            and parsed.password is None
            and parsed.port is None
            and not parsed.query
            and not parsed.fragment
        )
    except ValueError:
        valid = False
    if not valid:
        raise ModelGuidanceError("invalid public catalog URL")


def _date(value: object) -> date:
    if type(value) is date:
        return value
    if isinstance(value, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        try:
            return date.fromisoformat(value)
        except ValueError:
            pass
    raise ModelGuidanceError("catalog dates must be ISO calendar dates")
