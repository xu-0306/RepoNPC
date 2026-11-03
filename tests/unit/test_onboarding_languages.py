"""ADR-079 authoring follows the registry, while durable analysis keeps its own set."""

from __future__ import annotations

import threading
from itertools import combinations
from pathlib import Path
from typing import Any

import pytest
import yaml
from pydantic import ValidationError

from reponpc.admin.batch_execution import _valid_cached_inference
from reponpc.admin.onboarding import (
    GuidedOnboardingError,
    GuidedProfileDraft,
    GuidedRepositoryDraft,
    LocalizedSuggestion,
    LocalizedTitle,
    _analysis_config,
    _analysis_response_schema,
    _parse_analysis,
    _profile_defaults,
)
from reponpc.admin.operations import AdminOperations
from reponpc.api.admin import ContributionSuggestRequest, OnboardingDraftRequest
from reponpc.config.models import LocalesConfig, validate_public_config
from reponpc.domain.evidence import EVIDENCE_ID_RE
from reponpc.i18n.convert import convert
from reponpc.i18n.languages import (
    KNOWN_SCRIPTS,
    LANGUAGES,
    allowed_scripts,
    english_name,
    language_tags,
    title_max,
)
from reponpc.i18n.plan import ANALYSIS_LOCALES, LocaleNotEnabledError, plan_languages
from reponpc.providers.contracts import ProviderResult
from tests.unit.test_guided_onboarding import FakeChat, _service
from tests.unit.test_profile_translate import _script_word

TAGS = language_tags()
SITE_SETS = list(
    dict.fromkeys(
        [site for size in range(1, len(TAGS) + 1) for site in combinations(TAGS, size)]
        + [TAGS[index:] + TAGS[:index] for index in range(len(TAGS))]
    )
)


def draft_payload(site: tuple[str, ...]) -> dict[str, Any]:
    def localized(field: str) -> dict[str, str]:
        return {locale: f"Owner {field} {locale}" for locale in site}

    return {
        "locales": {"default": site[-1], "supported": list(site)},
        "profile": {
            "display_name": "Owner",
            "github_login": "octocat",
            **{field: localized(field) for field in ("headline", "bio", "greeting")},
        },
        "repositories": [
            {
                "slug": "octocat/demo",
                "role": localized("role"),
                "summary": localized("summary"),
                "claims": [{"id": "owner-work", "kind": "role", "statement": localized("claim")}],
            }
        ],
        "confirmed_assertions": True,
    }


class LanguageChat(FakeChat):
    def __init__(self) -> None:
        super().__init__()
        self.schemas: list[dict[str, Any]] = []
        self.payload: dict[str, Any] | None = None

    def generate(self, messages, response_schema, max_output_tokens, timeout):
        self.calls += 1
        self.messages.append(messages)
        self.schemas.append(response_schema)
        self.max_output_tokens.append(max_output_tokens)
        locales = response_schema["properties"]["role"]["required"]
        texts = {locale: _profile_defaults()[locale]["headline"] for locale in locales}
        payload = self.payload or {
            "role": texts,
            "summary": texts,
            "claims": [{"id": "owner-work", "kind": "role", "statement": texts}],
        }
        return ProviderResult(payload, "stop", None, None, 1.0)


@pytest.mark.parametrize("site", SITE_SETS, ids=lambda site: ",".join(site))
def test_contribution_requests_only_written_languages_and_returns_exact_site(
    tmp_path: Path, site
) -> None:
    chat = LanguageChat()
    service, _, resolver, _ = _service(tmp_path, chat=chat)
    statement = "I help maintain public tools."
    result = service.suggest_contributions(
        session_hash="session-a", slug="octocat/demo", owner_statement=statement, locales=site
    )
    plan = plan_languages(site)
    assert chat.calls == 1 and resolver.source_calls == 0
    assert result["original_statement"] == statement
    assert result["confirmed"] is False
    system = chat.messages[0][0].content
    schema = chat.schemas[0]
    for field_schema in (
        schema["properties"]["role"],
        schema["properties"]["summary"],
        schema["properties"]["claims"]["items"]["properties"]["statement"],
    ):
        assert field_schema["required"] == list(plan.written)
        assert list(field_schema["properties"]) == list(plan.written)
        assert field_schema["additionalProperties"] is False
    proposal = result["proposal"]
    for value in (proposal["role"], proposal["summary"], proposal["claims"][0]["statement"]):
        assert list(value) == list(site)
        for locale in plan.written:
            assert f"`{locale}` ({english_name(locale)})" in system
            assert value[locale] == _profile_defaults()[locale]["headline"]
        for target, source in plan.derived:
            assert f"`{target}`" not in system
            assert value[target] == convert(value[source], source, target)


