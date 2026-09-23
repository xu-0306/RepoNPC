from __future__ import annotations

import base64
import hashlib
import io
import json
from pathlib import Path

import pytest
import yaml
from PIL import Image

import reponpc.admin.local_portfolio as local_portfolio
from reponpc.admin.local_portfolio import (
    LocalPortfolioDraft,
    LocalPortfolioError,
    LocalPortfolioStore,
    apply_character,
)
from reponpc.cards.assets import HARD_MAX_BYTES, validate_sprite
from reponpc.config.models import MAX_CONFIG_BYTES

FIXTURE = Path(__file__).parents[1] / "fixtures" / "phase2" / "reponpc.yml"


def _builtin_content() -> str:
    return FIXTURE.read_text(encoding="utf-8")


def _custom_content() -> str:
    values = yaml.safe_load(_builtin_content())
    values["character"]["mode"] = "custom"
    values["character"].pop("builtin")
    values["character"]["custom"] = {"sprite_path": "assets/character/fixture.png"}
    values["character"]["revision"] = 2
    return yaml.safe_dump(values, allow_unicode=True, sort_keys=False)


def _sprite_base64() -> str:
    image = Image.new("RGBA", (256, 448), (0, 0, 0, 0))
    pixels = image.load()
    for row in range(7):
        for column in range(4):
            pixels[column * 64, row * 64] = (255, 0, 0, 255)
    output = io.BytesIO()
    image.save(output, format="PNG")
    return base64.b64encode(output.getvalue()).decode("ascii")


def _store_path(root: Path) -> Path:
    return root / "local-portfolio" / "draft.json"


def test_builtin_save_read_and_exact_shape(tmp_path: Path) -> None:
    store = LocalPortfolioStore(tmp_path)

    draft = store.save(
        content=_builtin_content(),
        sprite_base64=None,
        expected_revision=None,
    )

    assert isinstance(draft, LocalPortfolioDraft)
    assert draft.sprite_base64 is None
    assert set(draft.as_dict()) == {"content", "sprite_base64", "revision"}
    assert store.read() == draft
    assert LocalPortfolioStore(tmp_path).read() == draft


def test_custom_save_canonicalises_sprite_and_round_trips(tmp_path: Path) -> None:
    store = LocalPortfolioStore(tmp_path)
    content = _custom_content()
    sprite = _sprite_base64()

    draft = store.save(
        content=content,
        sprite_base64=sprite,
        expected_revision=None,
    )

    canonical = validate_sprite(base64.b64decode(sprite), max_bytes=HARD_MAX_BYTES).content
    assert draft.sprite_base64 == base64.b64encode(canonical).decode("ascii")
    assert draft.sprite_base64 != sprite
    assert store.read() == draft
    assert _store_path(tmp_path).exists()
    assert sorted(path.name for path in _store_path(tmp_path).parent.iterdir()) == ["draft.json"]


def test_builtin_and_custom_sprite_requirements_are_enforced(tmp_path: Path) -> None:
    store = LocalPortfolioStore(tmp_path)

    with pytest.raises(LocalPortfolioError) as forbidden:
        store.save(
            content=_builtin_content(),
            sprite_base64=_sprite_base64(),
            expected_revision=None,
        )
    assert forbidden.value.code == "PORTFOLIO_INVALID"

    with pytest.raises(LocalPortfolioError) as required:
        store.save(
            content=_custom_content(),
            sprite_base64=None,
            expected_revision=None,
        )
    assert required.value.code == "PORTFOLIO_ASSET_REQUIRED"


def test_compare_and_swap_rejects_stale_revision(tmp_path: Path) -> None:
    store = LocalPortfolioStore(tmp_path)
    first = store.save(
        content=_builtin_content(),
        sprite_base64=None,
        expected_revision=None,
    )

    changed = _builtin_content().replace("Fixture Developer", "Changed Developer")
    with pytest.raises(LocalPortfolioError) as conflict:
        store.save(
            content=changed,
            sprite_base64=None,
            expected_revision="0" * 64,
        )
    assert conflict.value.code == "PORTFOLIO_CONFLICT"
    assert store.read() == first


