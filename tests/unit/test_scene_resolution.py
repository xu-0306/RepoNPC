from __future__ import annotations

import hashlib
import io
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
import yaml
from PIL import Image, ImageDraw

from reponpc.cards.assets import FRAME_COLUMNS, FRAME_ROWS, FRAME_SIZE, HEIGHT, WIDTH
from reponpc.config.models import SceneConfig, load_public_config
from reponpc.indexing.public_profile import (
    PublicProfileError,
    build_public_profile_bytes,
    normalize_public_profile_scene,
    parse_public_profile_bytes,
)
from reponpc.scene.registry import SceneRegistry, default_scene_registry, parse_scene_registry
from reponpc.scene.resolve import (
    PublicScene,
    SceneResolutionError,
    _average_edge_color,
    resolve_scene,
)

ROOT = Path(__file__).parents[2]
PUBLIC_SCENE_KEYS = {
    "revision",
    "scheme",
    "color_mode",
    "visitor_mode_toggle",
    "visitor_scheme_choice",
    "npc_plate",
    "schemes",
    "themes",
    "background_url",
    "background_scaling",
    "background_focus",
    "background_dim",
}
PUBLIC_ROLES = {
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
    "sky",
    "horizon",
    "hill_far",
    "hill_near",
    "grass",
    "ground",
    "wood",
    "celestial",
}


def _sprite(
    state_colors: dict[int, str] | None = None,
    *,
    hidden: tuple[int, int, int, int] = (255, 0, 255, 0),
) -> bytes:
    colors = state_colors or {}
    image = Image.new("RGBA", (WIDTH, HEIGHT), hidden)
    draw = ImageDraw.Draw(image)
    for state in range(FRAME_ROWS):
        rgb = (*bytes.fromhex(colors.get(state, "111111")), 255)
        for column in range(FRAME_COLUMNS):
            left, top = column * FRAME_SIZE, state * FRAME_SIZE
            draw.rectangle((left + 16, top + 16, left + 47, top + 47), fill=rgb)
    output = io.BytesIO()
    image.save(output, "PNG")
    return output.getvalue()


def _test_only_registry() -> SceneRegistry:
    scheme = {
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
            "sky": "#ffffff",
            "horizon": "#bbbbbb",
            "hill_far": "#999999",
            "hill_near": "#333333",
            "grass": "#888888",
            "ground": "#222222",
            "wood": "#444444",
            "celestial": "#aaaaaa",
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
            "sky": "#101020",
            "horizon": "#222233",
            "hill_far": "#444455",
            "hill_near": "#181828",
            "grass": "#555533",
            "ground": "#222222",
            "wood": "#666655",
            "celestial": "#ddddcc",
        },
    }
    return parse_scene_registry(yaml.safe_dump({"schemes": [scheme], "aliases": {}}))


def _luminance(color: str) -> float:
    channels = [int(color[index : index + 2], 16) / 255 for index in (1, 3, 5)]
    linear = [
        channel / 12.92 if channel <= 0.04045 else ((channel + 0.055) / 1.055) ** 2.4
        for channel in channels
    ]
    return sum(
        weight * channel for weight, channel in zip((0.2126, 0.7152, 0.0722), linear, strict=True)
    )


def _ratio(first: str, second: str) -> float:
    low, high = sorted((_luminance(first), _luminance(second)))
    return (high + 0.05) / (low + 0.05)


def test_resolver_emits_exact_public_shape_and_frozen_roles() -> None:
    result = resolve_scene(SceneConfig(), sprite_content=_sprite(), revision=4)
    payload = result.public.model_dump(mode="json")
    assert set(payload) == PUBLIC_SCENE_KEYS
    assert payload["scheme"] == {"id": "meadow", "version": 1}
    assert payload["color_mode"] == "system"
    assert payload["visitor_mode_toggle"] is True
    assert payload["visitor_scheme_choice"] is True
    assert set(payload["npc_plate"]) == {"light", "dark"}
    assert [scheme["id"] for scheme in payload["schemes"]] == list(default_scene_registry().schemes)
    assert payload["background_url"] is None
    assert payload["background_scaling"] == "smooth"
    assert payload["background_focus"] == {"x": 50, "y": 50}
    assert payload["background_dim"] == "auto"
    assert set(payload["themes"]) == {"light", "dark"}
    assert all(set(theme) == PUBLIC_ROLES for theme in payload["themes"].values())
    assert all(theme["stage"] != theme["surface"] for theme in payload["themes"].values())
    assert "notices" not in payload


