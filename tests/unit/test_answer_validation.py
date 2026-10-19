"""Adversarial answer envelope and citation policy tests."""

from __future__ import annotations

import pytest

from reponpc.bundles.index_reader import IndexedEvidence
from reponpc.chat.answers import validate_v2_answer


def evidence(
    source_id: str,
    *,
    evidence_class: str = "REPOSITORY_FACT",
    content: str = "bounded fixture content",
) -> tuple[str, IndexedEvidence]:
    return (
        source_id,
        IndexedEvidence(
            evidence_id="E_" + "a" * 24,
            evidence_class=evidence_class,
            repository_slug="owner/repo",
            commit_sha="b" * 40,
            path="src/app.py",
            start_line=10,
            end_line=12,
            title="Fixture",
            symbol=None,
            content=content,
            language="python",
            metadata={},
        ),
    )


def test_validated_answer_builds_server_owned_immutable_citation() -> None:
    selected = dict([evidence("S1")])
    result = validate_v2_answer(
        {
            "segments": [
                {
                    "kind": "project",
                    "text": "The repository implements retrieval.",
                    "source_ids": ["S1"],
                }
            ],
            "insufficient_evidence": False,
        },
        selected,
        "en",
    )

    assert result.insufficient_evidence is False
    assert result.no_match_reason is None
    assert result.citations[0].url == (
        "https://github.com/owner/repo/blob/" + "b" * 40 + "/src/app.py#L10-L12"
    )


@pytest.mark.parametrize(
    "answer,used",
    [
        ("Unknown source. [S9]", ["S9"]),
        ("Uncited material claim.", []),
        ("Unsafe [citation](https://evil.test). [S1]", ["S1"]),
        ("<script>alert(1)</script> [S1]", ["S1"]),
    ],
)
def test_unknown_uncited_or_active_content_becomes_abstention(answer: str, used: list[str]) -> None:
    result = validate_v2_answer(
        {
            "segments": [{"kind": "project", "text": answer, "source_ids": used}],
            "insufficient_evidence": False,
        },
        dict([evidence("S1")]),
        "en",
    )

    assert result.insufficient_evidence is True
    assert result.citations == ()


def test_v2_person_paraphrase_is_backend_rendered_in_both_locales() -> None:
    selected = dict(
        [
            evidence(
                "S1",
                evidence_class="OWNER_ASSERTION",
                content="I built the retrieval service with FastAPI.",
            )
        ]
    )
    result = validate_v2_answer(
        {
            "segments": [
                {
                    "kind": "person",
                    "text": "{{owner}} created the retrieval service with FastAPI.",
                    "source_ids": ["S1"],
                }
            ],
            "insufficient_evidence": False,
        },
        selected,
        "en",
        owner_name="Alice",
    )

    assert result.insufficient_evidence is False
    assert "In Alice's own words" in result.answer_markdown
    assert "Alice created" in result.answer_markdown
    assert "[S1]" in result.answer_markdown
    assert result.citations[0].id == "S1"


def test_v2_cjk_person_paraphrase_keeps_matching_owner_assertion() -> None:
    result = validate_v2_answer(
        {
            "segments": [
                {
                    "kind": "person",
                    "text": "{{owner}} 開發了檢索服務。",
                    "source_ids": ["S1"],
                }
            ],
            "insufficient_evidence": False,
        },
        dict(
            [
                evidence(
                    "S1",
                    evidence_class="OWNER_ASSERTION",
                    content="我用 FastAPI 建立檢索服務。",
                )
            ]
        ),
        "zh-TW",
        owner_name="王小明",
    )

    assert result.insufficient_evidence is False
    assert "王小明 自述" in result.answer_markdown


def test_v2_inflation_or_invented_number_drops_only_that_segment() -> None:
    result = validate_v2_answer(
        {
            "segments": [
                {
                    "kind": "person",
                    "text": "{{owner}} built the API.",
                    "source_ids": ["S1"],
                },
                {
                    "kind": "person",
                    "text": "{{owner}} led a team of 7.",
                    "source_ids": ["S1"],
                },
                {
                    "kind": "project",
                    "text": "The tool implements retrieval.",
                    "source_ids": ["S2"],
                },
            ],
            "insufficient_evidence": False,
        },
        dict(
            [
                evidence(
                    "S1",
                    evidence_class="OWNER_ASSERTION",
                    content="I built the API.",
                ),
                evidence("S2", content="The tool implements retrieval."),
            ]
        ),
        "en",
        owner_name="Alice",
    )

    assert result.insufficient_evidence is False
    assert "built the API" in result.answer_markdown
    assert "led a team" not in result.answer_markdown
    assert {citation.id for citation in result.citations} == {"S1", "S2"}
    assert result.discarded_reason_codes == ("INFLATION_UNSUPPORTED", "NUMBER_UNSUPPORTED")
    assert result.no_match_reason is None


