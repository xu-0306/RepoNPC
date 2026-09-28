"""Independent boundary and in-flight approval regression checks for A4."""

from __future__ import annotations

import json
import threading
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from reponpc.admin.faq import FaqError, ReviewedFaq
from reponpc.chat.service import ChatDelivery
from reponpc.runtime.database import RuntimeDatabase
from tests.security.test_admin_writeback import ORIGIN, _application_without_github, _login


class SyntheticBundles:
    def status(self):
        return SimpleNamespace(active_bundle_id="bundle-current")

    @contextmanager
    def acquire_snapshot(self):
        yield None, "bundle-current", Path("unused-synthetic-public")


def _seed(
    database,
    ordinal,
    state="pending",
    *,
    bundle="bundle-current",
    locale="en",
    rewrite=None,
    error=None,
):
    entry_id = f"{ordinal:032x}"
    with database.connection() as connection:
        connection.execute(
            "INSERT INTO faq_entries (entry_id, question_key, bundle_id, locale, question, "
            "claim_kind, answer_markdown, diagnostics_json, coverage_status, review_state, "
            "rewrite_json, error_code) "
            "VALUES (?, ?, ?, ?, ?, 'context', ?, ?, 'answered', ?, ?, ?)",
            (
                entry_id,
                entry_id,
                bundle,
                locale,
                f"Question {ordinal}",
                "Safe validated reply",
                json.dumps([{"segment_index": 1, "reason_codes": ["OWNER_ONLY_CANARY"]}]),
                state,
                rewrite,
                error,
            ),
        )
    return entry_id


@pytest.mark.parametrize("locale", ["zh-TW", "en"])
def test_faq_routes_protect_mutations_and_share_only_approved_current_rows(tmp_path, locale):
    app = _application_without_github(tmp_path)
    database = app.state.admin_operations.database
    app.state.runtime_database = database
    app.state.bundle_manager = SyntheticBundles()
    approved = _seed(database, 1, "approved", locale=locale)
    _seed(database, 2, locale=locale)
    _seed(database, 3, "rejected", locale=locale)
    _seed(database, 4, "approved", bundle="bundle-old", locale=locale)
    _seed(database, 5, "approved", locale=locale, rewrite='{"private":"REWRITE_CANARY"}')
    _seed(database, 6, "approved", locale=locale, error="ERROR_CANARY")
    mutations = [
        ("/api/admin/portfolio/faq/check", {"locale": locale}),
        (f"/api/admin/portfolio/faq/{approved}/regenerate", {"revision": 1}),
        (
            f"/api/admin/portfolio/faq/{approved}/review",
            {"revision": 1, "bundle_id": "bundle-current", "action": "approve"},
        ),
        (
            f"/api/admin/portfolio/faq/{approved}/rewrite",
            {
                "revision": 1,
                "expected_draft_revision": "a" * 64,
                "repository": "owner/project",
                "kind": "context",
                "statement": {"zh-TW": "測試自述", "en": "Fixture statement"},
            },
        ),
    ]
    with TestClient(app, base_url=ORIGIN) as client:
        for path, body in mutations:
            assert client.post(path, headers={"Origin": ORIGIN}, json=body).status_code == 401
        assert client.get("/api/admin/portfolio/faq", headers={"Origin": ORIGIN}).status_code == 401
        assert (
            client.get("/api/admin/portfolio/faq/export", headers={"Origin": ORIGIN}).status_code
            == 401
        )
        csrf = _login(client)
        for path, body in mutations:
            assert client.post(path, headers={"Origin": ORIGIN}, json=body).status_code == 403
            assert (
                client.post(
                    path,
                    headers={"Origin": "https://evil.example", "X-CSRF-Token": csrf},
                    json=body,
                ).status_code
                == 403
            )
        headers = {"Origin": ORIGIN, "X-CSRF-Token": csrf}
        tampered = client.post(
            f"/api/admin/portfolio/faq/{approved}/review",
            headers=headers,
            json={
                "revision": 1,
                "bundle_id": "bundle-current",
                "action": "approve",
                "answer_markdown": "UNVALIDATED_ANSWER_CANARY",
            },
        )
        assert tampered.status_code == 400
        assert "UNVALIDATED_ANSWER_CANARY" not in tampered.text
        served = client.get(f"/api/public/faq?locale={locale}")
        exported = client.get(f"/api/admin/portfolio/faq/export?locale={locale}", headers=headers)
        assert served.status_code == exported.status_code == 200
        assert served.json() == exported.json()
        assert served.headers["cache-control"] == exported.headers["cache-control"] == "no-store"
        assert "attachment" in exported.headers["content-disposition"]
        assert set(served.json()) == {"bundle_id", "locale", "entries"}
        assert len(served.json()["entries"]) == 1
        assert set(served.json()["entries"][0]) == {"question", "answer_markdown", "citations"}
        for forbidden in ("CANARY", "review_state", "entry_id", "revision", "provider"):
            assert forbidden not in served.text


def test_regeneration_withholds_old_answer_until_new_validation_completes(tmp_path):
    database = RuntimeDatabase(tmp_path)
    database.initialize()
    entry_id = _seed(database, 1, "approved")
    entered, release = threading.Event(), threading.Event()
    calls = []

    class Chat:
        def answer_for_review(self, **kwargs):
            calls.append(kwargs["message"])
            entered.set()
            assert release.wait(5)
            return ChatDelivery(
                index_version="bundle-current",
                locale="en",
                evidence_count=0,
                answer_markdown="No supported content was found.",
                citations=(),
                finish_reason="stop",
                usage=None,
                insufficient_evidence=True,
            )

    faq = ReviewedFaq(database=database, bundles=SyntheticBundles(), chat_supplier=lambda: Chat())
    with ThreadPoolExecutor(max_workers=1) as executor:
        generated = executor.submit(faq.regenerate, entry_id, 1)
        try:
            assert entered.wait(5)
            current = faq.view("en")["entries"][0]
            assert faq.public_payload("en")["entries"] == []
            with pytest.raises(FaqError) as blocked:
                faq.review(entry_id, current["revision"], "bundle-current", "approve")
            assert blocked.value.code == "FAQ_NOT_READY"
            with pytest.raises(FaqError) as duplicate:
                faq.regenerate(entry_id, 1)
            assert duplicate.value.code == "FAQ_CONFLICT"
            assert len(calls) == 1
        finally:
            release.set()
        completed = generated.result(timeout=5)
    assert completed["coverage_status"] == "no_relevant_content"
    faq.review(entry_id, completed["revision"], "bundle-current", "approve")
    assert (
        faq.public_payload("en")["entries"][0]["answer_markdown"]
        == "No supported content was found."
    )
