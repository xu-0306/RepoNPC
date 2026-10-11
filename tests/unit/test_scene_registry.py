from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest
import yaml

from reponpc.config.models import SceneConfig
from reponpc.scene.registry import (
    SceneRegistryError,
    contrast_ratio,
    contrast_report,
    default_scene_registry,
    fallback_stylesheet,
    parse_scene_registry,
)

STARTER_IDS = {"neutral", "ocean", "forest", "sunset", "lavender"}
EXPECTED_ROLES = {
    "background",
    "surface",
    "surface_alt",
    "ink",
    "muted_ink",
    "accent",
    "accent_ink",
    "border",
    "stage",
    "focus",
}


def _test_scheme() -> dict[str, object]:
    return {
        "id": "unshipped_green",
        "version": 7,
        "label": {"zh-TW": "測試綠", "en": "Test Green"},
        "light": {
            "background": "#f5fff2",
            "surface": "#ffffff",
            "surface_alt": "#eaf5e6",
            "ink": "#17321b",
            "muted_ink": "#4f6652",
            "accent": "#276b39",
            "accent_ink": "#ffffff",
            "border": "#5a715e",
            "stage": "#cfe1d1",
            "focus": "#287a3f",
        },
        "dark": {
            "background": "#111a13",
            "surface": "#1a271d",
            "surface_alt": "#27362a",
            "ink": "#f4fbf5",
            "muted_ink": "#c4d0c6",
            "accent": "#8bd69b",
            "accent_ink": "#152317",
            "border": "#87998a",
            "stage": "#304635",
            "focus": "#93e0a3",
        },
    }


def _registry_data() -> dict[str, object]:
    return {"schemes": [_test_scheme()], "aliases": {"old_green": "unshipped_green"}}


def _yaml(data: object) -> str:
    return yaml.safe_dump(data, allow_unicode=True, sort_keys=False)


def _relative_luminance(color: str) -> float:
    channels = [int(color[index : index + 2], 16) / 255 for index in (1, 3, 5)]
    linear = [
        channel / 12.92 if channel <= 0.04045 else ((channel + 0.055) / 1.055) ** 2.4
        for channel in channels
    ]
    return sum(
        weight * channel for weight, channel in zip((0.2126, 0.7152, 0.0722), linear, strict=True)
    )


def _ratio(first: str, second: str) -> float:
    low, high = sorted((_relative_luminance(first), _relative_luminance(second)))
    return (high + 0.05) / (low + 0.05)


def test_authored_schemes_are_bilingual_versioned_and_meet_every_pair() -> None:
    registry = default_scene_registry()
    assert set(registry.schemes) == STARTER_IDS
    for scheme in registry.schemes.values():
        assert scheme.version >= 1
        assert set(scheme.label) == {"zh-TW", "en"}
        assert all(scheme.label[locale] for locale in ("zh-TW", "en"))
        for variant in ("light", "dark"):
            roles = scheme.variant(variant)
            assert set(roles) == EXPECTED_ROLES
            assert all(len(value) == 7 and value.startswith("#") for value in roles.values())
            for text in ("ink", "muted_ink"):
                for surface in ("background", "surface", "surface_alt"):
                    assert _ratio(roles[text], roles[surface]) >= 4.5
            assert _ratio(roles["accent_ink"], roles["accent"]) >= 4.5
            for edge in ("accent", "border", "focus"):
                for surface in ("background", "surface", "surface_alt"):
                    assert _ratio(roles[edge], roles[surface]) >= 3.0


def test_test_only_scheme_and_alias_resolve_without_frontend_changes() -> None:
    registry = parse_scene_registry(_yaml(_registry_data()))
    assert set(registry.schemes) == {"unshipped_green"}
    assert registry.canonical_id("old_green") == "unshipped_green"
    settings = SceneConfig.model_validate(
        {"color_scheme": "old_green"}, context={"scene_registry": registry}
    )
    assert settings.color_scheme == "unshipped_green"
    assert contrast_ratio("#000000", "#ffffff") == pytest.approx(21.0)


