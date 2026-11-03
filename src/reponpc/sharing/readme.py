"""GitHub profile README from the same confirmed public snapshot as Pages."""

from __future__ import annotations

import html
import json
import re
from functools import lru_cache
from pathlib import Path
from typing import cast
from urllib.parse import quote

from reponpc.config.models import Locale
from reponpc.indexing.public_profile import LocalizedPublicProfile
from reponpc.sharing.manifest import SiteExportError

_MARKDOWN = re.compile(r"([\\`*_{}\[\]()#+\-.!|>])")
MAX_README_BYTES = 500 * 1024


@lru_cache
def _readme_copy() -> dict[str, dict[str, str]]:
    return cast(
        dict[str, dict[str, str]],
        json.loads(Path(__file__).with_name("readme_copy.json").read_text(encoding="utf-8")),
    )


def _text(value: str, *, single_line: bool = False) -> str:
    value = value.replace("\r\n", "\n").replace("\r", "\n")
    value = "".join(character for character in value if character in "\n\t" or ord(character) >= 32)
    if single_line:
        value = " ".join(value.split())
    return _MARKDOWN.sub(r"\\\1", html.escape(value, quote=False))


def _link(label: str, url: str) -> str:
    destination = quote(url, safe=":/?&=#%+@,;~-")
    return f"[{_text(label, single_line=True)}](<{destination}>)"


def render_profile_readme(
    document: LocalizedPublicProfile, *, pages_url: str, locale: Locale
) -> bytes:
    """Render escaped public text and application-owned links, never model output."""
    profile = document.profile
    copy = _readme_copy()[locale]
    chat_label = copy["chat"]
    card_url = f"{pages_url}card-light-{locale}.gif"
    paragraphs = [
        f"# {_text(profile.display_name, single_line=True)}",
        _text(profile.headline),
        _text(profile.bio),
    ]
    if profile.location:
        paragraphs.append(_text(profile.location))
    if profile.links:
        paragraphs.append(" · ".join(_link(link.label, link.url) for link in profile.links))
    if document.repositories:
        paragraphs.append("## " + copy["projects"])
    for repository in document.repositories:
        paragraphs.extend(
            [
                "### "
                + _link(repository.slug, f"https://github.com/{quote(repository.slug, safe='/')}"),
                _text(repository.summary),
                _text(repository.role),
            ]
        )
        if repository.tags:
            paragraphs.append(" · ".join(_text(tag) for tag in repository.tags))
        if repository.demo_url:
            paragraphs.append(_link(copy["demo"], repository.demo_url))
    paragraphs.extend(
        [
            "## " + copy["card"],
            f"[![{chat_label}](<{card_url}>)](<{pages_url}>)",
            _link(chat_label, pages_url),
            copy["explanation"],
        ]
    )
    content = ("\n\n".join(paragraphs) + "\n").encode("utf-8")
    if len(content) > MAX_README_BYTES:
        raise SiteExportError("SHARING_EXPORT_TOO_LARGE")
    return content
