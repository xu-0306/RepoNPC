"""Main's AC-072 fixture matrix uses an independent pixel-edge/contrast oracle."""

from __future__ import annotations

import io
from pathlib import Path

import pytest
from PIL import Image, ImageDraw

from reponpc.cards.assets import validate_sprite
from reponpc.cards.sprite_composer import compose_builtin
from reponpc.config.models import SceneConfig, load_public_config
from reponpc.scene.registry import default_scene_registry
from reponpc.scene.resolve import resolve_scene
from tests.security.test_a5_review import _contrast

ROOT = Path(__file__).resolve().parents[2]
KINDS = (
    "object",
    "grey",
    "near_white",
    "near_black",
    "saturated",
    "multi_hue",
    "matching_light_stage",
    "matching_dark_stage",
    "humanoid_light",
    "humanoid_dark",
)


def _character(kind: str, stage: str) -> bytes:
    if kind.startswith("humanoid"):
        config = load_public_config(ROOT / "tests/fixtures/phase2/reponpc.yml")
        assert config.character.builtin is not None
        options = dict(config.character.builtin.options)
        options.update(
            hair_color="#f3d9ba" if kind == "humanoid_light" else "#15171c",
            primary_color="#ebedf4" if kind == "humanoid_light" else "#172033",
        )
        return compose_builtin(config.character.builtin.model_copy(update={"options": options}))
    colors = {
        "object": ("#b87615",),
        "grey": ("#888888",),
        "near_white": ("#fdfdfd",),
        "near_black": ("#020202",),
        "saturated": ("#ff0000",),
        "multi_hue": ("#ff0000", "#00ff00", "#0000ff", "#ffe100"),
        "matching_light_stage": (stage,),
        "matching_dark_stage": (stage,),
    }[kind]
    image = Image.new("RGBA", (256, 448))
    draw = ImageDraw.Draw(image)
    for row in range(7):
        for column in range(4):
            x, y = column * 64 + 15, row * 64 + 16
            # A toolbox with a handle, never a cat or a humanoid illustration.
            draw.rectangle((x, y + 7, x + 33, y + 31), fill=colors[(row + column) % len(colors)])
            draw.rectangle((x + 9, y, x + 24, y + 8), fill=colors[(row + column) % len(colors)])
    output = io.BytesIO()
    image.save(output, "PNG")
    return validate_sprite(output.getvalue()).content


def _edge(content: bytes) -> str:
    with Image.open(io.BytesIO(content)) as image:
        pixels = image.convert("RGBA")
        channels = [0, 0, 0]
        weight = 0
        for y in range(448):
            for x in range(256):
                color = pixels.getpixel((x, y))
                if not color[3]:
                    continue
                neighbors = ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1))
                if all(
                    0 <= nx < 256
                    and 0 <= ny < 448
                    and (nx // 64, ny // 64) == (x // 64, y // 64)
                    and pixels.getpixel((nx, ny))[3]
                    for nx, ny in neighbors
                ):
                    continue
                weight += color[3]
                for index in range(3):
                    channels[index] += color[index] * color[3]
        assert weight
        return "#" + "".join(f"{round(channel / weight):02x}" for channel in channels)


def _background(kind: str) -> bytes | None:
    if kind == "no_image":
        return None
    image = Image.new("RGBA", (640, 360), (110, 130, 150, 255))
    if kind == "busy_image":
        # Reproducible varied image, including translucent samples over the scene surface.
        image.putdata(
            [
                (
                    (x * 7 + y * 3) % 256,
                    (x * 2 + y * 11) % 256,
                    (x * 13 + y) % 256,
                    80 + (x + y) % 176,
                )
                for y in range(360)
                for x in range(640)
            ]
        )
    output = io.BytesIO()
    image.save(output, "PNG")
    return output.getvalue()


@pytest.mark.parametrize("scheme_id", tuple(default_scene_registry().schemes))
@pytest.mark.parametrize("kind", KINDS)
@pytest.mark.parametrize("background_kind", ("no_image", "flat_image", "busy_image"))
def test_ac072_non_cat_fixture_scheme_variant_matrix(
    scheme_id: str, kind: str, background_kind: str
) -> None:
    scheme = default_scene_registry().scheme(scheme_id)
    stage = scheme.dark["stage"] if kind == "matching_dark_stage" else scheme.light["stage"]
    content = _character(kind, stage)
    edge = _edge(content)
    background = _background(background_kind)
    settings = SceneConfig(
        color_scheme=scheme_id,
        background_path="assets/scene/matrix.png" if background is not None else None,
    )
    scene = resolve_scene(
        settings, sprite_content=content, background_content=background, revision=17
    ).public
    assert (
        scene.model_dump_json()
        == resolve_scene(
            settings, sprite_content=bytes(content), background_content=background, revision=17
        ).public.model_dump_json()
    )
    assert (scene.background_url is not None) == (background is not None)
    if background is not None:
        assert scene.background_dim in {"none", "low", "medium", "high"}
    for variant in ("light", "dark"):
        roles = getattr(scene.themes, variant).model_dump()
        authored = getattr(scheme, variant)
        assert {key: value for key, value in roles.items() if key != "stage"} == {
            key: value for key, value in authored.items() if key != "stage"
        }
        assert _contrast(edge, roles["stage"]) >= 3.0
        for surface in ("background", "surface", "surface_alt"):
            for text in ("ink", "muted_ink"):
                assert _contrast(roles[text], roles[surface]) >= 4.5
            for boundary in ("accent", "border", "focus"):
                assert _contrast(roles[boundary], roles[surface]) >= 3.0
        assert _contrast(roles["accent_ink"], roles["accent"]) >= 4.5