def test_corrupt_json_and_revision_are_rejected_without_content_in_error(
    tmp_path: Path,
) -> None:
    path = _store_path(tmp_path)
    path.parent.mkdir(parents=True)
    path.write_text("{not-json", encoding="utf-8")

    with pytest.raises(LocalPortfolioError) as malformed:
        LocalPortfolioStore(tmp_path).read()
    assert malformed.value.code == "PORTFOLIO_CORRUPT"
    assert "not-json" not in str(malformed.value)
    assert str(tmp_path) not in str(malformed.value)

    path.unlink()
    store = LocalPortfolioStore(tmp_path)
    draft = store.save(
        content=_builtin_content(),
        sprite_base64=None,
        expected_revision=None,
    )
    payload = draft.as_dict()
    payload["revision"] = "0" * 64
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(LocalPortfolioError) as wrong_revision:
        store.read()
    assert wrong_revision.value.code == "PORTFOLIO_CORRUPT"


def test_oversized_persisted_file_is_rejected_before_reading_bytes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = _store_path(tmp_path)
    path.parent.mkdir(parents=True)
    with path.open("wb") as stream:
        stream.seek(local_portfolio._JSON_MAX_BYTES)
        stream.write(b"x")

    def fail_read_bytes(_path: Path) -> bytes:
        raise AssertionError("oversized persisted file must be rejected before read")

    monkeypatch.setattr(Path, "read_bytes", fail_read_bytes)
    with pytest.raises(LocalPortfolioError) as error:
        LocalPortfolioStore(tmp_path).read()
    assert error.value.code == "PORTFOLIO_CORRUPT"


def test_content_and_sprite_size_bounds_are_enforced(tmp_path: Path) -> None:
    store = LocalPortfolioStore(tmp_path)
    oversized_content = _builtin_content() + "\n#" + "x" * MAX_CONFIG_BYTES
    with pytest.raises(LocalPortfolioError) as content_error:
        store.save(
            content=oversized_content,
            sprite_base64=None,
            expected_revision=None,
        )
    assert content_error.value.code == "PAYLOAD_TOO_LARGE"

    oversized_sprite = base64.b64encode(b"x" * (HARD_MAX_BYTES + 1)).decode("ascii")
    with pytest.raises(LocalPortfolioError) as sprite_error:
        store.save(
            content=_custom_content(),
            sprite_base64=oversized_sprite,
            expected_revision=None,
        )
    assert sprite_error.value.code == "PAYLOAD_TOO_LARGE"


def test_invalid_custom_sprite_path_is_rejected(tmp_path: Path) -> None:
    values = yaml.safe_load(_builtin_content())
    values["character"]["mode"] = "custom"
    values["character"].pop("builtin")
    values["character"]["custom"] = {"sprite_path": "outside/character.png"}
    invalid_content = yaml.safe_dump(values, allow_unicode=True, sort_keys=False)

    with pytest.raises(LocalPortfolioError) as error:
        LocalPortfolioStore(tmp_path).save(
            content=invalid_content,
            sprite_base64=_sprite_base64(),
            expected_revision=None,
        )
    assert error.value.code == "CONFIG_INVALID"


def test_apply_character_rewrites_config_without_writing_files(tmp_path: Path) -> None:
    original = yaml.safe_load(_builtin_content())
    draft = apply_character(_builtin_content(), _sprite_base64())
    rewritten = yaml.safe_load(draft.content)

    assert rewritten["character"]["mode"] == "custom"
    assert "builtin" not in rewritten["character"]
    assert rewritten["character"]["custom"] == {"sprite_path": "assets/character/portfolio.png"}
    assert rewritten["character"]["revision"] == original["character"]["revision"] + 1
    rewritten_without_character = dict(rewritten)
    original_without_character = dict(original)
    rewritten_without_character.pop("character")
    original_without_character.pop("character")
    assert rewritten_without_character == original_without_character
    assert not (tmp_path / "assets").exists()

    persisted = LocalPortfolioStore(tmp_path).save(
        content=draft.content,
        sprite_base64=draft.sprite_base64,
        expected_revision=None,
    )
    assert persisted.revision == draft.revision
    assert (
        persisted.revision
        == hashlib.sha256(
            draft.content.encode("utf-8") + base64.b64decode(draft.sprite_base64 or "")
        ).hexdigest()
    )


def test_apply_character_preserves_existing_custom_config_and_increments_revision() -> None:
    content = _custom_content()
    draft = apply_character(content, _sprite_base64())
    rewritten = yaml.safe_load(draft.content)
    assert rewritten["character"]["revision"] == 3
    assert rewritten["character"]["custom"]["sprite_path"] == ("assets/character/portfolio.png")