def test_public_scene_rejects_noncanonical_scheme_id_and_contrast_regressions() -> None:
    payload = resolve_scene(SceneConfig(), sprite_content=_sprite(), revision=1).public.model_dump(
        mode="json"
    )
    malformed_id = json.loads(json.dumps(payload))
    malformed_id["scheme"]["id"] = "../../scheme"
    with pytest.raises(ValueError):
        PublicScene.model_validate(malformed_id)

    low_contrast = json.loads(json.dumps(payload))
    low_contrast["themes"]["light"]["border"] = low_contrast["themes"]["light"]["background"]
    with pytest.raises(ValueError, match="border/background"):
        PublicScene.model_validate(low_contrast)


def test_unshipped_scheme_resolves_with_test_sheet_without_frontend_changes() -> None:
    registry = _test_only_registry()
    settings = SceneConfig.model_validate(
        {"color_scheme": "unshipped_green"}, context={"scene_registry": registry}
    )
    resolved = resolve_scene(settings, sprite_content=_sprite(), revision=1, registry=registry)
    assert resolved.public.scheme.id == "unshipped_green"
    assert resolved.public.scheme.version == 7


def test_all_animation_cells_contribute_to_their_own_edge_average() -> None:
    image = Image.new("RGBA", (WIDTH, HEIGHT), (12, 24, 36, 255))
    for column in range(FRAME_COLUMNS):
        image.paste(
            (200, 100, 50, 255),
            (column * FRAME_SIZE, 3 * FRAME_SIZE, (column + 1) * FRAME_SIZE, 4 * FRAME_SIZE),
        )

    expected_r = round((12 * 24 + 200 * 4) / 28)
    expected_g = round((24 * 24 + 100 * 4) / 28)
    expected_b = round((36 * 24 + 50 * 4) / 28)
    assert _average_edge_color(image) == f"#{expected_r:02x}{expected_g:02x}{expected_b:02x}"


def test_talking_frame_edge_changes_aggregate_stage_and_transparent_rgb_is_ignored() -> None:
    black = _sprite()
    talking_white = _sprite({4: "ffffff"})
    black_stage = resolve_scene(
        SceneConfig(), sprite_content=black, revision=1
    ).public.themes.dark.stage
    mixed_stage = resolve_scene(
        SceneConfig(), sprite_content=talking_white, revision=1
    ).public.themes.dark.stage
    assert black_stage != mixed_stage

    hidden_green = _sprite(hidden=(0, 255, 0, 0))
    hidden_blue = _sprite(hidden=(0, 0, 255, 0))
    first = resolve_scene(SceneConfig(), sprite_content=hidden_green, revision=1).public
    second = resolve_scene(SceneConfig(), sprite_content=hidden_blue, revision=1).public
    assert first.themes == second.themes
    before = hashlib.sha256(black).digest()
    resolve_scene(SceneConfig(), sprite_content=black, revision=1)
    assert hashlib.sha256(black).digest() == before


def test_stage_keeps_three_to_one_edge_contrast_and_notices_are_variant_private() -> None:
    result = resolve_scene(SceneConfig(accent="#777777"), sprite_content=_sprite(), revision=8)
    for variant in (result.public.themes.light, result.public.themes.dark):
        edge = "#111111"
        assert _ratio(edge, variant.stage) >= 3.0
        assert _ratio(variant.accent, variant.background) >= 3.0
        assert _ratio(variant.accent, variant.surface) >= 3.0
        assert _ratio(variant.accent, variant.surface_alt) >= 3.0
        assert _ratio(variant.accent_ink, variant.accent) >= 4.5
    accent_notices = [notice for notice in result.notices if notice.kind == "accent_adjusted"]
    assert accent_notices
    assert {notice.variant for notice in accent_notices} == {"light", "dark"}
    for notice in accent_notices:
        actual = getattr(result.public.themes, notice.variant).accent
        assert notice.adjusted_value == actual
        assert "contrast" in notice.reason


