"""Regression checks for the reduced Pages sharing state."""

from __future__ import annotations

import sqlite3

import pytest

from tests.security import test_pages_verification

configured_service = test_pages_verification.configured_service


def test_pages_state_has_no_export_receipt_or_cas_fields(configured_service) -> None:
    service, database, _entrance, _manifest, _expected, _web_dist = configured_service
    assert set(service.state()) == {
        "pages_url",
        "configured",
        "verified",
        "verified_at",
        "verified_content_sha256",
    }
    with database.connection() as connection:
        columns = {row[1] for row in connection.execute("PRAGMA table_info(pages_sharing_state)")}
    assert columns == {
        "singleton_id",
        "pages_url",
        "verified_pages_url",
        "verified_content_sha256",
        "verified_at",
    }


def test_partial_verification_cannot_be_persisted(configured_service) -> None:
    _service, database, _entrance, _manifest, _expected, _web_dist = configured_service
    with database.connection() as connection, pytest.raises(sqlite3.IntegrityError):
        connection.execute(
            "UPDATE pages_sharing_state SET verified_content_sha256=?",
            ("a" * 64,),
        )
