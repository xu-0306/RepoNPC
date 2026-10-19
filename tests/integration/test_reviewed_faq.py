"""A4 coverage and rewrite exercise actual immutable local builds and validation."""

from __future__ import annotations

import hashlib
import json
from dataclasses import replace

import pytest
import yaml
from fastapi.testclient import TestClient

from reponpc.admin.embedding_reindex import EmbeddingReindexCoordinator
from reponpc.admin.faq import (
    FaqError,
    ReviewedFaq,
    normalize_question,
    validate_question_variants,
)
from reponpc.admin.faq_registry import STANDARD_QUESTIONS
from reponpc.admin.local_portfolio import LocalPortfolioStore
from reponpc.admin.local_publication import LocalPortfolioBuilder
from reponpc.chat.limits import ProviderLane
from reponpc.chat.service import GroundedChatService, delivery_events
from reponpc.providers import ProviderCapabilities, ProviderHealth, ProviderResult
from reponpc.providers.runtime import ProviderRuntime
from reponpc.runtime.database import MIGRATIONS, Migration, RuntimeDatabase, RuntimeDatabaseError
from tests.integration.test_embedding_reindex import _profile, _system
from tests.integration.test_index_build import FIXTURE_CONFIG, _fixture_snapshot
from tests.integration.test_local_publication import FixtureResolver
from tests.security.test_admin_writeback import ORIGIN, _application_without_github, _login


class SyntheticChat:
    partial = False
    no_match = False
    failure = False
    hook = None
    calls = 0

    def capabilities(self):
        return ProviderCapabilities(True, True, True, True, True, 16000, 1000)

    def health(self):
        return ProviderHealth(True, "2026-09-28T00:00:00Z")

    def generate(self, messages, response_schema, max_output_tokens, timeout):
        assert response_schema["required"] == ["segments", "insufficient_evidence"]
        self.calls += 1
        if self.hook:
            self.hook()
        if self.failure:
            raise ValueError("PRIVATE_PROVIDER_CANARY")
        segments = (
            []
            if self.no_match
            else [
                {
                    "kind": "inference",
                    "text": "A documented project capability.",
                    "source_ids": ["S1"],
                }
            ]
        )
        if self.partial:
            segments.append(
                {
                    "kind": "person",
                    "text": "{{owner}} performed 999999 deployments.",
                    "source_ids": ["S1"],
                }
            )
        return ProviderResult(
            {"segments": segments, "insufficient_evidence": self.no_match}, "stop", None, None, 1.0
        )


class OwnerLimits:
    def __init__(self):
        self.lanes = []
        self.public_admissions = 0

    def acquire_generation(self, lane):
        from contextlib import nullcontext

        self.lanes.append(lane)
        return nullcontext()

    def admit_public_chat(self, client_ip):
        self.public_admissions += 1


def faq_system(tmp_path):
    database, providers, manager, registry, _, transition = _system(tmp_path)
    provider = providers["a"]
    profile = registry.probe(registry.create(_profile(provider)).profile_id)
    store = LocalPortfolioStore(tmp_path / "data")
    store.save(
        content=FIXTURE_CONFIG.read_text(encoding="utf-8"),
        sprite_base64=None,
        expected_revision=None,
    )
    ordinal = 0

    def build():
        nonlocal ordinal
        ordinal += 1
        builder = LocalPortfolioBuilder(
            store.read(),
            data_directory=tmp_path / "data",
            resolver=FixtureResolver(),
            max_bundle_bytes=10 * 1024 * 1024,
        )
        coordinator = EmbeddingReindexCoordinator(
            registry=registry, manager=manager, builder=builder, provider_transition=transition
        )
        coordinator.queue(profile.profile_id, force=True)
        result = coordinator.wait(profile.profile_id, timeout=30)
        assert result.active
        return manager.status().active_bundle_id

    build()
    chat = SyntheticChat()
    limits = OwnerLimits()
    service = GroundedChatService(
        bundles=manager,
        providers=ProviderRuntime(chat=chat, embedding=provider, max_attempts=1),
        limits=limits,
        max_output_tokens=1000,
        timeout_seconds=5,
    )
    faq = ReviewedFaq(database=database, bundles=manager, chat_supplier=lambda: service)
    return database, manager, store, chat, service, limits, faq, build


