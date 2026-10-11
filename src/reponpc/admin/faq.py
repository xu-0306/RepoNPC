"""Owner-reviewed FAQ state, kept outside immutable publication bundles."""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import unicodedata
import uuid
from collections.abc import Callable
from dataclasses import asdict
from typing import Any, Literal

from reponpc.admin.faq_registry import STANDARD_QUESTIONS
from reponpc.bundles.manager import BundleManager
from reponpc.chat.service import GroundedChatService
from reponpc.indexing.public_profile import parse_public_profile_bytes
from reponpc.runtime.database import RuntimeDatabase

Locale = Literal["zh-TW", "en"]
ClaimKind = Literal["role", "responsibility", "achievement", "context"]
_PUBLIC_CITATION_FIELDS = (
    "id",
    "evidence_id",
    "evidence_class",
    "repository",
    "commit_sha",
    "path",
    "start_line",
    "end_line",
    "title",
    "excerpt",
    "url",
)


class FaqError(ValueError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__("FAQ operation could not be completed")


class ReviewedFaq:
    def __init__(
        self,
        *,
        database: RuntimeDatabase,
        bundles: BundleManager,
        chat_supplier: Callable[[], GroundedChatService | None],
    ) -> None:
        self.database = database
        self.bundles = bundles
        self.chat_supplier = chat_supplier

    def initialize_queue(self, locale: Locale) -> dict[str, Any]:
        with self.bundles.acquire_snapshot() as (_index, bundle_id, directory):
            profile = parse_public_profile_bytes((directory / "profile.json").read_bytes())
            questions: list[tuple[str, ClaimKind, str, str | None]] = [
                (key, kind, texts[locale], key) for key, kind, texts in STANDARD_QUESTIONS
            ]
            known = {item[2] for item in questions}
            for question in profile.locales[locale].suggested_questions:
                if question in known:
                    continue
                known.add(question)
                key = "suggested_" + hashlib.sha256(question.encode()).hexdigest()
                questions.append((key, "context", question, None))
            with self.database.connection() as connection:
                connection.execute("BEGIN IMMEDIATE")
                for key, kind, question, topic in questions:
                    connection.execute(
                        "INSERT OR IGNORE INTO faq_entries "
                        "(entry_id, question_key, bundle_id, locale, question, topic, claim_kind) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?)",
                        (uuid.uuid4().hex, key, bundle_id, locale, question, topic, kind),
                    )
                connection.commit()
        return self.view(locale)

    def view(self, locale: Locale) -> dict[str, Any]:
        active = self.bundles.status().active_bundle_id
        with self.database.connection() as connection:
            rows = connection.execute(
                "SELECT * FROM faq_entries WHERE locale = ? ORDER BY topic IS NULL, rowid",
                (locale,),
            ).fetchall()
        return {
            "bundle_id": active,
            "locale": locale,
            "entries": [self._owner_entry(row, active) for row in rows],
        }

    def regenerate(self, entry_id: str, revision: int) -> dict[str, Any]:
        row = self._entry(entry_id)
        if row["revision"] != revision:
            raise FaqError("FAQ_CONFLICT")
        chat = self.chat_supplier()
        if chat is None:
            raise FaqError("SERVICE_NOT_READY")
        self._update(
            entry_id,
            revision,
            {
                "review_state": "pending",
                "error_code": None,
                "answer_markdown": None,
                "citations_json": "[]",
                "diagnostics_json": "[]",
                "coverage_status": "unchecked",
            },
        )
        revision += 1
        try:
            delivery = chat.answer_for_review(
                message=row["question"],
                locale=row["locale"],
            )
        except Exception as exc:
            # Persist only safe codes, never exceptions/provider bodies or prompts.
            code = getattr(exc, "code", None)
            if code is None:
                failure = getattr(exc, "failure", None)
                code = getattr(failure, "code", "FAQ_GENERATION_FAILED")
            allowed = {
                "CONCURRENCY_LIMIT",
                "TIMEOUT",
                "PROVIDER_TIMEOUT",
                "PROVIDER_UNAVAILABLE",
                "SERVICE_NOT_READY",
            }
            self._update(
                entry_id,
                revision,
                {
                    "error_code": str(code) if str(code) in allowed else "FAQ_GENERATION_FAILED",
                    "review_state": "pending",
                },
            )
            if not hasattr(exc, "code") and not hasattr(exc, "failure"):
                raise FaqError("FAQ_GENERATION_FAILED") from None
            raise
        status = (
            "no_relevant_content"
            if not delivery.citations
            else (
                "partially_answered"
                if delivery.insufficient_evidence or delivery.discarded_segments
                else "answered"
            )
        )
        self._update(
            entry_id,
            revision,
            {
                "bundle_id": delivery.index_version,
                "answer_markdown": delivery.answer_markdown,
                "citations_json": json.dumps([asdict(item) for item in delivery.citations]),
                "diagnostics_json": json.dumps(
                    [
                        {"segment_index": index, "reason_codes": list(reasons)}
                        for index, reasons in delivery.discarded_segments
                    ]
                ),
                "coverage_status": status,
                "review_state": "pending",
                "error_code": None,
                "rewrite_json": None,
            },
        )
        return self._owner_entry(self._entry(entry_id), self.bundles.status().active_bundle_id)

    def replace_variants(
        self,
        entry_id: str,
        revision: int,
        bundle_id: str,
        variants: list[str],
    ) -> dict[str, Any]:
        with (
            self.bundles.acquire_snapshot() as (
                _index,
                active_bundle_id,
                _directory,
            ),
            self.database.connection() as connection,
        ):
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT * FROM faq_entries WHERE entry_id = ?", (entry_id,)
            ).fetchone()
            if row is None:
                raise FaqError("FAQ_NOT_FOUND")
            validated = validate_question_variants(row["question"], variants)
            cursor = connection.execute(
                "UPDATE faq_entries SET variants_json = ?, review_state = 'pending', "
                "rewrite_json = NULL, "
                "revision = revision + 1 WHERE entry_id = ? AND revision = ? "
                "AND bundle_id = ? AND ? = ?",
                (
                    json.dumps(validated, ensure_ascii=False, separators=(",", ":")),
                    entry_id,
                    revision,
                    bundle_id,
                    bundle_id,
                    active_bundle_id,
                ),
            )
            if cursor.rowcount != 1:
                connection.rollback()
                if row["bundle_id"] != bundle_id or bundle_id != active_bundle_id:
                    raise FaqError("FAQ_STALE")
                raise FaqError("FAQ_CONFLICT")
            connection.commit()
            return self._owner_entry(self._entry(entry_id), active_bundle_id)

    def review(self, entry_id: str, revision: int, action: str) -> dict[str, Any]:
        row = self._entry(entry_id)
        if row["bundle_id"] != self.bundles.status().active_bundle_id:
            raise FaqError("FAQ_STALE")
        if action == "approve" and (row["answer_markdown"] is None or row["error_code"]):
            raise FaqError("FAQ_NOT_READY")
        self._update(
            entry_id, revision, {"review_state": "approved" if action == "approve" else "rejected"}
        )
        return self._owner_entry(self._entry(entry_id), self.bundles.status().active_bundle_id)

    def public_payload(self, locale: Locale) -> dict[str, Any]:
        # One allowlist serves public delivery and JSON export. No runtime row is serialized.
        with (
            self.bundles.acquire_snapshot() as (_index, bundle_id, _directory),
            self.database.connection() as connection,
        ):
            return self.public_payload_for_bundle(locale, bundle_id, connection)

    def public_payload_for_bundle(
        self, locale: Locale, bundle_id: str, connection: sqlite3.Connection
    ) -> dict[str, Any]:
        """Project approved rows against a caller's already-captured bundle identity."""
        if self.bundles.status().active_bundle_id != bundle_id:
            raise FaqError("FAQ_STALE")
        rows = connection.execute(
            "SELECT question, variants_json, answer_markdown, citations_json "
            "FROM faq_entries WHERE locale = ? AND bundle_id = ? "
            "AND review_state = 'approved' "
            "AND error_code IS NULL AND answer_markdown IS NOT NULL "
            "ORDER BY rowid",
            (locale, bundle_id),
        ).fetchall()
        entries: list[dict[str, Any]] = []
        for row in rows:
            citations = json.loads(row["citations_json"])
            entries.append(
                {
                    "question": row["question"],
                    "variants": json.loads(row["variants_json"]),
                    "answer_markdown": row["answer_markdown"],
                    "citations": [
                        {key: citation[key] for key in _PUBLIC_CITATION_FIELDS if key in citation}
                        for citation in citations
                    ],
                }
            )
        return {
            "bundle_id": bundle_id,
            "locale": locale,
            "entries": entries,
        }

    def _entry(self, entry_id: str) -> sqlite3.Row:
        with self.database.connection() as connection:
            row = connection.execute(
                "SELECT * FROM faq_entries WHERE entry_id = ?", (entry_id,)
            ).fetchone()
        if row is None:
            raise FaqError("FAQ_NOT_FOUND")
        return row

    def _update(self, entry_id: str, revision: int, values: dict[str, Any]) -> None:
        values = {"rewrite_json": None, **values}
        with self.database.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            # Keys are internal fixed call-site columns, never request-controlled.
            cursor = connection.execute(
                "UPDATE faq_entries SET "
                + ", ".join(f"{key} = ?" for key in values)
                + ", revision = revision + 1 WHERE entry_id = ? AND revision = ?",
                (*values.values(), entry_id, revision),
            )
            if cursor.rowcount != 1:
                connection.rollback()
                raise FaqError("FAQ_CONFLICT")
            connection.commit()

    @staticmethod
    def _owner_entry(row: sqlite3.Row, active: str | None) -> dict[str, Any]:
        return {
            "entry_id": row["entry_id"],
            "bundle_id": row["bundle_id"],
            "question": row["question"],
            "variants": json.loads(row["variants_json"]),
            "topic": row["topic"],
            "claim_kind": row["claim_kind"],
            "answer_markdown": row["answer_markdown"],
            "citations": json.loads(row["citations_json"]),
            "dropped_segments": json.loads(row["diagnostics_json"]),
            "coverage_status": row["coverage_status"],
            "review_state": row["review_state"],
            "needs_reconfirmation": row["bundle_id"] != active,
            "error_code": row["error_code"],
            "revision": row["revision"],
        }


def normalize_question(value: str) -> str:
    """Use the offline matcher v2 equality rule for owner-approved variants."""
    normalized = unicodedata.normalize("NFKC", value).lower()
    # Match ECMAScript whitespace; Python's \s adds NEL/control separators and omits BOM.
    normalized = re.sub(
        r"[\u0009-\u000d\u0020\u00a0\u1680\u2000-\u200a\u2028\u2029\u202f\u205f\u3000\ufeff]+",
        " ",
        normalized,
    )
    return normalized.strip(" ").rstrip("?!。., ")


def validate_question_variants(question: str, variants: object) -> list[str]:
    if not isinstance(variants, list) or len(variants) > 8:
        raise FaqError("FAQ_VARIANTS_INVALID")
    seen = {normalize_question(question)}
    validated: list[str] = []
    for variant in variants:
        if not isinstance(variant, str):
            raise FaqError("FAQ_VARIANTS_INVALID")
        trimmed = variant.strip()
        normalized = normalize_question(trimmed)
        if not trimmed or len(trimmed) > 200 or not normalized or normalized in seen:
            raise FaqError("FAQ_VARIANTS_INVALID")
        seen.add(normalized)
        validated.append(trimmed)
    return validated
