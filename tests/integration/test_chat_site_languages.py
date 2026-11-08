"""ADR-079 runtime, FAQ and public API behavior across W1-built site sets."""

from __future__ import annotations

import json
import sqlite3

import pytest
from fastapi.testclient import TestClient

from reponpc.admin.faq import ReviewedFaq
from reponpc.api.public import SetupState
from reponpc.api.visitor_ingress import _message, create_visitor_gateway_app
from reponpc.chat import answers
from reponpc.chat.service import ChatDelivery, GroundedChatService
from reponpc.i18n.catalog import translate
from reponpc.i18n.convert import convert
from reponpc.i18n.languages import LANGUAGES, english_name, get_language, language_tags
from reponpc.i18n.plan import ANALYSIS_LOCALES, LocaleNotEnabledError, plan_languages
from reponpc.indexing.public_profile import (
    localized_public_profile_bytes,
    parse_public_profile_bytes,
)
from reponpc.main import create_app
from reponpc.providers.runtime import ProviderRuntime
from reponpc.runtime.database import MIGRATIONS, Migration, RuntimeDatabase, RuntimeDatabaseError
from tests.integration.test_index_build import DeterministicEmbeddingProvider
from tests.integration.test_reviewed_faq import OwnerLimits, SyntheticChat
from tests.integration.test_site_language_bundles import (
    SITE_SETS,
    _build,
    _legacy_bundle,
    _manager,
    _verify,
)


@pytest.mark.parametrize("broken", [False, True])
def test_migration_38_preserves_every_faq_column_rowid_and_constraint(tmp_path, broken):
    database = RuntimeDatabase(tmp_path / "runtime")
    database.initialize(migrations=MIGRATIONS[:37])
    with database.connection() as connection:
        for ordinal, tag in enumerate(ANALYSIS_LOCALES):
            connection.execute(
                "INSERT INTO faq_entries(rowid, entry_id, question_key, bundle_id, locale, "
                "question, topic, claim_kind, answer_markdown, citations_json, diagnostics_json, "
                "coverage_status, review_state, rewrite_json, error_code, revision, "
                "variants_json, no_match_reason) VALUES "
                "(?, ?, 'q', 'bundle', ?, 'Question', 'topic', 'context', 'Answer', '[{}]', "
                "'[{}]', 'answered', 'approved', '{}', NULL, 7, '[\"Variant\"]', "
                "'ALL_SEGMENTS_DROPPED')",
                (9 - ordinal * 4, f"entry-{ordinal}", tag),
            )
        before = [
            tuple(row)
            for row in connection.execute("SELECT rowid,* FROM faq_entries ORDER BY rowid")
        ]
        foreign_keys = connection.execute("PRAGMA foreign_key_list(faq_entries)").fetchall()
        indexes = [
            (
                row[2],
                tuple(item[2] for item in connection.execute(f"PRAGMA index_info('{row[1]}')")),
            )
            for row in connection.execute("PRAGMA index_list(faq_entries)")
        ]
    migration = MIGRATIONS[37]
    assert migration.version == 38
    if broken:
        failed = Migration(38, migration.name, (*migration.statements, "INVALID SQL"))
        with pytest.raises(RuntimeDatabaseError):
            database.initialize(migrations=(*MIGRATIONS[:37], failed))
        assert database.schema_version() == 37
        with database.connection() as connection:
            assert [
                tuple(row)
                for row in connection.execute("SELECT rowid,* FROM faq_entries ORDER BY rowid")
            ] == before
            assert (
                "CHECK(locale IN"
                in connection.execute(
                    "SELECT sql FROM sqlite_schema WHERE name = 'faq_entries'"
                ).fetchone()[0]
            )
    database.initialize()
    database.initialize()
    assert database.schema_version() == MIGRATIONS[-1].version == 39
    with database.connection() as connection:
        assert [
            tuple(row)
            for row in connection.execute("SELECT rowid,* FROM faq_entries ORDER BY rowid")
        ] == before
        assert connection.execute("PRAGMA foreign_key_list(faq_entries)").fetchall() == foreign_keys
        assert [
            (
                row[2],
                tuple(item[2] for item in connection.execute(f"PRAGMA index_info('{row[1]}')")),
            )
            for row in connection.execute("PRAGMA index_list(faq_entries)")
        ] == indexes
        for tag in language_tags():
            connection.execute(
                "INSERT INTO faq_entries(entry_id,question_key,bundle_id,locale,question,"
                "claim_kind) "
                "VALUES (?, 'registry', 'bundle', ?, 'Question', 'context')",
                (tag, tag),
            )
            with pytest.raises(sqlite3.IntegrityError):
                connection.execute(
                    "INSERT INTO faq_entries(entry_id,question_key,bundle_id,locale,question,"
                    "claim_kind) "
                    "VALUES (?, 'registry', 'bundle', ?, 'Duplicate', 'context')",
                    (tag + "-duplicate", tag),
                )
        for assignment in (
            "variants_json = '{}'",
            "review_state = 'unknown'",
            "no_match_reason = 'unknown'",
            "revision = 0",
        ):
            with pytest.raises(sqlite3.IntegrityError):
                connection.execute("UPDATE faq_entries SET " + assignment)
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []


