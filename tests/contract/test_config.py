from __future__ import annotations

import math
from copy import deepcopy
from pathlib import Path

import pytest
import yaml

from reponpc.config.models import ConfigValidationError, load_public_config, validate_public_config

ROOT = Path(__file__).parents[2]


def example_data() -> dict:
    return yaml.safe_load((ROOT / "reponpc.example.yml").read_text(encoding="utf-8"))


def assert_invalid(data: dict, expected_path: str) -> ConfigValidationError:
    with pytest.raises(ConfigValidationError) as captured:
        validate_public_config(data)
    assert any(expected_path in issue.path for issue in captured.value.issues)
    return captured.value


def test_normative_example_is_sufficient() -> None:
    config = load_public_config(ROOT / "reponpc.example.yml")
    assert config.schema_version == 1
    assert config.locales.supported == ("zh-TW", "en")
    assert len(config.repositories) == 2
    assert config.retrieval.embedding.adapter == "ollama"
    assert config.retrieval.embedding.model == "qwen3-embedding:0.6b"
    assert config.retrieval.embedding.dimension == 1024


def test_builtin_character_uses_versioned_pack_contract() -> None:
    config = load_public_config(ROOT / "reponpc.example.yml")
    assert config.character.builtin is not None
    assert config.character.builtin.pack_id == "core/humanoid"
    assert config.character.builtin.pack_version == 1
    assert config.character.builtin.options["attire"] == "adventurer"


def test_legacy_humanoid_fields_are_rejected_without_compatibility_aliases() -> None:
    data = example_data()
    data["character"]["builtin"] = {
        "body": "standard",
        "skin": "medium",
        "hair": "short",
        "outfit": "adventurer",
        "accessory": "glasses",
        "hair_color": "#2b1d14",
        "primary_color": "#6d5dfc",
        "secondary_color": "#f2c14e",
    }
    error = assert_invalid(data, "character.builtin")
    assert any(issue.code == "missing" for issue in error.issues)


@pytest.mark.parametrize(
    ("mutation", "expected_path", "expected_code"),
    [
        (("pack_id", "community/unknown"), "character.builtin", "unknown_pack"),
        (("pack_version", 2), "character.builtin", "pack_version_unsupported"),
        (("options.cape", "yes"), "character.builtin.options.cape", "unknown_option"),
    ],
)
def test_builtin_pack_registry_rejects_unknown_contract_values(
    mutation: tuple[str, object], expected_path: str, expected_code: str
) -> None:
    data = example_data()
    path, value = mutation
    if path.startswith("options."):
        data["character"]["builtin"]["options"][path.removeprefix("options.")] = value
    else:
        data["character"]["builtin"][path] = value

    error = assert_invalid(data, expected_path)
    assert error.issues[0].code == expected_code


@pytest.mark.parametrize("key", ["api_key", "password", "github_token", "private_url"])
def test_secret_fields_are_rejected_without_echoing_values(key: str) -> None:
    data = example_data()
    canary = "CANARY-DO-NOT-ECHO"
    data[key] = canary
    error = assert_invalid(data, key)
    assert canary not in str(error)
    assert canary not in repr(error.issues)


def test_unknown_root_key_is_rejected() -> None:
    data = example_data()
    data["mystery"] = True
    assert_invalid(data, "mystery")


def test_parent_path_is_rejected() -> None:
    data = example_data()
    data["repositories"][0]["include"] = ["../secret.txt"]
    assert_invalid(data, "repositories.0.include")


def test_duplicate_repository_and_claim_ids_are_rejected() -> None:
    data = example_data()
    data["repositories"].append(deepcopy(data["repositories"][0]))
    assert_invalid(data, "$")

    data = example_data()
    data["repositories"][1]["claims"][0]["id"] = data["repositories"][0]["claims"][0]["id"]
    assert_invalid(data, "$")


def test_missing_localized_value_is_rejected() -> None:
    data = example_data()
    del data["profile"]["headline"]["en"]
    assert_invalid(data, "$")


def test_invalid_url_and_zero_weights_are_rejected() -> None:
    data = example_data()
    data["profile"]["links"][0]["url"] = "javascript:alert(1)"
    assert_invalid(data, "profile.links.0.url")

    data = example_data()
    data["retrieval"]["fusion"]["lexical_weight"] = 0
    data["retrieval"]["fusion"]["vector_weight"] = 0
    assert_invalid(data, "retrieval.fusion")


def test_unsupported_locale_absolute_path_non_finite_weight_and_limit_are_rejected() -> None:
    data = example_data()
    data["locales"]["supported"].append("fr")
    assert_invalid(data, "locales.supported.2")

    data = example_data()
    data["repositories"][0]["include"] = ["/etc/passwd"]
    assert_invalid(data, "repositories.0.include")

    data = example_data()
    data["retrieval"]["fusion"]["lexical_weight"] = math.nan
    assert_invalid(data, "retrieval.fusion.lexical_weight")

    data = example_data()
    data["retrieval"]["chunking"]["max_characters"] = 12_001
    assert_invalid(data, "retrieval.chunking.max_characters")


def test_file_size_and_utf8_are_bounded(tmp_path: Path) -> None:
    oversized = tmp_path / "large.yml"
    oversized.write_bytes(b"x" * 16)
    with pytest.raises(ConfigValidationError) as captured:
        load_public_config(oversized, max_bytes=8)
    assert captured.value.issues[0].code == "file_too_large"

    invalid = tmp_path / "invalid.yml"
    invalid.write_bytes(b"\xff")
    with pytest.raises(ConfigValidationError) as captured:
        load_public_config(invalid)
    assert captured.value.issues[0].code == "invalid_encoding"
