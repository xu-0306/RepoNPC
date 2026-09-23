"""Focused coverage for the bounded passage-vector cache."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from reponpc.indexing.passage_cache import PassageVectorCache
from reponpc.indexing.sources import EmbeddingIdentity


@dataclass
class Provider:
    identity_value: EmbeddingIdentity = field(
        default_factory=lambda: EmbeddingIdentity("fixture", "model-a", 2, True, "", "")
    )
    calls: list[list[str]] = field(default_factory=list)
    output: np.ndarray | None = None

    def identity(self) -> EmbeddingIdentity:
        return self.identity_value

    def embed_passages(self, texts: list[str]) -> np.ndarray:
        self.calls.append(list(texts))
        if self.output is not None:
            return self.output
        return np.asarray([_vector_for(text) for text in texts], dtype=np.float32)


def _vector_for(text: str) -> tuple[float, float]:
    return (1.0, 0.0) if text.casefold().startswith(("a", "c")) else (0.0, 1.0)


def _identity(**changes: Any) -> EmbeddingIdentity:
    values: dict[str, Any] = {
        "adapter": "fixture",
        "model_id": "model-a",
        "dimension": 2,
        "normalized": True,
        "query_prefix": "",
        "passage_prefix": "",
    }
    values.update(changes)
    return EmbeddingIdentity(**values)


def _cache_files(root: Path) -> list[Path]:
    return sorted(root.glob("*.json"))


def test_reuses_exact_inputs_preserves_order_and_batches_unique_misses(tmp_path: Path) -> None:
    provider = Provider()
    cache = PassageVectorCache(tmp_path)

    first = cache.embed_passages(provider, ["alpha", "beta", "alpha"])
    second = cache.embed_passages(provider, ["alpha", "beta", "alpha"])
    partial = cache.embed_passages(provider, ["beta", "gamma", "beta"])

    assert provider.calls == [["alpha", "beta"], ["gamma"]]
    assert np.array_equal(first, second)
    assert np.array_equal(partial, np.asarray([[0, 1], [0, 1], [0, 1]], dtype=np.float32))
    assert all("alpha" not in path.read_text(encoding="utf-8") for path in _cache_files(tmp_path))


def test_identity_model_prefix_and_dimension_changes_are_cache_misses(tmp_path: Path) -> None:
    provider = Provider()
    cache = PassageVectorCache(tmp_path)

    cache.embed_passages(provider, ["same"])
    provider.identity_value = _identity(model_id="model-b")
    cache.embed_passages(provider, ["same"])
    provider.identity_value = _identity(passage_prefix="passage: ")
    cache.embed_passages(provider, ["same"])
    provider.identity_value = _identity(dimension=3)
    provider.output = np.asarray([[1, 0, 0]], dtype=np.float32)
    cache.embed_passages(provider, ["same"])

    assert provider.calls == [["same"], ["same"], ["same"], ["same"]]
    assert len(_cache_files(tmp_path)) == 4


def test_corrupt_and_expired_entries_are_recomputed(tmp_path: Path) -> None:
    now = [100.0]
    provider = Provider()
    cache = PassageVectorCache(tmp_path, ttl_seconds=10, clock=lambda: now[0])

    cache.embed_passages(provider, ["corrupt", "expired"])
    files = _cache_files(tmp_path)
    assert len(files) == 2
    files[0].write_text("not-json", encoding="utf-8")
    now[0] = 111.0

    cache.embed_passages(provider, ["corrupt", "expired"])

    assert provider.calls == [["corrupt", "expired"], ["corrupt", "expired"]]


def test_oldest_entries_are_evicted_to_capacity(tmp_path: Path) -> None:
    provider = Provider()
    warm_cache = PassageVectorCache(tmp_path, clock=lambda: 1.0)
    warm_cache.embed_passages(provider, ["first"])
    first_size = _cache_files(tmp_path)[0].stat().st_size
    assert first_size > 0

    now = [2.0]
    bounded = PassageVectorCache(tmp_path, max_bytes=first_size + 1, clock=lambda: now[0])
    bounded.embed_passages(provider, ["second"])

    assert len(_cache_files(tmp_path)) == 1
    assert provider.calls[-1] == ["second"]


@pytest.mark.parametrize(
    "output",
    [
        np.asarray([[1.0, 0.0]], dtype=np.float64),
        np.asarray([[1.0, 0.0, 0.0]], dtype=np.float32),
        np.asarray([[np.nan, 0.0]], dtype=np.float32),
        np.asarray([[0.5, 0.5]], dtype=np.float32),
    ],
)
def test_invalid_provider_output_is_rejected_and_not_cached(
    tmp_path: Path, output: np.ndarray
) -> None:
    provider = Provider(output=output)

    with pytest.raises(ValueError, match="invalid vectors"):
        PassageVectorCache(tmp_path).embed_passages(provider, ["passage"])

    assert not _cache_files(tmp_path)


def test_disk_write_failure_does_not_mask_valid_provider_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    provider = Provider()
    cache = PassageVectorCache(tmp_path)

    def fail_replace(_source: object, _destination: object) -> None:
        raise OSError("disk full")

    monkeypatch.setattr("reponpc.indexing.passage_cache.os.replace", fail_replace)

    result = cache.embed_passages(provider, ["passage"])

    assert np.array_equal(result, np.asarray([[0.0, 1.0]], dtype=np.float32))
    assert provider.calls == [["passage"]]


@pytest.mark.parametrize(
    ("name", "value"),
    [("max_bytes", 0), ("max_bytes", True), ("ttl_seconds", 0), ("ttl_seconds", float("inf"))],
)
def test_constructor_rejects_unbounded_configuration(
    name: str, value: object, tmp_path: Path
) -> None:
    with pytest.raises(ValueError):
        PassageVectorCache(tmp_path, **{name: value})  # type: ignore[arg-type]


def test_payload_is_json_without_source_text_and_has_integrity_fields(tmp_path: Path) -> None:
    provider = Provider()
    PassageVectorCache(tmp_path).embed_passages(provider, ["private source text"])

    payload = json.loads(_cache_files(tmp_path)[0].read_text(encoding="utf-8"))

    assert "private source text" not in json.dumps(payload)
    assert payload["dtype"] == "float32"
    assert payload["shape"] == [2]
    assert payload["vector_sha256"]
    assert payload["payload_sha256"]