@pytest.fixture(params=SITE_SETS, scope="module", ids=lambda tags: "+".join(tags))
def site(request, tmp_path_factory):
    root = tmp_path_factory.mktemp("site-languages")
    bundle = _build(root / "build", request.param)
    manager, database = _manager(root)
    manager.activate(_verify(bundle.archive_path, root / "stage"))
    return manager, database, request.param


class RecordingChat:
    def __init__(self, bundle_id):
        self.bundle_id = bundle_id
        self.locales = []

    def answer(self, **kwargs):
        self.locales.append(kwargs["locale"])
        return ChatDelivery(
            self.bundle_id, kwargs["locale"], 0, "Python API.", (), "stop", None, False
        )


def _application(manager, database, service, gateway):
    with manager.acquire_snapshot() as (_, bundle_id, directory):
        state = SetupState(
            index_ready=True, index_version=bundle_id, model_ready=True, public_directory=directory
        )
    if gateway:
        faq = ReviewedFaq(database=database, bundles=manager, chat_supplier=lambda: None)
        return create_visitor_gateway_app(
            state_supplier=lambda: state,
            bundle_manager_supplier=lambda: manager,
            chat_service_supplier=lambda: service,
            faq_supplier=lambda: faq,
            gateway_origin="https://fixture.ts.net",
            pages_origin="https://fixture.github.io",
            listener_ready_supplier=lambda: True,
            web_dist=None,
            gateway_port=8832,
            trusted_proxy_cidrs=(),
            max_message_characters=2000,
            max_history_messages=6,
            max_history_characters=6000,
            global_concurrency=1,
            keepalive_seconds=15,
        )
    app = create_app(setup_state=state, chat_service=service, runtime_database=database)
    app.state.bundle_manager = manager
    return app


@pytest.mark.parametrize("gateway", [False, True])
def test_public_routes_use_site_default_exact_set_and_existing_validation_envelope(
    site, gateway, tmp_path
):
    manager, _database, tags = site
    database = RuntimeDatabase(tmp_path / "api-runtime")
    database.initialize()
    faq_service = ReviewedFaq(database=database, bundles=manager, chat_supplier=lambda: None)
    for tag in tags:
        entry = faq_service.initialize_queue(tag)["entries"][0]
        with database.connection() as connection:
            connection.execute(
                "UPDATE faq_entries SET answer_markdown = ?, review_state = 'approved' "
                "WHERE entry_id = ?",
                ("Python API " + tag, entry["entry_id"]),
            )
    with manager.acquire_snapshot() as (index, bundle_id, directory):
        default = index.locales.default
        document = parse_public_profile_bytes((directory / "profile.json").read_bytes())
    service = RecordingChat(bundle_id)
    with TestClient(
        _application(manager, database, service, gateway), base_url="https://fixture.ts.net"
    ) as client:
        response = client.get("/api/public/profile")
        assert response.status_code == 200
        assert response.content == localized_public_profile_bytes(document, default)
        assert response.json()["available_locales"] == [
            {"tag": tag, "endonym": get_language(tag).endonym} for tag in tags
        ]
        for tag in tags:
            profile = client.get("/api/public/profile", params={"locale": tag})
            assert profile.status_code == 200
            assert profile.content == localized_public_profile_bytes(document, tag)
            assert profile.json()["locale"] == tag
            faq = client.get("/api/public/faq", params={"locale": tag})
            assert faq.status_code == 200
            assert faq.json()["locale"] == tag
            assert faq.json() == faq_service.public_payload(tag)
            assert faq.json()["entries"][0]["answer_markdown"] == "Python API " + tag
            for extension in ("svg", "gif", "png"):
                card = client.get(f"/api/public/card.{extension}", params={"locale": tag})
                assert card.status_code == 200
                assert card.content == (directory / f"card-light-{tag}.{extension}").read_bytes()
            chat = client.post(
                "/api/public/chat/stream", json={"message": "Python?", "locale": tag}
            )
            assert chat.status_code == 200
            metadata = json.loads(
                next(line[6:] for line in chat.text.splitlines() if line.startswith("data: "))
            )
            assert metadata["locale"] == tag
            invalid_history = client.post(
                "/api/public/chat/stream",
                json={
                    "message": "Python?",
                    "locale": tag,
                    "history": [{"role": "assistant", "content": "Private invalid history"}],
                },
            )
            assert invalid_history.status_code == 400
            assert invalid_history.json()["error"]["message"] == (
                _message(get_language(tag).chrome, "VALIDATION_ERROR")
                if gateway
                else translate(tag, "validation_error", field="request", reason="invalid")
            )
            assert "Private invalid history" not in invalid_history.text
        assert service.locales == list(tags)
        assert client.get("/api/public/faq").json()["locale"] == default
        assert (
            client.get("/api/public/card.svg").content
            == (directory / f"card-light-{default}.svg").read_bytes()
        )
        assert (
            client.post("/api/public/chat/stream", json={"message": "Python?"}).status_code == 200
        )
        assert service.locales[-1] == default
        calls = len(service.locales)
        for disabled in (*[tag for tag in language_tags() if tag not in tags], "unknown"):
            for endpoint in ("profile", "faq", "card.svg"):
                invalid = client.get("/api/public/" + endpoint, params={"locale": disabled})
                assert invalid.status_code == 400
                error = invalid.json()["error"]
                assert error["code"] == "VALIDATION_ERROR"
                assert error["details"] == {"fields": [{"path": "query.locale", "code": "invalid"}]}
                assert error["message"] == translate(
                    default, "validation_error", field="locale", reason="invalid"
                )
            invalid = client.post(
                "/api/public/chat/stream", json={"message": "Python?", "locale": disabled}
            )
            assert invalid.status_code == 400
            assert invalid.json()["error"]["details"] == {
                "fields": [{"path": "body.locale", "code": "invalid"}]
            }
        assert len(service.locales) == calls