def save_owner_statement(store):
    """Use the ordinary draft store; there is no FAQ-specific association."""
    draft = store.read()
    values = yaml.safe_load(draft.content)
    target = next(
        item for item in values["repositories"] if item["slug"] == _fixture_snapshot().slug
    )
    target.setdefault("claims", []).append(
        {
            "id": "manual_faq_statement",
            "kind": "responsibility",
            "statement": {
                "zh-TW": "我實作資料驗證與例外處理。",
                "en": "I implemented café input validation\r\nand exception handling.",
            },
        }
    )
    return store.save(
        content=yaml.safe_dump(values, allow_unicode=True, sort_keys=False),
        sprite_base64=draft.sprite_base64,
        expected_revision=draft.revision,
    )


@pytest.mark.parametrize("locale", ["zh-TW", "en"])
def test_manual_claim_save_then_normal_regeneration_requires_new_review(tmp_path, locale):
    _database, _manager, store, _chat, _service, limits, faq, build = faq_system(tmp_path)
    initial = faq.initialize_queue(locale)
    assert len([entry for entry in initial["entries"] if entry["topic"]]) == 6
    assert all(entry["coverage_status"] == "unchecked" for entry in initial["entries"])
    entry = faq.regenerate(initial["entries"][0]["entry_id"], 1)
    assert entry["coverage_status"] == "answered"
    faq.review(entry["entry_id"], entry["revision"], "approve")
    assert len(faq.public_payload(locale)["entries"]) == 1
    before = {
        path: hashlib.sha256(path.read_bytes()).hexdigest()
        for path in (tmp_path / "data" / "bundles" / "validated").rglob("*")
        if path.is_file()
    }
    entry = faq.view(locale)["entries"][0]
    save_owner_statement(store)
    # Saving a draft does not change the active bundle or its reviewed FAQ.
    assert len(faq.public_payload(locale)["entries"]) == 1
    assert all(
        hashlib.sha256(path.read_bytes()).hexdigest() == digest for path, digest in before.items()
    )
    new_bundle = build()
    assert new_bundle != entry["bundle_id"]
    stale = faq.view(locale)["entries"][0]
    assert stale["needs_reconfirmation"]
    assert faq.public_payload(locale)["entries"] == []
    with pytest.raises(FaqError) as rejected:
        faq.review(stale["entry_id"], stale["revision"], "approve")
    assert rejected.value.code == "FAQ_STALE"
    regenerated = faq.regenerate(stale["entry_id"], stale["revision"])
    assert regenerated["bundle_id"] == new_bundle
    assert "rewrite" not in regenerated and regenerated["review_state"] == "pending"
    assert faq.public_payload(locale)["entries"] == []
    approved = faq.review(regenerated["entry_id"], regenerated["revision"], "approve")
    assert approved["review_state"] == "approved"
    assert faq.public_payload(locale)["entries"][0]["citations"]
    assert limits.public_admissions == 0 and set(limits.lanes) == {ProviderLane.ADMIN_SINGLE}


def test_validated_partial_reasons_and_failed_generation_never_become_gaps(tmp_path):
    _, _manager, _, chat, _, _, faq, _ = faq_system(tmp_path)
    entry = faq.initialize_queue("en")["entries"][0]
    chat.partial = True
    entry = faq.regenerate(entry["entry_id"], entry["revision"])
    assert entry["coverage_status"] == "partially_answered"
    assert entry["dropped_segments"][0]["segment_index"] == 1
    assert entry["dropped_segments"][0]["reason_codes"]
    chat.failure = True
    with pytest.raises(FaqError):
        faq.regenerate(entry["entry_id"], entry["revision"])
    failed = faq.view("en")["entries"][0]
    assert failed["coverage_status"] == "unchecked" and failed["answer_markdown"] is None
    assert failed["error_code"] == "FAQ_GENERATION_FAILED"
    assert "PRIVATE_PROVIDER_CANARY" not in json.dumps(failed)


def test_leased_answer_keeps_original_bundle_during_real_activation(tmp_path):
    _, manager, store, chat, service, _, _faq, build = faq_system(tmp_path)
    old_bundle = manager.status().active_bundle_id
    current = store.read()
    store.save(
        content=current.content.replace("revision: 0", "revision: 1"),
        sprite_base64=None,
        expected_revision=current.revision,
    )
    chat.hook = build
    delivery = service.answer(
        message="How is this project built?", locale="en", history=(), client_ip="127.0.0.1"
    )
    assert delivery.index_version == old_bundle != manager.status().active_bundle_id
    assert not any(
        "discarded_segments" in payload for _, payload in delivery_events(delivery, "fixture")
    )