@pytest.mark.parametrize("site", SITE_SETS, ids=lambda site: ",".join(site))
@pytest.mark.parametrize("invalid", ["missing", "extra", "script"])
def test_contribution_rejects_wrong_language_set_or_ungrounded_scripts(
    tmp_path: Path, site, invalid
) -> None:
    chat = LanguageChat()
    written = plan_languages(site).written
    texts = {locale: "Owner work" for locale in written}
    invalid_texts = dict(texts)
    if invalid == "missing":
        del invalid_texts[written[-1]]
    elif invalid == "extra":
        extra = next((tag for tag in TAGS if tag not in written), "unknown")
        invalid_texts[extra] = "Unrequested language"
    else:
        invalid_texts[written[0]] = _script_word(
            next(iter(sorted(KNOWN_SCRIPTS - allowed_scripts(written[0]))))
        )
    chat.payload = {
        "role": texts,
        "summary": texts,
        "claims": [{"id": "owner-work", "kind": "role", "statement": invalid_texts}],
    }
    service, _, _, _ = _service(tmp_path, chat=chat)
    with pytest.raises(GuidedOnboardingError) as error:
        service.suggest_contributions(
            session_hash="session-a",
            slug="octocat/demo",
            owner_statement="Owner work",
            locales=site,
        )
    assert (error.value.code, error.value.reason) == (
        "PROVIDER_ERROR",
        "PROVIDER_OUTPUT_SCHEMA_INVALID",
    )
    assert chat.calls == 1


@pytest.mark.parametrize("site", SITE_SETS, ids=lambda site: ",".join(site))
@pytest.mark.parametrize("use_base", [False, True])
def test_draft_round_trips_every_language_and_keeps_other_base_settings(
    tmp_path: Path, site, use_base
) -> None:
    service, _, resolver, chat = _service(tmp_path)
    providers, _ = service._provider_dependencies()
    base, _ = _analysis_config(
        slug="octocat/demo",
        ref=None,
        include=(),
        exclude=(),
        identity=providers.embedding.identity(),
    )
    values = base.model_dump(mode="json")
    values["profile"]["location"] = "Owner location"
    values["repositories"][0]["tags"] = ["Owner tag"]
    for locale in ANALYSIS_LOCALES:
        values["profile"]["suggested_questions"][locale] = [f"Owner question {locale}"]
        values["card"]["call_to_action"][locale] = f"Owner call {locale}"
    base = validate_public_config(values)
    service._providers_supplier = lambda: None
    request = OnboardingDraftRequest.model_validate(draft_payload(site))
    draft = service.create_draft(
        profile=request.profile,
        repositories=request.repositories,
        base_config=base if use_base else None,
        confirmed_assertions=True,
        locales=request.locales,
    )
    config = validate_public_config(yaml.safe_load(draft["content"]))
    assert draft["validation"]["valid"] is True
    assert config.schema_version == 1
    assert config.locales == request.locales
    assert config.locales.default == site[-1]
    localized = (
        config.profile.headline,
        config.profile.bio,
        config.profile.greeting,
        config.profile.suggested_questions,
        config.card.call_to_action,
        config.repositories[0].role,
        config.repositories[0].summary,
        config.repositories[0].claims[0].statement,
    )
    assert all(tuple(value) == site for value in localized)
    for locale in site:
        expected_questions = values["profile"]["suggested_questions"].get(
            locale, _profile_defaults()[locale]["suggested_questions"]
        )
        expected_call = values["card"]["call_to_action"].get(
            locale, _profile_defaults()[locale]["call_to_action"]
        )
        assert config.profile.suggested_questions[locale] == tuple(
            expected_questions if use_base else _profile_defaults()[locale]["suggested_questions"]
        )
        assert config.card.call_to_action[locale] == (
            expected_call if use_base else _profile_defaults()[locale]["call_to_action"]
        )
    if use_base:
        assert config.profile.location == "Owner location"
        assert config.repositories[0].tags == ("Owner tag",)
        assert config.character == base.character and config.retrieval == base.retrieval
    assert resolver.source_calls == chat.calls == 0