def test_v2_participation_accepts_dates_but_drops_role_claims() -> None:
    result = validate_v2_answer(
        {
            "segments": [
                {
                    "kind": "participation",
                    "text": "{{owner}} was active from 2024-03 through 2025-01.",
                    "source_ids": ["S1"],
                },
                {
                    "kind": "participation",
                    "text": "{{owner}} led the backend team.",
                    "source_ids": ["S1"],
                },
                {
                    "kind": "project",
                    "text": "The project uses SQLite.",
                    "source_ids": ["S2"],
                },
            ],
            "insufficient_evidence": False,
        },
        dict(
            [
                evidence(
                    "S1",
                    evidence_class="PARTICIPATION",
                    content="Active from 2024-03 through 2025-01.",
                ),
                evidence("S2", content="The project uses SQLite."),
            ]
        ),
        "en",
        owner_name="Alice",
    )

    assert result.insufficient_evidence is False
    assert "2024-03" in result.answer_markdown
    assert "led the backend" not in result.answer_markdown


def test_v2_participation_and_inference_cannot_assign_personal_roles() -> None:
    result = validate_v2_answer(
        {
            "segments": [
                {
                    "kind": "participation",
                    "text": "{{owner}} was the backend engineer.",
                    "source_ids": ["S1"],
                },
                {
                    "kind": "inference",
                    "text": "{{owner}} designed the backend architecture.",
                    "source_ids": ["S2"],
                },
                {
                    "kind": "project",
                    "text": "The repository contains a backend API.",
                    "source_ids": ["S2"],
                },
            ],
            "insufficient_evidence": False,
        },
        dict(
            [
                evidence("S1", evidence_class="PARTICIPATION", content="2024-03 commits"),
                evidence("S2", content="The repository contains a backend API."),
            ]
        ),
        "en",
        owner_name="Alice",
    )

    assert result.insufficient_evidence is False
    assert "engineer" not in result.answer_markdown
    assert "Alice designed" not in result.answer_markdown
    assert "backend API" in result.answer_markdown


@pytest.mark.parametrize(
    "text",
    ["其他功能", "開發工具", "這個專案實作了 API"],
)
def test_v2_cjk_project_phrases_are_not_person_claims(text: str) -> None:
    result = validate_v2_answer(
        {
            "segments": [{"kind": "project", "text": text, "source_ids": ["S1"]}],
            "insufficient_evidence": False,
        },
        dict([evidence("S1")]),
        "zh-TW",
        owner_name="王小明",
    )

    assert result.insufficient_evidence is False
    assert text in result.answer_markdown


def test_v2_identity_recall_reclassifies_project_as_person() -> None:
    result = validate_v2_answer(
        {
            "segments": [{"kind": "project", "text": "Alice built the API.", "source_ids": ["S1"]}],
            "insufficient_evidence": False,
        },
        dict(
            [
                evidence(
                    "S1",
                    evidence_class="OWNER_ASSERTION",
                    content="I built the API.",
                )
            ]
        ),
        "en",
        owner_name="Alice",
    )

    assert result.insufficient_evidence is True
    assert "OWNER_REFERENCE_MISSING" in result.discarded_reason_codes
    assert result.no_match_reason == "ALL_SEGMENTS_DROPPED"
    assert "PROJECT_OWNER_REFERENCE" not in result.discarded_reason_codes


