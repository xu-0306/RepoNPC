"""Public configuration can identify only the owner-approved built-in source."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from reponpc.config.models import EmbeddingConfig
from reponpc.providers.builtin_artifacts import builtin_embedding_identity


def _values() -> dict[str, object]:
    identity = builtin_embedding_identity()
    return {
        "adapter": identity.adapter,
        "model": identity.model_id,
        "dimension": identity.dimension,
        "normalized": True,
        "query_prefix": "",
        "passage_prefix": "",
    }


def test_builtin_config_preserves_exact_revision_and_no_prefixes() -> None:
    config = EmbeddingConfig.model_validate(_values())
    assert config.model == builtin_embedding_identity().model_id
    assert config.dimension == 1024
    assert config.query_prefix == config.passage_prefix == ""


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("model", "BAAI/bge-m3"),
        ("model", "BAAI/bge-m3:" + "a" * 40),
        ("model", "other/model"),
        ("dimension", 384),
        ("query_prefix", "query: "),
        ("passage_prefix", "passage: "),
    ],
)
def test_public_builtin_identity_cannot_select_alternate_artifacts(
    field: str, value: object
) -> None:
    values = _values()
    values[field] = value
    with pytest.raises(ValidationError):
        EmbeddingConfig.model_validate(values)


def test_external_embedding_identity_remains_independent() -> None:
    values = _values()
    values.update(
        adapter="ollama", model="owner-chosen-model", dimension=384, query_prefix="query: "
    )
    config = EmbeddingConfig.model_validate(values)
    assert config.adapter == "ollama" and config.model == "owner-chosen-model"


def test_builtin_config_accepts_no_local_path_or_download_url() -> None:
    for field in ("model_path", "download_url"):
        values = _values()
        values[field] = "untrusted"
        with pytest.raises(ValidationError):
            EmbeddingConfig.model_validate(values)
