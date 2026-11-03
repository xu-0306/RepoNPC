"""Regenerate zh-CN chat policy through the registry converter (ADR-079).

Generated: person_reference.zh-CN.yml and the zh-CN entries in inflation_terms.yml
and visitor_messages.yml. Other languages, comments and formatting stay unchanged.
Run with this worktree's src on PYTHONPATH; no provider or network is used.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import yaml

from reponpc.chat.policy_data import POLICY_DIR
from reponpc.i18n.convert import convert

_GENERATED = "# zh-CN generated from zh-TW by scripts/generate_zh_cn_policy.py; do not edit.\n"
_GROUP_KEY = re.compile(r"^  [^\s#-][^:]*:")
_LOCALE_KEY = re.compile(r"^    [^\s#-][^:]*:")


def _scalar(text: str) -> str:
    return json.dumps(text, ensure_ascii=False)


def _update_entries(path: Path, entries: dict[str, str | list[str]]) -> None:
    text = path.read_bytes().decode("utf-8")
    if _GENERATED not in text:
        text = _GENERATED + text
    lines = text.splitlines(keepends=True)
    for key, value in entries.items():
        start = lines.index(f"  {key}:\n") + 1
        end = next(
            (i for i in range(start, len(lines)) if _GROUP_KEY.match(lines[i])),
            len(lines),
        )
        target = next((i for i in range(start, end) if lines[i].startswith("    zh-CN:")), None)
        if target is None:
            source = next(i for i in range(start, end) if lines[i].startswith("    zh-TW:"))
            target = next(
                (i for i in range(source + 1, end) if _LOCALE_KEY.match(lines[i])),
                end,
            )
            stop = target
        else:
            stop = next(
                (i for i in range(target + 1, end) if _LOCALE_KEY.match(lines[i])),
                end,
            )
            while stop > target + 1 and (
                not lines[stop - 1].strip() or lines[stop - 1].lstrip().startswith("#")
            ):
                stop -= 1
        rendered = (
            [f"    zh-CN: {_scalar(value)}\n"]
            if isinstance(value, str)
            else ["    zh-CN:\n", *(f"      - {_scalar(term)}\n" for term in value)]
        )
        lines[target:stop] = rendered
    path.write_bytes("".join(lines).encode("utf-8"))


def generate(policy_dir: Path = POLICY_DIR) -> None:
    person = yaml.safe_load((policy_dir / "person_reference.zh-TW.yml").read_text(encoding="utf-8"))
    lines = [_GENERATED]
    for key in ("references", "exclusions"):
        values = [convert(term, "zh-TW", "zh-CN") for term in person[key]]
        lines.extend(
            [f"{key}:\n", *(f"  - {_scalar(term)}\n" for term in values)]
            if values
            else [f"{key}: []\n"]
        )
    (policy_dir / "person_reference.zh-CN.yml").write_bytes("".join(lines).encode("utf-8"))

    inflation = policy_dir / "inflation_terms.yml"
    groups = yaml.safe_load(inflation.read_text(encoding="utf-8"))["groups"]
    _update_entries(
        inflation,
        {
            group: [convert(term, "zh-TW", "zh-CN") for term in locales["zh-TW"]]
            for group, locales in groups.items()
        },
    )

    visitor = policy_dir / "visitor_messages.yml"
    messages = yaml.safe_load(visitor.read_text(encoding="utf-8"))["messages"]
    _update_entries(
        visitor,
        {key: convert(locales["zh-TW"], "zh-TW", "zh-CN") for key, locales in messages.items()},
    )


if __name__ == "__main__":
    generate()