@pytest.mark.parametrize(
    "segment",
    [
        {"kind": "project", "text": "See https://evil.test", "source_ids": ["S1"]},
        {"kind": "project", "text": "<b>unsafe</b>", "source_ids": ["S1"]},
        {"kind": "project", "text": "unknown source", "source_ids": ["S9"]},
        {"kind": "project", "text": "No source", "source_ids": []},
        {"kind": "unknown", "text": "Unknown kind", "source_ids": ["S1"]},
    ],
)
def test_v2_integrity_failures_reject_the_complete_answer(segment: dict[str, object]) -> None:
    result = validate_v2_answer(
        {"segments": [segment], "insufficient_evidence": False},
        dict([evidence("S1")]),
        "en",
        owner_name="Alice",
    )

    assert result.insufficient_evidence is True
    assert result.answer_markdown == (
        "I couldn't find anything about that in this portfolio. Try one of these questions."
    )
    assert result.citations == ()


def test_v2_no_valid_source_returns_localized_no_match_and_suggestions() -> None:
    result = validate_v2_answer(
        {"segments": [], "insufficient_evidence": False},
        {},
        "zh-TW",
        suggested_questions=["專案用了哪些技術\uff1f", "https://ignored.example", "第二個問題"],
    )

    assert result.insufficient_evidence is True
    assert result.answer_markdown.startswith("這個問題我在作品集裡找不到相關內容")
    assert result.suggested_questions == ("專案用了哪些技術\uff1f", "第二個問題")


def test_v2_inference_cycle_rejects_the_complete_answer() -> None:
    result = validate_v2_answer(
        {
            "segments": [{"kind": "inference", "text": "Derived claim", "source_ids": ["S1"]}],
            "insufficient_evidence": False,
        },
        dict([evidence("S1", evidence_class="MODEL_INFERENCE")]),
        "en",
    )

    assert result.insufficient_evidence is True
    assert result.citations == ()
    assert result.no_match_reason == "INFERENCE_CYCLE"


def test_v2_entrypoint_rejects_legacy_or_missing_v2_fields() -> None:
    result = validate_v2_answer(
        {
            "answer_markdown": "The old envelope. [S1]",
            "used_source_ids": ["S1"],
            "inferences": [],
            "insufficient_evidence": False,
        },
        dict([evidence("S1")]),
        "en",
    )

    assert result.insufficient_evidence is True
    assert result.answer_markdown == (
        "I couldn't find anything about that in this portfolio. Try one of these questions."
    )


@pytest.mark.parametrize(
    ("claim", "source", "accepted"),
    [
        ("{{owner}} was active in 2024-03.", "Active in 2024 and 03.", False),
        ("{{owner}} was active in 2024-03.", "Active in 2024年3月.", True),
        ("{{owner}} improved uptime by 10%.", "I improved uptime by 10.", False),
        ("{{owner}} improved uptime by 10%.", "I improved uptime by 百分之十.", True),
    ],
)
def test_v2_numeric_facts_keep_date_and_percent_units(
    claim: str, source: str, accepted: bool
) -> None:
    result = validate_v2_answer(
        {
            "segments": [{"kind": "person", "text": claim, "source_ids": ["S1"]}],
            "insufficient_evidence": False,
        },
        dict([evidence("S1", evidence_class="OWNER_ASSERTION", content=source)]),
        "en",
        owner_name="Alice",
    )

    assert result.insufficient_evidence is not accepted


@pytest.mark.parametrize(
    "locale,text",
    [
        ("en", "We use SQLite; they document our API and share their tools with us."),
        ("zh-TW", "我們使用 SQLite，他們在文件裡介紹 API。"),  # noqa: RUF001
        ("en", "The API keeps \uff21\uff30\uff29 casing."),
    ],
)
def test_collective_project_text_is_preserved(locale, text) -> None:
    result = validate_v2_answer(
        {
            "segments": [{"kind": "project", "text": text, "source_ids": ["S1"]}],
            "insufficient_evidence": False,
        },
        dict([evidence("S1")]),
        locale,
        owner_name="Alice",
    )
    assert result.answer_markdown == text + " [S1]"
    assert not result.insufficient_evidence


@pytest.mark.parametrize("kind", ["project", "inference"])
@pytest.mark.parametrize(
    "text",
    [
        "His work uses SQLite.",
        "He built the API.",
        "I built the API.",
        "他建立 API。",
        "我的工作使用 SQLite。",
    ],
)
def test_singular_reference_is_dropped_without_rewriting_valid_sibling(kind, text) -> None:
    result = validate_v2_answer(
        {
            "segments": [
                {"kind": kind, "text": text, "source_ids": ["S1"]},
                {"kind": "project", "text": "SQLite stores records.", "source_ids": ["S2"]},
            ],
            "insufficient_evidence": False,
        },
        dict([evidence("S1", evidence_class="OWNER_ASSERTION", content=text), evidence("S2")]),
        "en",
        owner_name="Alice",
    )
    assert result.answer_markdown == "SQLite stores records. [S2]"
    assert result.discarded_segments == ((0, ("OWNER_REFERENCE_MISSING",)),)
    assert "Alice work" not in result.answer_markdown