def test_directory_only_profile_serves_the_index_default(site):
    manager, _database, tags = site
    with manager.acquire_snapshot() as (index, bundle_id, directory):
        default = index.locales.default
        document = parse_public_profile_bytes((directory / "profile.json").read_bytes())
    app = create_app(
        setup_state=SetupState(
            index_ready=True, index_version=bundle_id, public_directory=directory
        )
    )
    with TestClient(app) as client:
        response = client.get("/api/public/profile")
        assert response.status_code == 200
        assert response.content == localized_public_profile_bytes(document, default)
        assert response.json()["available_locales"] == [
            {"tag": tag, "endonym": get_language(tag).endonym} for tag in tags
        ]


def test_faq_queue_review_derivation_and_disabled_rows_follow_active_set(site):
    manager, database, tags = site
    faq = ReviewedFaq(
        database=database,
        bundles=manager,
        chat_supplier=lambda: pytest.fail("conversion called a model"),
    )
    bundle_id = manager.status().active_bundle_id
    for tag in tags:
        assert faq.public_payload(tag) == {"bundle_id": bundle_id, "locale": tag, "entries": []}
    for tag in plan_languages(tags).written:
        queue = faq.initialize_queue(tag)
        assert queue["locale"] == tag
        assert len([entry for entry in queue["entries"] if entry["topic"]]) == 6
        row = queue["entries"][0]
        with database.connection() as connection:
            connection.execute(
                "UPDATE faq_entries SET question = ?, answer_markdown = ?, citations_json = ?, "
                "variants_json = ?, coverage_status = 'answered', review_state = 'approved' "
                "WHERE entry_id = ?",
                (
                    "專案使用網路程式。",
                    "專案包含資料庫與網路程式。",
                    '[{"id":"S1","excerpt":"不可轉換"}]',
                    '["網路工具?"]',
                    row["entry_id"],
                ),
            )
    for target, source in plan_languages(tags).derived:
        original = faq.view(source)["entries"][0]
        queue = faq.initialize_queue(target)
        entry = queue["entries"][0]
        assert entry["question"] == convert(original["question"], source, target)
        assert entry["answer_markdown"] == convert(original["answer_markdown"], source, target)
        assert entry["variants"] == [convert(text, source, target) for text in original["variants"]]
        assert entry["citations"] == original["citations"]
        assert entry["review_state"] == "pending"
        assert faq.public_payload(target)["entries"] == []
        with database.connection() as connection:
            keys = connection.execute(
                "SELECT question_key FROM faq_entries WHERE locale = ? "
                "ORDER BY topic IS NULL,rowid",
                (target,),
            ).fetchall()
            source_keys = connection.execute(
                "SELECT question_key FROM faq_entries WHERE locale = ? "
                "ORDER BY topic IS NULL,rowid",
                (source,),
            ).fetchall()
        assert [row[0] for row in keys] == [row[0] for row in source_keys]
        edited = faq.replace_variants(
            entry["entry_id"], entry["revision"], bundle_id, ["FAQ Python?"]
        )
        regenerated = faq.regenerate(entry["entry_id"], edited["revision"])
        assert regenerated["review_state"] == "pending"
        assert regenerated["question"] == entry["question"]
        assert regenerated["variants"] == edited["variants"]
        faq.review(entry["entry_id"], regenerated["revision"], "approve")
        assert (
            faq.public_payload(target)["entries"][0]["answer_markdown"] == entry["answer_markdown"]
        )
    for tag in (*[tag for tag in language_tags() if tag not in tags], "unknown"):
        with database.connection() as connection:
            connection.execute(
                "INSERT INTO faq_entries(entry_id,question_key,bundle_id,locale,question,"
                "claim_kind,answer_markdown,review_state) "
                "VALUES (?, 'disabled', ?, ?, 'Hidden', 'context', 'Hidden answer', 'approved')",
                (tag, bundle_id, tag),
            )
        for action in (faq.initialize_queue, faq.view, faq.public_payload):
            with pytest.raises(LocaleNotEnabledError):
                action(tag)
        with database.connection() as connection, pytest.raises(LocaleNotEnabledError):
            faq.public_payload_for_bundle(tag, bundle_id, connection)


