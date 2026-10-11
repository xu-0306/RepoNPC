"""GitHub profile README from the same confirmed public snapshot as Pages."""

from __future__ import annotations

import html
import re
from urllib.parse import quote

from reponpc.config.models import Locale
from reponpc.indexing.public_profile import LocalizedPublicProfile
from reponpc.sharing.manifest import SiteExportError

_MARKDOWN = re.compile(r"([\\`*_{}\[\]()#+\-.!|>])")
MAX_README_BYTES = 500 * 1024


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
    zh = locale == "zh-TW"
    chat_label = "與我的 NPC 對話" if zh else "Chat with my NPC"
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
        paragraphs.append("## 作品" if zh else "## Projects")
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
            paragraphs.append(_link("展示" if zh else "Demo", repository.demo_url))
    paragraphs.extend(
        [
            "## NPC 名片" if zh else "## NPC card",
            f"[![{chat_label}](<{card_url}>)](<{pages_url}>)",
            _link(chat_label, pages_url),
            "點擊連結前往 RepoNPC 網站。GitHub README 顯示名片。對話會在網站進行。"
            if zh
            else (
                "Open the link to visit my RepoNPC site. GitHub README displays the card; "
                "conversations take place on the site."
            ),
        ]
    )
    content = ("\n\n".join(paragraphs) + "\n").encode("utf-8")
    if len(content) > MAX_README_BYTES:
        raise SiteExportError("SHARING_EXPORT_TOO_LARGE")
    return content