@pytest.mark.parametrize(
    "raw,selected,reason",
    [
        (
            {"segments": [], "insufficient_evidence": True},
            dict([evidence("S1")]),
            "MODEL_INSUFFICIENT_EVIDENCE",
        ),
        ({}, dict([evidence("S1")]), "ENVELOPE_SCHEMA_INVALID"),
        ('{"segments":', dict([evidence("S1")]), "ENVELOPE_SCHEMA_INVALID"),
        (
            {
                "segments": [{"kind": "project", "text": "Unknown source", "source_ids": ["S9"]}],
                "insufficient_evidence": False,
            },
            dict([evidence("S1")]),
            "SOURCE_ID_UNKNOWN",
        ),
        (
            {
                "segments": [
                    {
                        "kind": "project",
                        "text": "Unselected evidence",
                        "source_ids": ["E_unselected"],
                    }
                ],
                "insufficient_evidence": False,
            },
            dict([evidence("S1")]),
            "SOURCE_ID_UNKNOWN",
        ),
        (
            {"segments": [], "insufficient_evidence": False},
            dict([evidence("invalid")]),
            "SELECTED_MAP_INVALID",
        ),
        (
            {"segments": [], "insufficient_evidence": False},
            dict([evidence("S1")]),
            "ALL_SEGMENTS_DROPPED",
        ),
        ({"segments": [], "insufficient_evidence": False}, {}, "NO_EVIDENCE_SELECTED"),
    ],
)
def test_closed_no_match_reasons_preserve_the_visitor_reply(raw, selected, reason):
    result = validate_v2_answer(raw, selected, "en", suggested_questions=["Next question?"])
    assert result.no_match_reason == reason
    assert result.answer_markdown == (
        "I couldn't find anything about that in this portfolio. Try one of these questions."
    )
    assert result.insufficient_evidence is True
    assert result.citations == ()
    assert result.suggested_questions == ("Next question?",)


@pytest.mark.parametrize(
    "text",
    [
        "See https://example.invalid",
        "<b>Markup</b>",
        "[a](relative)",
        "Inline [S1]",
    ],
)
def test_markup_reason_rejects_all_segments_including_safe_siblings(text):
    result = validate_v2_answer(
        {
            "segments": [
                {"kind": "project", "text": "Safe sibling", "source_ids": ["S1"]},
                {"kind": "project", "text": text, "source_ids": ["S1"]},
            ],
            "insufficient_evidence": False,
        },
        dict([evidence("S1")]),
        "en",
    )
    assert result.no_match_reason == "MODEL_AUTHORED_MARKUP"
    assert result.insufficient_evidence is True and result.citations == ()
    assert "Safe sibling" not in result.answer_markdown


@pytest.mark.parametrize("error_type", [ValueError, TypeError, AttributeError, KeyError])
def test_unexpected_validation_errors_have_a_fixed_reason(monkeypatch, error_type):
    def unexpected(*args, **kwargs):
        raise error_type("PRIVATE_VALIDATION_CANARY")

    monkeypatch.setattr("reponpc.chat.answers._validate_v2_envelope", unexpected)
    result = validate_v2_answer(
        {"segments": [], "insufficient_evidence": False},
        dict([evidence("S1")]),
        "en",
    )
    assert result.no_match_reason == "VALIDATION_UNEXPECTED"
    assert result.insufficient_evidence is True and result.citations == ()
    assert "PRIVATE_VALIDATION_CANARY" not in result.answer_markdown


def test_model_abstention_reason_keeps_precedence_over_selected_map_validation():
    result = validate_v2_answer(
        {"segments": [], "insufficient_evidence": True},
        {},
        "en",
    )
    assert result.no_match_reason == "MODEL_INSUFFICIENT_EVIDENCE"
    assert result.insufficient_evidence is True
