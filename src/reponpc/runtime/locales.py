"""Read the active site's language contract, including directory-only serving."""

from __future__ import annotations

import sqlite3
from contextlib import closing
from pathlib import Path

from reponpc.bundles.manager import BundleManager
from reponpc.config.models import LocalesConfig
from reponpc.i18n.plan import ANALYSIS_LOCALES
from reponpc.indexing.public_profile import parse_public_profile_bytes


def bundle_locales(
    manager: BundleManager | None, public_directory: Path | None = None
) -> LocalesConfig | None:
    if manager is not None:
        with manager.acquire() as index:
            return index.locales
    if public_directory is None:
        return None
    document = parse_public_profile_bytes((public_directory / "profile.json").read_bytes())
    if document.schema_version == 1:
        return LocalesConfig(default=ANALYSIS_LOCALES[0], supported=ANALYSIS_LOCALES)
    path = public_directory.parent / "index.sqlite"
    with closing(sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True)) as connection:
        row = connection.execute("SELECT value FROM bundle_meta WHERE key = 'locales'").fetchone()
    if row is None:
        raise ValueError("bundle languages are missing")
    return LocalesConfig.model_validate_json(row[0])
