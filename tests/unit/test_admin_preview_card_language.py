"""The admin card preview renders each site language with that language's card copy (ADR-079)."""

from __future__ import annotations

from collections import Counter

import pytest
import yaml

from reponpc.admin import operations
from reponpc.admin.operations import AdminOperations
from reponpc.cards.render import repository_count_text
from tests.fixtures.bundles.site_languages import site_data

SITES = [("zh-TW", "en"), ("en",), ("es",), ("zh-CN", "en"), ("zh-TW", "zh-CN", "en", "es")]


@pytest.mark.parametrize("tags", SITES, ids="-".join)
def test_preview_cards_use_the_copy_of_their_own_language(
    tags: tuple[str, ...], monkeypatch: pytest.MonkeyPatch
) -> None:
    data = site_data(tags)
    content = yaml.safe_dump(data, allow_unicode=True).encode("utf-8")
    rendered = []
    real = operations.render_card_assets

    def spy(*, copy, **kwargs):  # type: ignore[no-untyped-def]
        rendered.append(copy)
        return real(copy=copy, **kwargs)

    monkeypatch.setattr(operations, "render_card_assets", spy)
    preview = AdminOperations(
        database=None,  # type: ignore[arg-type]
        public_base_url="https://example.test",
    ).preview_config(content)

    assert Counter(copy.locale for copy in rendered) == {tag: 2 for tag in tags}
    assert set(preview["cards"]) == {
        f"{theme}-{tag}" for theme in ("light", "dark") for tag in tags
    }
    for copy in rendered:
        assert copy.headline == data["profile"]["headline"][copy.locale]
        assert copy.repository_count is not None
        text = repository_count_text(copy.repository_count, copy.locale)
        assert text is not None and str(copy.repository_count) in text
