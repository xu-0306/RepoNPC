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
from tests.security.test_admin_assets import ORIGIN, _login, local_admin_application


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
    app = local_admin_application(tmp_path)
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
            {"revision": 1, "action": "approve"},
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
        assert len(served.json()["entries"]) == 2
        assert set(served.json()["entries"][0]) == {
            "question",
            "variants",
            "answer_markdown",
            "citations",
        }
        for forbidden in ("CANARY", "review_state", "entry_id", "revision", "provider"):
            assert forbidden not in served.text


@pytest.mark.parametrize(
    "stored_bundle,requested_bundle,revision,code",
    [
        ("bundle-current", "bundle-old", 1, "FAQ_STALE"),
        ("bundle-old", "bundle-current", 1, "FAQ_STALE"),
        ("bundle-current", "bundle-current", 2, "FAQ_CONFLICT"),
    ],
)
def test_variant_update_preserves_rows_on_stale_bundle_or_revision(
    tmp_path, stored_bundle, requested_bundle, revision, code
):
    database = RuntimeDatabase(tmp_path)
    database.initialize()
    entry_id = _seed(database, 1, "approved", bundle=stored_bundle)
    faq = ReviewedFaq(database=database, bundles=SyntheticBundles(), chat_supplier=lambda: None)
    before = faq.view("en")
    with pytest.raises(FaqError) as error:
        faq.replace_variants(entry_id, revision, requested_bundle, ["Alternative question"])
    assert error.value.code == code
    assert faq.view("en") == before


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
                faq.review(entry_id, current["revision"], "approve")
            assert blocked.value.code == "FAQ_NOT_READY"
            with pytest.raises(FaqError) as duplicate:
                faq.regenerate(entry_id, 1)
            assert duplicate.value.code == "FAQ_CONFLICT"
            assert len(calls) == 1
        finally:
            release.set()
        completed = generated.result(timeout=5)
    assert completed["coverage_status"] == "no_relevant_content"
    faq.review(entry_id, completed["revision"], "approve")
    assert (
        faq.public_payload("en")["entries"][0]["answer_markdown"]
        == "No supported content was found."
    )


@pytest.mark.parametrize("operation", ["review", "variants", "regenerate"])
def test_unused_legacy_rewrite_values_are_ignored_and_cleared(tmp_path, operation):
    database = RuntimeDatabase(tmp_path)
    database.initialize()
    entry_id = _seed(database, 1, "approved", rewrite="invalid legacy JSON")

    class Chat:
        def answer_for_review(self, **kwargs):
            assert set(kwargs) == {"message", "locale"}
            return ChatDelivery(
                index_version="bundle-current",
                locale="en",
                evidence_count=0,
                answer_markdown="No supported content.",
                citations=(),
                finish_reason="stop",
                usage=None,
                insufficient_evidence=True,
            )

    faq = ReviewedFaq(database=database, bundles=SyntheticBundles(), chat_supplier=lambda: Chat())
    assert "rewrite" not in faq.view("en")["entries"][0]
    assert len(faq.public_payload("en")["entries"]) == 1
    if operation == "review":
        faq.review(entry_id, 1, "approve")
    elif operation == "variants":
        faq.replace_variants(entry_id, 1, "bundle-current", ["Alternative question"])
    else:
        faq.regenerate(entry_id, 1)
    with database.connection() as connection:
        assert connection.execute("SELECT rewrite_json FROM faq_entries").fetchone()[0] is None
