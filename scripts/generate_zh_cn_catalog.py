"""Regenerate the shared Simplified Chinese chrome through the backend converter."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from reponpc.i18n.convert import convert
from reponpc.i18n.languages import get_language

ROOT = Path(__file__).resolve().parents[1]
MESSAGES = ROOT / "apps/web/src/i18n/messages.ts"
SNAPSHOT = ROOT / "apps/web/src/app/zhCnCatalog.snapshot.json"
START = "  // generated, do not edit (scripts/generate_zh_cn_catalog.py)\n"
END = "  // end generated catalog\n"


def generate(source: str) -> tuple[str, str]:
    """Return the updated module and the source/output drift snapshot."""
    target = get_language("zh-CN")
    assert target.derive is not None
    source_tag = target.derive.source
    match = re.search(
        rf"^  {re.escape(json.dumps(source_tag))}: {{\n.*?^  }},\n",
        source,
        re.MULTILINE | re.DOTALL,
    )
    if match is None:
        raise ValueError("source catalog not found")
    original = match[0]
    converted = convert(original, source_tag, target.tag).replace(
        json.dumps(source_tag), json.dumps(target.tag)
    )
    block = START + converted + END
    if START in source:
        start = source.index(START)
        end = source.index(END, start) + len(END)
        output = source[:start] + block + source[end:]
    else:
        output = source[: match.end()] + block + source[match.end() :]
    snapshot = (
        json.dumps({"source": original, "generated": converted}, ensure_ascii=False, indent=2)
        + "\n"
    )
    return output, snapshot


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    source = MESSAGES.read_text(encoding="utf-8")
    output, snapshot = generate(source)
    if args.check:
        if source != output or SNAPSHOT.read_text(encoding="utf-8") != snapshot:
            raise SystemExit("Generated catalog drift; run scripts/generate_zh_cn_catalog.py")
        print("zh-CN catalog and drift snapshot: 2 passed")
    else:
        MESSAGES.write_text(output, encoding="utf-8", newline="\n")
        SNAPSHOT.write_text(snapshot, encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
