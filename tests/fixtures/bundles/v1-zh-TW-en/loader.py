"""Load the complete deterministic pre-ADR-079 bundle without rebuilding it."""

import json
from pathlib import Path

from reponpc.bundles.archive import verify_bundle_archive
from tests.integration.test_index_build import DeterministicEmbeddingProvider


def load_bundle(staging_directory: Path):
    root = Path(__file__).parent
    anchor = json.loads((root / "anchor.json").read_text(encoding="utf-8"))
    return verify_bundle_archive(
        archive_path=root / "bundle.tar.zst",
        staging_directory=staging_directory,
        expected_outer_sha256=anchor["sha256"],
        expected_embedding=DeterministicEmbeddingProvider().identity(),
        max_bundle_bytes=1024 * 1024,
    )