def test_packaged_registry_requires_the_default_neutral_scheme(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import reponpc.scene.registry as registry_module

    test_registry = parse_scene_registry(_yaml(_registry_data()))
    monkeypatch.setattr(registry_module, "load_scene_registry", lambda _path: test_registry)
    registry_module.default_scene_registry.cache_clear()
    try:
        with pytest.raises(SceneRegistryError, match="missing default scheme neutral"):
            registry_module.default_scene_registry()
    finally:
        registry_module.default_scene_registry.cache_clear()


def test_duplicate_yaml_mapping_key_fails_before_overwrite() -> None:
    with pytest.raises(SceneRegistryError, match="duplicate key"):
        parse_scene_registry("schemes: []\nschemes: []\naliases: {}\n")


def test_duplicate_scheme_id_and_missing_locale_fail() -> None:
    data = _registry_data()
    data["schemes"].append(deepcopy(data["schemes"][0]))
    with pytest.raises(SceneRegistryError, match="duplicate id"):
        parse_scene_registry(_yaml(data))

    data = _registry_data()
    del data["schemes"][0]["label"]["en"]
    with pytest.raises(SceneRegistryError, match="exactly zh-TW and en"):
        parse_scene_registry(_yaml(data))


@pytest.mark.parametrize(
    ("mutation", "expected"),
    [
        ("missing", "missing stage role"),
        ("unknown", "unknown scene_hint role"),
        ("hex", "role focus must be #rrggbb"),
    ],
)
def test_role_shape_and_hex_fail_with_context(mutation: str, expected: str) -> None:
    data = _registry_data()
    roles = data["schemes"][0]["light"]
    if mutation == "missing":
        del roles["stage"]
    elif mutation == "unknown":
        roles["scene_hint"] = "#112233"
    else:
        roles["focus"] = "red"
    with pytest.raises(SceneRegistryError, match=expected):
        parse_scene_registry(_yaml(data))


def test_authored_contrast_failure_names_scheme_variant_and_pair() -> None:
    data = _registry_data()
    data["schemes"][0]["light"]["ink"] = "#f5fff2"
    with pytest.raises(
        SceneRegistryError,
        match=r"scheme unshipped_green light: contrast ink/background",
    ):
        parse_scene_registry(_yaml(data))


@pytest.mark.parametrize("field", ["image", "backdrop", "pack", "species", "font", "css"])
def test_unknown_registry_fields_fail_closed(field: str) -> None:
    data = _registry_data()
    data["schemes"][0][field] = "unapproved"
    with pytest.raises(SceneRegistryError, match="scheme entry"):
        parse_scene_registry(_yaml(data))


def test_alias_problems_fail_closed() -> None:

    for aliases, phrase in (
        ({"old_a": "old_b", "old_b": "old_a"}, "alias cycle"),
        ({"old_a": "missing_target"}, "dangling target"),
        ({"unshipped_green": "unshipped_green"}, "conflicts with a live scheme id"),
    ):
        data = _registry_data()
        data["aliases"] = aliases
        with pytest.raises(SceneRegistryError, match=phrase):
            parse_scene_registry(_yaml(data))


def test_fallback_is_reproducible_and_tracks_normalized_registry_identity() -> None:
    registry = default_scene_registry()
    text = (Path(__file__).parents[2] / "src/reponpc/scene/color_schemes.yml").read_text(
        encoding="utf-8"
    )
    windows_registry = parse_scene_registry(text.replace("\n", "\r\n"))
    assert windows_registry.source_sha256 == registry.source_sha256
    assert fallback_stylesheet(registry) == fallback_stylesheet(windows_registry)
    fallback = fallback_stylesheet(registry).decode()
    assert ':root[data-visitor-mode="light"]' in fallback
    assert ':root[data-visitor-mode="dark"]' in fallback
    assert "prefers-color-scheme: dark" in fallback
    assert f"Registry SHA-256: {registry.source_sha256}" in fallback
    assert set(contrast_report(registry)["schemes"][0]["variants"]) == {"light", "dark"}