def test_chat_service_uses_registry_language_and_rejects_disabled_before_generation(
    site, monkeypatch
):
    manager, _database, tags = site
    loaded = []
    original = answers._load_locale_policy

    def load(tag):
        loaded.append(tag)
        return original(tag)

    monkeypatch.setattr(answers, "_load_locale_policy", load)

    class Chat(SyntheticChat):
        def generate(self, messages, *args):
            self.messages = messages
            return super().generate(messages, *args)

    chat = Chat()
    service = GroundedChatService(
        bundles=manager,
        providers=ProviderRuntime(
            chat=chat, embedding=DeterministicEmbeddingProvider(), max_attempts=1
        ),
        limits=OwnerLimits(),
        max_output_tokens=16384,
        timeout_seconds=5,
    )
    for tag in tags:
        answer = service.answer_for_review(message="Python API", locale=tag)
        assert answer.locale == tag
        assert not answer.insufficient_evidence
        assert f"Respond in {english_name(tag)}." in chat.messages[0].content
    assert set(loaded) == {*tags, "en"}
    calls = chat.calls
    for tag in (*[language.tag for language in LANGUAGES if language.tag not in tags], "unknown"):
        with pytest.raises(LocaleNotEnabledError):
            service.answer_for_review(message="Python API", locale=tag)
    assert chat.calls == calls


def test_legacy_bundle_public_response_is_unchanged_and_no_files_are_rewritten(tmp_path):
    verified = _legacy_bundle(tmp_path / "stage")
    manager, database = _manager(tmp_path)
    manager.activate(verified)
    before = {path: path.read_bytes() for path in verified.directory.rglob("*") if path.is_file()}
    with manager.acquire_snapshot() as (_, bundle_id, directory):
        document = parse_public_profile_bytes((directory / "profile.json").read_bytes())
    with TestClient(_application(manager, database, RecordingChat(bundle_id), False)) as client:
        assert client.get("/api/public/profile").content == localized_public_profile_bytes(
            document, ANALYSIS_LOCALES[0]
        )
        for tag in ANALYSIS_LOCALES:
            assert client.get(
                "/api/public/profile", params={"locale": tag}
            ).content == localized_public_profile_bytes(document, tag)
    assert {path: path.read_bytes() for path in before} == before


def test_no_active_bundle_follows_a_requested_registry_language_else_english():
    with TestClient(create_app()) as client:
        response = client.get("/api/public/profile")
        assert response.status_code == 503
        assert response.json()["error"]["message"] == translate("en", "index_unavailable")
        response = client.get("/api/public/profile", params={"locale": "unknown"})
        assert response.status_code == 400
        assert response.json()["error"]["message"] == translate(
            "en", "validation_error", field="locale", reason="invalid"
        )
        for tag in language_tags():
            response = client.get("/api/public/profile", params={"locale": tag})
            assert response.status_code == 503
            assert response.json()["error"]["message"] == translate(tag, "index_unavailable")
            response = client.post(
                "/api/public/chat/stream", json={"message": "Python?", "locale": tag}
            )
            assert response.status_code == 503
            assert response.json()["error"]["message"] == _message("en", "SERVICE_NOT_READY")
