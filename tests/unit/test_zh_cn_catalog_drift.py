"""The generated zh-CN visitor catalog follows its zh-TW source (ADR-079 decision 2)."""

from __future__ import annotations

from scripts.generate_zh_cn_catalog import MESSAGES, SNAPSHOT, generate


def test_committed_catalog_and_snapshot_match_a_fresh_conversion() -> None:
    source = MESSAGES.read_text(encoding="utf-8")
    output, snapshot = generate(source)
    assert output == source
    assert SNAPSHOT.read_text(encoding="utf-8") == snapshot


def test_generation_is_idempotent() -> None:
    output, _ = generate(MESSAGES.read_text(encoding="utf-8"))
    assert generate(output)[0] == output


def test_a_changed_source_is_converted_and_other_text_is_untouched() -> None:
    zh_tw = '  "zh-TW": {\n    note: "網路程式維護",\n  },\n'
    english = '  en: {\n    note: "Network",\n  },\n'
    output, snapshot = generate(zh_tw + english)
    assert output.startswith(zh_tw)
    assert output.endswith(english)
    assert '  "zh-CN": {\n    note: "网络程序维护",\n  },\n' in output
    assert "網路程式維護" in snapshot and "网络程序维护" in snapshot
