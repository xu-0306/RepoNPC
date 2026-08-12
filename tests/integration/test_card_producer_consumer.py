from __future__ import annotations

import io
import xml.etree.ElementTree as ET
from pathlib import Path

from PIL import Image

from reponpc.cards.production import build_public_card_assets
from reponpc.config.models import load_public_config
from reponpc.indexing.pipeline import build_index_bundle
from reponpc.indexing.sources import ResolvedConfiguration
from tests.integration.test_index_build import (
    DeterministicEmbeddingProvider,
    _fixture_snapshot,
)


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
        assert character.size == (128, 224)
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
