"""P2-07 repeatability gate over independently staged real bundle builds."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from tests.integration.test_bundle_producer_consumer import _bundle


def test_identical_fixture_inputs_produce_equivalent_immutable_bundle_bytes(tmp_path: Path) -> None:
    first, _ = _bundle(tmp_path / "first")
    second, _ = _bundle(tmp_path / "second")

    assert first.manifest.bundle_id == second.manifest.bundle_id
    assert first.manifest.canonical_bytes() == second.manifest.canonical_bytes()
    assert first.archive_sha256 == second.archive_sha256
    assert first.archive_size == second.archive_size
    assert first.archive_path.read_bytes() == second.archive_path.read_bytes()

    with (
        sqlite3.connect(tmp_path / "first" / "index" / "index.sqlite") as first_index,
        sqlite3.connect(tmp_path / "second" / "index" / "index.sqlite") as second_index,
    ):
        first_rows = first_index.execute(
            "SELECT evidence_id, content, start_line, end_line FROM evidence ORDER BY evidence_id"
        ).fetchall()
        second_rows = second_index.execute(
            "SELECT evidence_id, content, start_line, end_line FROM evidence ORDER BY evidence_id"
        ).fetchall()
    assert first_rows == second_rows