@pytest.mark.parametrize("field", ["headline", "bio", "greeting", "role", "summary", "statement"])
@pytest.mark.parametrize("invalid", ["missing", "extra"])
def test_draft_rejects_wrong_keys_in_every_localized_value(tmp_path: Path, field, invalid) -> None:
    payload = draft_payload(TAGS)
    value = (
        payload["profile"][field]
        if field in ("headline", "bio", "greeting")
        else payload["repositories"][0]["claims"][0][field]
        if field == "statement"
        else payload["repositories"][0][field]
    )
    if invalid == "missing":
        del value[TAGS[-1]]
    else:
        value["unknown"] = "Unexpected text"
    with pytest.raises(ValidationError):
        OnboardingDraftRequest.model_validate(payload)
    if invalid == "missing":
        service, _, _, _ = _service(tmp_path)
        with pytest.raises(GuidedOnboardingError) as error:
            service.create_draft(
                profile=GuidedProfileDraft.model_validate(payload["profile"]),
                repositories=tuple(
                    GuidedRepositoryDraft.model_validate(repository)
                    for repository in payload["repositories"]
                ),
                base_config=None,
                confirmed_assertions=True,
                locales=LocalesConfig.model_validate(payload["locales"]),
            )
        assert error.value.code == "VALIDATION_ERROR"


@pytest.mark.parametrize("site", [[], [TAGS[0], TAGS[0]], ["unknown"], [*TAGS, TAGS[0]]])
def test_suggest_invalid_site_fails_before_provider(tmp_path: Path, site) -> None:
    with pytest.raises(ValidationError):
        ContributionSuggestRequest.model_validate(
            {"slug": "octocat/demo", "owner_statement": "Owner work", "locales": site}
        )
    service, _, _, chat = _service(tmp_path)
    with pytest.raises(GuidedOnboardingError) as error:
        service.suggest_contributions(
            session_hash="session-a",
            slug="octocat/demo",
            owner_statement="Owner work",
            locales=site,
        )
    assert error.value.code == "VALIDATION_ERROR"
    assert chat.calls == 0


def test_profile_defaults_cover_registry_and_spanish_review_notice() -> None:
    assert tuple(_profile_defaults()) == TAGS
    path = Path(__file__).parents[2] / "src/reponpc/admin/profile_defaults.yml"
    assert "# DRAFT: Spanish defaults need review by a Spanish speaker.\nes:" in path.read_text(
        "utf-8"
    )


@pytest.mark.parametrize("target", [language for language in LANGUAGES if language.derive])
def test_profile_defaults_conversion_drift(target) -> None:
    assert target.derive is not None
    # The earlier registry entry is the authored source; the later one is generated.
    if TAGS.index(target.derive.source) > TAGS.index(target.tag):
        target = next(language for language in LANGUAGES if language.tag == target.derive.source)
    defaults = _profile_defaults()
    assert set(defaults[target.tag]) == set(defaults[target.derive.source])
    for field, value in defaults[target.derive.source].items():
        expected = (
            [convert(text, target.derive.source, target.tag) for text in value]
            if isinstance(value, list)
            else convert(value, target.derive.source, target.tag)
        )
        assert defaults[target.tag][field] == expected


@pytest.mark.parametrize("language", LANGUAGES, ids=lambda language: language.tag)
def test_localized_title_limit_is_the_registry_value(language) -> None:
    maximum = title_max(language.tag)
    assert LocalizedTitle.model_validate({language.tag: "x" * maximum}).public() == {
        language.tag: "x" * maximum
    }
    with pytest.raises(ValidationError):
        LocalizedTitle.model_validate({language.tag: "x" * (maximum + 1)})


