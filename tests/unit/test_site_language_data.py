from __future__ import annotations

import io
import itertools
import json
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image

from reponpc.cards.production import _character_sprite, build_public_card_assets
from reponpc.cards.render import CardPalette, _Card, repository_count_text
from reponpc.config.models import ConfigValidationError, validate_public_config
from reponpc.i18n.languages import chrome_locale, get_language, language_tags
from reponpc.i18n.plan import LocaleNotEnabledError
from reponpc.indexing.public_profile import (
    PublicProfileError,
    available_locales,
    build_public_profile_bytes,
    localized_public_profile_bytes,
    parse_public_profile_bytes,
)
from reponpc.scene.resolve import resolve_scene
from reponpc.sharing.export import _rewrite_entry_html
from reponpc.sharing.readme import render_profile_readme
from tests.fixtures.bundles.site_languages import FIXTURE_CONFIG, site_data
from tests.unit.test_card_pixel import svg_to_image

TAGS = language_tags()
SITE_SETS = [
    tags for size in range(1, len(TAGS) + 1) for tags in itertools.combinations(TAGS, size)
] + [TAGS[1:] + TAGS[:1]]


@pytest.mark.parametrize("tags", SITE_SETS)
def test_every_registry_subset_and_rotated_order_loads(tags: tuple[str, ...]) -> None:
    config = validate_public_config(site_data(tags, default=tags[-1]))
    assert config.locales.supported == tags
    assert config.locales.default == tags[-1]
    assert config.schema_version == 1
    document = parse_public_profile_bytes(
        build_public_profile_bytes(
            config=config,
            index_version="site-languages",
            built_at=datetime(2026, 11, 3, tzinfo=UTC),
            repository_count=1,
        )
    )
    assert document.schema_version == 2
    assert tuple(document.locales) == tags
    assert available_locales(document) == [
        {"tag": tag, "endonym": get_language(tag).endonym} for tag in tags
    ]
    for tag in tags:
        payload = json.loads(localized_public_profile_bytes(document, tag))
        assert payload["locale"] == tag
        assert payload["available_locales"] == available_locales(document)
        assert payload["repositories"][0]["summary"].startswith(tag + ":")
        assert set(document.locales[tag].model_dump()) == {
            "profile",
            "repositories",
            "suggested_questions",
        }
    for tag in set(TAGS) - set(tags):
        with pytest.raises(LocaleNotEnabledError):
            localized_public_profile_bytes(document, tag)


@pytest.mark.parametrize("tag", TAGS)
@pytest.mark.parametrize(
    "field",
    [
        "profile.headline",
        "profile.bio",
        "profile.greeting",
        "profile.suggested_questions",
        "profile.links.0.label",
        "card.call_to_action",
        "repositories.0.role",
        "repositories.0.summary",
        "repositories.0.claims.0.statement",
    ],
)
@pytest.mark.parametrize("mutation", ["missing", "extra"])
def test_localized_values_require_exact_site_keys(tag: str, field: str, mutation: str) -> None:
    data = site_data((tag,))
    value = data
    for part in field.split("."):
        value = value[int(part)] if isinstance(value, list) else value[part]
    if mutation == "missing":
        del value[tag]
    else:
        value[next(other for other in TAGS if other != tag)] = next(iter(value.values()))
    with pytest.raises(ConfigValidationError) as error:
        validate_public_config(data)
    # Cross-field issues retain their existing safe root path and name the localized field.
    assert field.rsplit(".", 1)[-1] in str(error.value.issues)


@pytest.mark.parametrize("mutation", ["empty", "duplicate", "unknown", "default"])
def test_invalid_site_sets_name_the_locale_field(mutation: str) -> None:
    data = site_data((TAGS[0],))
    if mutation == "empty":
        data["locales"]["supported"] = []
    elif mutation == "duplicate":
        data["locales"]["supported"] *= 2
    elif mutation == "unknown":
        data["locales"]["supported"] = ["unknown"]
    else:
        data["locales"]["default"] = TAGS[-1]
    with pytest.raises(ConfigValidationError) as error:
        validate_public_config(data)
    assert all(issue.path.startswith("locales") for issue in error.value.issues)


@pytest.mark.parametrize("tag", TAGS)
@pytest.mark.parametrize("field", ["display_name", "links", "repository_count", "stars"])
def test_every_locale_is_compared_to_the_first(tag: str, field: str) -> None:
    tags = (*(other for other in TAGS if other != tag), tag)
    config = validate_public_config(site_data(tags))
    raw = json.loads(
        build_public_profile_bytes(
            config=config,
            index_version="site-languages",
            built_at=datetime(2026, 11, 3, tzinfo=UTC),
            repository_count=1,
        )
    )
    target = raw["locales"][tag]
    if field == "display_name":
        target["profile"][field] += " changed"
    elif field == "links":
        target["profile"]["links"][0]["url"] = "https://example.invalid/changed"
    elif field == "repository_count":
        target["repositories"] = []
    else:
        target["repositories"][0][field] = 3
    with pytest.raises(PublicProfileError):
        parse_public_profile_bytes(json.dumps(raw).encode())