def test_invalid_sprite_error_does_not_echo_attacker_content() -> None:
    canary = b"PRIVATE-URL-CANARY"
    with pytest.raises(SceneResolutionError) as caught:
        resolve_scene(SceneConfig(), sprite_content=canary, revision=1)
    assert caught.value.code == "character_sprite_invalid"
    assert canary.decode() not in str(caught.value)


def test_profile_build_accepts_explicit_sheet_and_legacy_normalization_uses_it() -> None:
    config = load_public_config(ROOT / "reponpc.example.yml")
    timestamp = datetime(2026, 9, 29, tzinfo=UTC)
    no_scene = parse_public_profile_bytes(
        build_public_profile_bytes(
            config=config,
            index_version="scene-batch1",
            built_at=timestamp,
            repository_count=sum(repository.enabled for repository in config.repositories),
        )
    )
    assert no_scene.character.scene is None
    first = normalize_public_profile_scene(no_scene, sprite_content=_sprite())
    second = normalize_public_profile_scene(no_scene, sprite_content=_sprite({0: "ffffff"}))
    assert first.character.scene is not None
    assert second.character.scene is not None
    assert first.character.scene.themes != second.character.scene.themes

    built = parse_public_profile_bytes(
        build_public_profile_bytes(
            config=config,
            index_version="scene-batch1",
            built_at=timestamp,
            repository_count=sum(repository.enabled for repository in config.repositories),
            sprite_content=_sprite(),
        )
    )
    assert built.character.scene is not None
    assert built.character.scene.revision == built.character.revision
    assert set(built.character.scene.model_dump(mode="json")) == PUBLIC_SCENE_KEYS


def test_public_profile_rejects_scene_revision_mismatch() -> None:
    config = load_public_config(ROOT / "reponpc.example.yml")
    payload = json.loads(
        build_public_profile_bytes(
            config=config,
            index_version="scene-batch1",
            built_at=datetime(2026, 9, 29, tzinfo=UTC),
            repository_count=sum(repository.enabled for repository in config.repositories),
            sprite_content=_sprite(),
        )
    )
    payload["character"]["scene"]["revision"] += 1
    with pytest.raises(PublicProfileError):
        parse_public_profile_bytes(json.dumps(payload).encode())


@pytest.mark.parametrize("scheme_id", ["meadow", "sunset", "coast", "sakura"])
@pytest.mark.parametrize("variant,edge", [("light", "#000000"), ("dark", "#ffffff")])
def test_scene_separation_preserves_stage_when_both_layers_pass(
    scheme_id: str, variant: str, edge: str
) -> None:
    scheme = default_scene_registry().scheme(scheme_id)
    authored = scheme.variant(variant)
    assert all(_ratio(edge, authored[role]) >= 3.0 for role in ("sky", "hill_near"))
    result = resolve_scene(
        SceneConfig(color_scheme=scheme_id),
        sprite_content=_sprite(dict.fromkeys(range(FRAME_ROWS), edge[1:])),
        revision=2,
    )
    assert getattr(result.public.npc_plate, variant) is False
    assert getattr(result.public.themes, variant).model_dump() == dict(authored)


@pytest.mark.parametrize("scheme_id", ["meadow", "sunset", "coast", "sakura"])
@pytest.mark.parametrize("variant", ["light", "dark"])
def test_scene_matching_edge_gets_plate_without_adjusting_scene_colors(
    scheme_id: str, variant: str
) -> None:
    scheme = default_scene_registry().scheme(scheme_id)
    authored = scheme.variant(variant)
    edge = authored["sky"]
    result = resolve_scene(
        SceneConfig(color_scheme=scheme_id),
        sprite_content=_sprite(dict.fromkeys(range(FRAME_ROWS), edge[1:])),
        revision=2,
    )
    resolved = getattr(result.public.themes, variant).model_dump()
    assert getattr(result.public.npc_plate, variant) is True
    assert _ratio(edge, resolved["stage"]) >= 3.0
    assert {role: value for role, value in resolved.items() if role != "stage"} == {
        role: value for role, value in authored.items() if role != "stage"
    }
    assert any(
        notice.kind == "stage_plate"
        and notice.variant == variant
        and notice.adjusted_value == resolved["stage"]
        for notice in result.notices
    )


