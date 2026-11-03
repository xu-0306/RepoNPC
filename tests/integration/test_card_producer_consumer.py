from __future__ import annotations

import io
import xml.etree.ElementTree as ET
from pathlib import Path

import yaml
from PIL import Image

import reponpc.cards.render as card_render
from reponpc.cards.assets import HEIGHT, WIDTH
from reponpc.cards.production import build_public_card_assets
from reponpc.config.models import load_public_config
from reponpc.indexing.pipeline import build_index_bundle
from reponpc.indexing.sources import ResolvedConfiguration
from tests.integration.test_index_build import (
    DeterministicEmbeddingProvider,
    _fixture_snapshot,
)
from tests.unit.test_card_pixel import svg_to_image


class _Resolver:
    def resolve(self, *, slug: str, ref: str | None):
        del slug, ref
        return _fixture_snapshot()


def test_config_produces_complete_deterministic_bundle_assets_for_real_consumers() -> None:
    path = Path("tests/fixtures/phase2/reponpc.yml")
    config = load_public_config(path)

    first = build_public_card_assets(config, config_directory=path.parent)
    second = build_public_card_assets(config, config_directory=path.parent)

    assert first == second
    assert set(first) == {
        "public/character.png",
        *{
            f"public/card-{theme}-{locale}.{extension}"
            for theme in ("light", "dark")
            for locale in ("zh-TW", "en")
            for extension in ("svg", "gif", "png")
        },
    }
    with Image.open(io.BytesIO(first["public/character.png"])) as character:
        assert character.size == (WIDTH, HEIGHT)
    for name, payload in first.items():
        if name.endswith(".svg"):
            assert ET.fromstring(payload).attrib["viewBox"] == "0 0 600 180"
        elif "card-" in name:
            with Image.open(io.BytesIO(payload)) as card:
                assert card.size == (600, 180)


def test_index_build_generates_cards_without_prebuilt_public_directory(tmp_path: Path) -> None:
    fixture = Path("tests/fixtures/phase2/reponpc.yml")
    config_path = tmp_path / "reponpc.yml"
    content = fixture.read_text(encoding="utf-8")
    config_path.write_text(content, encoding="utf-8")

    bundle = build_index_bundle(
        config_path,
        tmp_path / "dist",
        resolver=_Resolver(),
        embedding_provider=DeterministicEmbeddingProvider(),
        configuration_source=ResolvedConfiguration(
            repository_slug="fixture-owner/reponpc-demo",
            commit_sha="a" * 40,
            path="reponpc.yml",
            content=content,
            github_html_url="https://github.com/fixture-owner/reponpc-demo",
        ),
    )

    assert bundle.archive_path.is_file()


def test_long_bilingual_copy_is_readable_across_every_card_variant(tmp_path: Path) -> None:
    fixture = Path("tests/fixtures/phase2/reponpc.yml")
    data = yaml.safe_load(fixture.read_text(encoding="utf-8"))
    data["profile"]["display_name"] = "RepoNPC超長角色名稱" * 6
    data["profile"]["headline"] = {
        "zh-TW": "以可驗證證據打造可靠又清楚的開源專案導覽" * 8,
        "en": "https://example.invalid/" + "unbroken-verifiable-project-path/" * 8,
    }
    data["card"]["call_to_action"] = {
        "zh-TW": "立即閱讀所有可驗證的專案內容" * 8,
        "en": "Read every verified repository detail " * 8,
    }
    config_path = tmp_path / "reponpc.yml"
    config_path.write_text(
        yaml.safe_dump(data, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    config = load_public_config(config_path)

    first = build_public_card_assets(config, config_directory=tmp_path)
    second = build_public_card_assets(config, config_directory=tmp_path)

    assert first == second
    for theme in ("light", "dark"):
        for locale in ("zh-TW", "en"):
            svg = first[f"public/card-{theme}-{locale}.svg"]
            root = ET.fromstring(svg)
            namespace = {"svg": "http://www.w3.org/2000/svg"}
            visible = root.findall("svg:text", namespace)
            assert root.attrib["viewBox"] == "0 0 600 180"
            assert len(visible) == 0 and root.findall("svg:path", namespace)
            assert root.find("svg:title", namespace).text == config.profile.display_name[:80]
            assert root.find("svg:desc", namespace).text == config.profile.headline[locale][:160]
            card = card_render._Card(
                card_render.CardPalette(**getattr(config.card.themes, theme).model_dump())
            )
            repos = f"{sum(repository.enabled for repository in config.repositories)} repos"
            label_max = 570 - card.measure(repos, "body", 110) - 20 - 242 - 24
            for value, role, width in (
                (config.profile.display_name[:80], "display", 350),
                (config.profile.headline[locale][:160], "body", 360),
                (config.card.call_to_action[locale][:80], "body", label_max),
                (repos, "body", 110),
            ):
                font = card.pick(value, role)
                fitted = card.fit(value, font, width)
                assert fitted and font.getlength(fitted) <= width
            for extension, expected_format in (("png", "PNG"), ("gif", "GIF")):
                payload = first[f"public/card-{theme}-{locale}.{extension}"]
                with Image.open(io.BytesIO(payload)) as image:
                    assert image.format == expected_format
                    assert image.size == (600, 180)
                    assert svg_to_image(svg).tobytes() == image.convert("RGB").tobytes()