@pytest.mark.parametrize("tag", TAGS)
def test_cards_readmes_and_scene_labels_for_every_registry_language(tag: str) -> None:
    config = validate_public_config(site_data((tag,)))
    assets = build_public_card_assets(config, config_directory=FIXTURE_CONFIG.parent)
    assert set(assets) == {
        "public/character.png",
        *{
            f"public/card-{theme}-{tag}.{extension}"
            for theme in ("light", "dark")
            for extension in ("svg", "gif", "png")
        },
    }
    for theme in ("light", "dark"):
        svg = assets[f"public/card-{theme}-{tag}.svg"]
        for extension in ("png", "gif"):
            with Image.open(
                io.BytesIO(assets[f"public/card-{theme}-{tag}.{extension}"])
            ) as rendered:
                assert rendered.size == (600, 180)
                assert rendered.convert("RGB").tobytes() == svg_to_image(svg).tobytes()
    scene = resolve_scene(
        config.character.scene,
        sprite_content=assets["public/character.png"],
        revision=config.character.revision,
    ).public
    for scheme in scene.schemes:
        assert set(scheme.label) == {chrome_locale(language) for language in TAGS}
        assert scheme.label[chrome_locale(tag)]
    document = parse_public_profile_bytes(
        build_public_profile_bytes(
            config=config,
            index_version="site-languages",
            built_at=datetime(2026, 11, 3, tzinfo=UTC),
            repository_count=1,
        )
    )
    readme = render_profile_readme(
        document.locales[tag], pages_url="https://example.github.io/", locale=tag
    )
    assert f"card-light-{tag}.gif".encode() in readme
    assert document.locales[tag].profile.headline.encode() in readme
    root = Path(__file__).parents[2] / "src" / "reponpc"
    readme_copy = json.loads((root / "sharing/readme_copy.json").read_text(encoding="utf-8"))
    card_copy = json.loads((root / "cards/copy.json").read_text(encoding="utf-8"))
    assert set(readme_copy) == set(card_copy) == set(TAGS)
    assert ("## " + readme_copy[tag]["projects"]).encode() in readme
    assert readme_copy[tag]["chat"].encode() in readme
    for count in (0, 1, 7):
        template = card_copy[tag]["one" if count == 1 else "many"]
        assert repository_count_text(count, tag) == template.format(count=count)
    assert repository_count_text(None, tag) is None


@pytest.mark.parametrize("default", TAGS)
def test_every_exported_html_page_uses_the_site_default(default: str) -> None:
    config = validate_public_config(site_data(TAGS, default=default))
    sprite = _character_sprite(config, config_directory=FIXTURE_CONFIG.parent)
    scene = resolve_scene(config.character.scene, sprite_content=sprite.content, revision=1).public
    snapshot = SimpleNamespace(document=SimpleNamespace(character=SimpleNamespace(scene=scene)))
    files = {
        "index.html": (
            b'<!doctype html><html lang="en" data-owner-mode="system" '
            b'data-visitor-toggle="true"><head><script src="./scene-mode.js"></script>'
            b"</head><body></body></html>"
        ),
        "nested/about.html": (
            b'<!doctype html><html lang="en"><head></head><body>About</body></html>'
        ),
    }
    _rewrite_entry_html(files, snapshot, "https://fixture.ts.net", default)
    assert all(f'<html lang="{default}"'.encode() in payload for payload in files.values())


@pytest.mark.parametrize("sample", ["软件项目", "áéíóúüñÁÉÍÓÚÜÑ¿¡"])
def test_bundled_fonts_render_glyphs_in_all_card_formats(sample: str) -> None:
    config = validate_public_config(site_data(TAGS))
    card = _Card(CardPalette(**config.card.themes.light.model_dump()))
    for role in ("display", "body"):
        font = card.pick(sample, role)
        assert all(bytes(font.getmask(char)) != bytes(font.getmask("\ue000")) for char in sample)
    # The fixture uses the production renderer; SVG consists of the same raster's pixel paths.
    from reponpc.cards.render import CardCopy, render_card_assets

    rendered = render_card_assets(
        copy=CardCopy(sample, sample, sample, 1),
        palette=CardPalette(**config.card.themes.light.model_dump()),
        sprite=_character_sprite(config, config_directory=FIXTURE_CONFIG.parent),
    )
    expected = svg_to_image(rendered.svg)
    for payload in (rendered.png, rendered.gif):
        with Image.open(io.BytesIO(payload)) as image:
            assert image.convert("RGB").tobytes() == expected.tobytes()