def test_registry_has_unique_bounded_equivalent_locale_topics():
    assert len(STANDARD_QUESTIONS) == 6
    assert len({key for key, _, _ in STANDARD_QUESTIONS}) == 6
    for _, kind, texts in STANDARD_QUESTIONS:
        assert kind in {"role", "responsibility", "achievement", "context"}
        assert set(texts) == {"zh-TW", "en"}
        assert all(1 <= len(question) <= 2000 for question in texts.values())
    assert all(
        len({texts[locale] for _, _, texts in STANDARD_QUESTIONS}) == 6
        for locale in ("zh-TW", "en")
    )


def test_faq_api_all_owner_actions_and_safe_failure(tmp_path):
    database, manager, store, chat, service, _, _, build = faq_system(tmp_path / "build")
    application = _application_without_github(tmp_path / "admin")
    application.state.admin_operations = replace(
        application.state.admin_operations, database=database, local_portfolio=store
    )
    application.state.runtime_database = database
    application.state.bundle_manager = manager
    application.state.chat_service = service
    with TestClient(application, base_url=ORIGIN) as client:
        csrf = _login(client)
        headers = {"Origin": ORIGIN, "X-CSRF-Token": csrf}
        queue = client.post(
            "/api/admin/portfolio/faq/check", headers=headers, json={"locale": "en"}
        ).json()
        entry = queue["entries"][0]
        root = f"/api/admin/portfolio/faq/{entry['entry_id']}"
        generated = client.post(
            root + "/regenerate", headers=headers, json={"revision": entry["revision"]}
        )
        assert generated.status_code == 200
        entry = generated.json()
        for action in ("approve", "reject"):
            response = client.post(
                root + "/review",
                headers=headers,
                json={
                    "revision": entry["revision"],
                    "action": action,
                },
            )
            assert response.status_code == 200
            entry = response.json()
            public = client.get("/api/public/faq?locale=en").json()
            assert len(public["entries"]) == int(action == "approve")
            exported = client.get("/api/admin/portfolio/faq/export?locale=en", headers=headers)
            assert exported.json() == public
            assert "attachment" in exported.headers["content-disposition"]
        assert client.post(root + "/rewrite", headers=headers, json={}).status_code == 405
        assert (
            client.post(
                root + "/review",
                headers=headers,
                json={
                    "revision": entry["revision"],
                    "bundle_id": entry["bundle_id"],
                    "action": "approve",
                },
            ).status_code
            == 400
        )
        save_owner_statement(store)
        build()
        response = client.post(
            root + "/regenerate", headers=headers, json={"revision": entry["revision"]}
        )
        assert response.status_code == 200 and response.json()["review_state"] == "pending"
        chat.failure = True
        response = client.post(
            root + "/regenerate", headers=headers, json={"revision": response.json()["revision"]}
        )
        assert response.status_code == 503
        assert "PRIVATE_PROVIDER_CANARY" not in response.text
        assert (
            client.post(
                "/api/admin/portfolio/faq/not-a-uuid/regenerate",
                headers=headers,
                json={"revision": 1},
            ).status_code
            == 400
        )


def test_question_variants_withdraw_approval_and_use_existing_revision(tmp_path):
    database, manager, store, _chat, service, _, _faq, _build = faq_system(tmp_path / "build")
    application = _application_without_github(tmp_path / "admin")
    application.state.admin_operations = replace(
        application.state.admin_operations, database=database, local_portfolio=store
    )
    application.state.runtime_database = database
    application.state.bundle_manager = manager
    application.state.chat_service = service
    with TestClient(application, base_url=ORIGIN) as client:
        csrf = _login(client)
        headers = {"Origin": ORIGIN, "X-CSRF-Token": csrf}
        queue = client.post(
            "/api/admin/portfolio/faq/check", headers=headers, json={"locale": "en"}
        ).json()
        entry = client.post(
            f"/api/admin/portfolio/faq/{queue['entries'][0]['entry_id']}/regenerate",
            headers=headers,
            json={"revision": 1},
        ).json()
        approved = client.post(
            f"/api/admin/portfolio/faq/{entry['entry_id']}/review",
            headers=headers,
            json={
                "revision": entry["revision"],
                "action": "approve",
            },
        ).json()
        public_before = client.get("/api/public/faq?locale=en").json()
        assert public_before["entries"][0]["variants"] == []
        assert set(public_before) == {"bundle_id", "locale", "entries"}

        path = f"/api/admin/portfolio/faq/{approved['entry_id']}/variants"
        body = {
            "bundle_id": approved["bundle_id"],
            "revision": approved["revision"],
            "variants": ["Which portfolio projects stand out?", "What are the top projects?"],
        }
        assert client.put(path, headers={"Origin": ORIGIN}, json=body).status_code == 403
        updated_response = client.put(path, headers=headers, json=body)
        assert updated_response.status_code == 200
        updated = updated_response.json()
        assert updated["revision"] == approved["revision"] + 1
        assert updated["review_state"] == "pending"
        assert updated["answer_markdown"] == approved["answer_markdown"]
        assert updated["citations"] == approved["citations"]
        assert client.get("/api/public/faq?locale=en").json()["entries"] == []

        invalid = client.put(
            path,
            headers=headers,
            json={
                "bundle_id": updated["bundle_id"],
                "revision": updated["revision"],
                "variants": [updated["question"].upper()],
            },
        )
        assert invalid.status_code == 422
        assert invalid.json()["error"]["code"] == "FAQ_VARIANTS_INVALID"
        assert "PRIVATE" not in invalid.text

        rereviewed = client.post(
            f"/api/admin/portfolio/faq/{updated['entry_id']}/review",
            headers=headers,
            json={
                "revision": updated["revision"],
                "action": "approve",
            },
        )
        assert rereviewed.status_code == 200
        public_after = client.get("/api/public/faq?locale=en").json()
        assert public_after["entries"][0]["variants"] == body["variants"]