@pytest.mark.parametrize("site", SITE_SETS)
def test_analysis_and_cache_keep_analysis_locales_independent_of_site(site) -> None:
    schema = _analysis_response_schema(["S1"])["properties"]["inferences"]["items"]["properties"]
    for field in ("title", "statement"):
        assert schema[field]["required"] == list(ANALYSIS_LOCALES)
    assert {tag: field["maxLength"] for tag, field in schema["title"]["properties"].items()} == {
        tag: title_max(tag) for tag in ANALYSIS_LOCALES
    }
    inference = {
        "title": {tag: "x" * title_max(tag) for tag in site},
        "statement": dict.fromkeys(site, "Repository data"),
        "supporting_evidence_ids": ["S1"],
    }
    persistent_id = "E_" + "a" * 24
    assert EVIDENCE_ID_RE.fullmatch(persistent_id)
    cached = {
        **inference,
        "evidence_class": "MODEL_INFERENCE",
        "supporting_evidence_ids": [persistent_id],
    }
    if set(site) == set(ANALYSIS_LOCALES):
        assert _parse_analysis(
            {"inferences": [inference]}, {"S1": persistent_id}, "Repository data"
        )
        assert _valid_cached_inference(cached) == cached
    else:
        with pytest.raises(GuidedOnboardingError) as error:
            _parse_analysis({"inferences": [inference]}, {"S1": persistent_id}, "Repository data")
        assert error.value.reason == "PROVIDER_OUTPUT_SCHEMA_INVALID"
        assert _valid_cached_inference(cached) is None


@pytest.mark.parametrize("language", LANGUAGES, ids=lambda language: language.tag)
def test_localized_values_validate_registry_keys_and_stripped_text(language) -> None:
    assert LocalizedSuggestion.model_validate({language.tag: " Owner text "}).public() == {
        language.tag: "Owner text"
    }
    for value in (
        {" " + language.tag: "text"},
        {"unknown": "text"},
        {language.tag: " "},
        {language.tag: "x" * 2001},
        {language.tag: 42},
        {},
    ):
        with pytest.raises(ValidationError):
            LocalizedSuggestion.model_validate(value)


@pytest.mark.parametrize("site", SITE_SETS)
def test_readme_snippet_service_requires_enabled_language(tmp_path, site, monkeypatch) -> None:
    _, database, _, _ = _service(tmp_path)
    operations = AdminOperations(database, "https://portfolio.example.com")
    rendered = []

    def render(**kwargs):
        rendered.append(kwargs["locale"])
        return "Rendered " + kwargs["locale"]

    monkeypatch.setattr("reponpc.admin.operations.render_readme_snippet", render)
    for tag in site:
        assert (
            operations.readme_snippet(
                locale=tag, theme="light", extension="svg", revision=1, locales=site
            )
            == "Rendered " + tag
        )
    for tag in ("unknown", *(tag for tag in TAGS if tag not in site)):
        with pytest.raises(LocaleNotEnabledError):
            operations.readme_snippet(
                locale=tag, theme="light", extension="svg", revision=1, locales=site
            )
    assert rendered == list(site)


@pytest.mark.parametrize("path", ["compatibility", "resolved"])
def test_analysis_wire_order_stays_legacy_when_provider_keys_are_rotated(tmp_path, path) -> None:
    chat = FakeChat(
        analysis_content={
            "inferences": [
                {
                    "title": dict.fromkeys(reversed(ANALYSIS_LOCALES), "Short title"),
                    "statement": dict.fromkeys(reversed(ANALYSIS_LOCALES), "Repository data"),
                    "supporting_evidence_ids": ["S1"],
                }
            ]
        }
    )
    service, _, resolver, _ = _service(tmp_path, chat=chat)
    if path == "compatibility":
        result = service.analyze_repository(
            session_hash="session-a",
            slug="octocat/demo",
            ref=None,
            include=(),
            exclude=(),
            cancel_requested=threading.Event(),
        )
    else:
        result = service.analyze_resolved_repository(
            snapshot=resolver.resolve(slug="octocat/demo", cancel_requested=lambda: False),
            include=(),
            exclude=(),
            cancel_requested=lambda: False,
        )
    assert chat.calls == 1
    for field in ("title", "statement"):
        assert tuple(result["inferences"][0][field]) == ANALYSIS_LOCALES