def test_image_keeps_stage_adjustment_and_only_fallback_needs_plate(monkeypatch) -> None:
    scheme = default_scene_registry().scheme("meadow")
    edge = scheme.light["stage"]
    sprite = _sprite(dict.fromkeys(range(FRAME_ROWS), edge[1:]))
    settings = SceneConfig(background_path="assets/scene/fixture.png")
    adjusted = resolve_scene(settings, sprite_content=sprite, revision=3)
    assert adjusted.public.npc_plate.light is False
    assert _ratio(edge, adjusted.public.themes.light.stage) >= 3.0
    assert adjusted.public.themes.light.stage != edge
    assert any(n.kind == "stage_adjusted" and n.variant == "light" for n in adjusted.notices)
    monkeypatch.setattr("reponpc.scene.resolve._nearest_lightness", lambda *_args: None)
    fallback = resolve_scene(settings, sprite_content=sprite, revision=3)
    assert fallback.public.npc_plate.light is True
    assert _ratio(edge, fallback.public.themes.light.stage) >= 3.0
    assert any(n.kind == "stage_plate" and n.variant == "light" for n in fallback.notices)


def test_every_catalog_entry_resolves_accent_and_is_deterministic() -> None:
    settings = SceneConfig(color_scheme="coast", accent="#333399", visitor_scheme_choice=False)
    first = resolve_scene(settings, sprite_content=_sprite(), revision=9).public
    second = resolve_scene(settings, sprite_content=_sprite(), revision=9).public
    assert first.model_dump_json() == second.model_dump_json()
    assert first.visitor_scheme_choice is False
    assert [scheme.id for scheme in first.schemes] == list(default_scene_registry().schemes)
    for scheme in first.schemes:
        authored = default_scene_registry().scheme(scheme.id)
        assert scheme.version == authored.version
        assert scheme.label == dict(authored.label)
        assert scheme.themes.light.accent == "#333399"
        for variant in ("light", "dark"):
            tokens = getattr(scheme.themes, variant)
            assert _ratio(tokens.accent_ink, tokens.accent) >= 4.5
            for surface in ("background", "surface", "surface_alt"):
                assert _ratio(tokens.accent, getattr(tokens, surface)) >= 3.0
            for role in (
                "sky",
                "horizon",
                "hill_far",
                "hill_near",
                "grass",
                "ground",
                "wood",
                "celestial",
            ):
                assert getattr(tokens, role) == authored.variant(variant)[role]
    selected = next(scheme for scheme in first.schemes if scheme.id == first.scheme.id)
    assert selected.themes == first.themes
    assert selected.npc_plate == first.npc_plate


@pytest.mark.parametrize("mutation", ["duplicate", "default", "scene_pair", "plate_bool", "labels"])
def test_public_catalog_rejects_malformed_or_inconsistent_entries(mutation: str) -> None:
    payload = resolve_scene(SceneConfig(), sprite_content=_sprite(), revision=1).public.model_dump(
        mode="json"
    )
    if mutation == "duplicate":
        payload["schemes"].append(payload["schemes"][0])
    elif mutation == "default":
        payload["schemes"] = payload["schemes"][1:]
    elif mutation == "scene_pair":
        tokens = payload["schemes"][1]["themes"]["dark"]
        tokens["wood"] = tokens["sky"]
    elif mutation == "plate_bool":
        payload["schemes"][1]["npc_plate"]["light"] = 1
    else:
        del payload["schemes"][1]["label"]["en"]
    with pytest.raises(ValueError):
        PublicScene.model_validate(payload)