def test_question_variant_validation_is_bounded_and_unicode_normalized(tmp_path):
    _database, _manager, _store, _chat, _service, _limits, faq, _build = faq_system(tmp_path)
    queue = faq.initialize_queue("en")
    entry = queue["entries"][0]
    generated = faq.regenerate(entry["entry_id"], entry["revision"])
    assert faq.replace_variants(
        entry["entry_id"],
        generated["revision"],
        generated["bundle_id"],
        ["What is this project's overview?"],
    )["variants"] == ["What is this project's overview?"]
    invalid_sets = [
        [" "],
        ["a" * 201],
        ["\uff33\uff41\uff4d\uff45\u3000question\uff1f", "same  question!"],
        [entry["question"].upper()],
        [str(index) for index in range(9)],
    ]
    for variants in invalid_sets:
        with pytest.raises(FaqError) as rejected:
            faq.replace_variants(
                entry["entry_id"],
                faq.view("en")["entries"][0]["revision"],
                entry["bundle_id"],
                variants,
            )
        assert rejected.value.code == "FAQ_VARIANTS_INVALID"


def test_migration_29_backup_reopen_and_failed_upgrade_preserve_prior_state(tmp_path):
    database = RuntimeDatabase(tmp_path / "runtime")
    prior = tuple(migration for migration in MIGRATIONS if migration.version < 29)
    faq_migration = next(migration for migration in MIGRATIONS if migration.version == 29)
    broken = Migration(29, "bad-faq", (faq_migration.statements[0], "INVALID SQL"))
    database.initialize(migrations=prior)
    with pytest.raises(RuntimeDatabaseError):
        database.initialize(migrations=(*prior, broken))
    assert database.schema_version() == 28
    database.initialize()
    database.initialize()
    with database.connection() as connection:
        connection.execute(
            "INSERT INTO faq_entries "
            "(entry_id,question_key,bundle_id,locale,question,claim_kind,"
            "review_state,rewrite_json) "
            "VALUES ('fixture','fixture','bundle','en','Question','context','pending',?)",
            (json.dumps({"claim_id": "faq_fixture", "draft_revision": "a" * 64}),),
        )
        connection.execute(
            "INSERT INTO faq_entries (entry_id,question_key,bundle_id,locale,question,"
            "claim_kind,review_state,answer_markdown,coverage_status) VALUES "
            "('approved','approved','bundle','en','Approved question','context',"
            "'approved','Validated no-match reply','no_relevant_content')"
        )
    backup = tmp_path / "backup.sqlite"
    database.backup_to(backup)
    import sqlite3

    with sqlite3.connect(backup) as connection:
        assert (
            json.loads(connection.execute("SELECT rewrite_json FROM faq_entries").fetchone()[0])[
                "claim_id"
            ]
            == "faq_fixture"
        )
        assert (
            connection.execute(
                "SELECT review_state FROM faq_entries WHERE entry_id = 'approved'"
            ).fetchone()[0]
            == "approved"
        )
    RuntimeDatabase(tmp_path / "runtime").initialize()
    assert database.schema_version() == MIGRATIONS[-1].version
    with database.connection() as connection:
        assert (
            connection.execute(
                "SELECT review_state FROM faq_entries WHERE entry_id = 'approved'"
            ).fetchone()[0]
            == "approved"
        )


FAQ_NORMALIZATION_CASES = [
    ("  \uff33\uff45\uff54\u3000 UP?!  ", "set up"),
    ("setup", "setup"),
    ("使用 C 嗎\uff1f", "使用 c 嗎"),
    ("使用C嗎\uff1f", "使用c嗎"),
    ("5 ms", "5 ms"),
    ("5ms", "5ms"),
    ("user_id", "user_id"),
    ("userid", "userid"),
    ("file-name / path", "file-name / path"),
    ("\ufeffA\t\u2003B\ufeff。", "a b"),
    ("A\u0085B", "a\u0085b"),
    ("A\u001cB", "a\u001cb"),
]


@pytest.mark.parametrize("value,expected", FAQ_NORMALIZATION_CASES)
def test_question_normalization_matches_exact_v2(value, expected):
    assert normalize_question(value) == expected


@pytest.mark.parametrize(
    "question,variant",
    [
        ("How do I set up the project?", "How do I setup the project?"),
        ("這個專案使用 C 嗎\uff1f", "這個專案使用C嗎\uff1f"),
        ("Latency is 5 ms?", "Latency is 5ms?"),
        ("Does user_id exist?", "Does userid exist?"),
    ],
)
def test_internal_question_structure_can_be_explicitly_approved(question, variant):
    assert validate_question_variants(question, [variant]) == [variant]


def test_no_match_reason_is_private_stored_returned_and_cleared_on_success(tmp_path):
    database, manager, store, chat, service, _, _, _ = faq_system(tmp_path / "build")
    application = _application_without_github(tmp_path / "admin")
    application.state.admin_operations = replace(
        application.state.admin_operations, database=database, local_portfolio=store
    )
    application.state.runtime_database = database
    application.state.bundle_manager = manager
    application.state.chat_service = service
    with TestClient(application, base_url=ORIGIN) as client:
        headers = {"Origin": ORIGIN, "X-CSRF-Token": _login(client)}
        queue = client.post(
            "/api/admin/portfolio/faq/check", headers=headers, json={"locale": "en"}
        ).json()
        entry = queue["entries"][0]
        assert entry["no_match_reason"] is None
        root = f"/api/admin/portfolio/faq/{entry['entry_id']}"
        chat.no_match = True
        response = client.post(
            root + "/regenerate", headers=headers, json={"revision": entry["revision"]}
        )
        assert response.status_code == 200
        entry = response.json()
        assert entry["no_match_reason"] == "MODEL_INSUFFICIENT_EVIDENCE"
        assert entry["coverage_status"] == "no_relevant_content"
        assert entry["dropped_segments"] == []
        owner = client.get("/api/admin/portfolio/faq?locale=en", headers=headers)
        assert owner.headers["cache-control"] == "no-store"
        assert owner.json()["entries"][0]["no_match_reason"] == "MODEL_INSUFFICIENT_EVIDENCE"
        with database.connection() as connection:
            stored = connection.execute(
                "SELECT no_match_reason, diagnostics_json FROM faq_entries WHERE entry_id = ?",
                (entry["entry_id"],),
            ).fetchone()
        assert tuple(stored) == ("MODEL_INSUFFICIENT_EVIDENCE", "[]")
        reviewed = client.post(
            root + "/review",
            headers=headers,
            json={"revision": entry["revision"], "action": "approve"},
        )
        assert reviewed.status_code == 200
        entry = reviewed.json()
        public = client.get("/api/public/faq?locale=en")
        exported = client.get("/api/admin/portfolio/faq/export?locale=en", headers=headers)
        assert public.json() == exported.json()
        assert len(public.json()["entries"]) == 1
        assert set(public.json()["entries"][0]) == {
            "question",
            "variants",
            "answer_markdown",
            "citations",
        }
        assert (
            "no_match_reason" not in public.text
            and "MODEL_INSUFFICIENT_EVIDENCE" not in public.text
        )
        chat.no_match = False

        def check_cleared_before_call():
            current = client.get("/api/admin/portfolio/faq?locale=en", headers=headers).json()[
                "entries"
            ][0]
            assert current["no_match_reason"] is None
            assert current["coverage_status"] == "unchecked"

        chat.hook = check_cleared_before_call
        response = client.post(
            root + "/regenerate", headers=headers, json={"revision": entry["revision"]}
        )
        assert response.status_code == 200
        entry = response.json()
        assert entry["no_match_reason"] is None and entry["coverage_status"] == "answered"
        assert entry["dropped_segments"] == []
        with database.connection() as connection:
            assert (
                connection.execute(
                    "SELECT no_match_reason FROM faq_entries WHERE entry_id = ?",
                    (entry["entry_id"],),
                ).fetchone()[0]
                is None
            )
