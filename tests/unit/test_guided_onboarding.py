"""Focused invariants for owner-approved guided onboarding."""

from __future__ import annotations

import re
import threading
from pathlib import Path

import numpy as np
import pytest

from reponpc.admin.onboarding import (
    ContributionProposal,
    GuidedOnboardingError,
    GuidedOnboardingService,
    GuidedProfileDraft,
    GuidedRepositoryDraft,
    _analysis_config,
)
from reponpc.chat.limits import ChatLimits
from reponpc.indexing.exclusions import SourceEntryKind
from reponpc.indexing.github import (
    GitHubSourceResolver,
    PublicRepositoryMetadata,
    RepositoryDiscoveryPage,
    SourceResolutionError,
    normalize_github_account,
    normalize_github_repository,
)
from reponpc.indexing.sources import EmbeddingIdentity, RepositoryBlob, ResolvedRepository
from reponpc.providers.contracts import (
    ProviderCapabilities,
    ProviderError,
    ProviderFailureCode,
    ProviderHealth,
    ProviderResult,
)
from reponpc.providers.runtime import ProviderRuntime
from reponpc.runtime.database import RuntimeDatabase

SHA = "a" * 40


class FakeResolver:
    def __init__(self) -> None:
        self.source_calls = 0

    def discover(self, *, account: str, page: int) -> RepositoryDiscoveryPage:
        assert account == "octocat"
        return RepositoryDiscoveryPage((_metadata(),), page, False)

    def repository_metadata(self, *, repository: str) -> PublicRepositoryMetadata:
        assert normalize_github_repository(repository) == "octocat/demo"
        return _metadata()

    def resolve(self, **values: object) -> ResolvedRepository:
        self.source_calls += 1
        assert values["slug"] == "octocat/demo"
        cancel = values["cancel_requested"]
        assert callable(cancel) and not cancel()
        return ResolvedRepository(
            slug="octocat/demo",
            commit_sha=SHA,
            default_branch="main",
            github_html_url="https://github.com/octocat/demo",
            blobs=(
                RepositoryBlob(
                    path="README.md",
                    entry_kind=SourceEntryKind.REGULAR_FILE,
                    size_bytes=len(b"# Demo\nA safe architecture overview.\n"),
                    content=b"# Demo\nA safe architecture overview.\n",
                ),
                RepositoryBlob(
                    path=".env",
                    entry_kind=SourceEntryKind.REGULAR_FILE,
                    size_bytes=len(b"TOKEN=secret"),
                    content=b"TOKEN=secret",
                ),
                RepositoryBlob(
                    path="docs/link",
                    entry_kind=SourceEntryKind.SYMLINK,
                    size_bytes=4,
                ),
            ),
        )


class FakeEmbedding:
    def identity(self) -> EmbeddingIdentity:
        return EmbeddingIdentity("ollama", "fixture", 3, True, "query: ", "passage: ")

    def embed_query(self, texts: list[str]) -> np.ndarray:
        return np.tile(np.asarray([[1.0, 0.0, 0.0]], dtype=np.float32), (len(texts), 1))

    def embed_passages(self, texts: list[str]) -> np.ndarray:
        return np.tile(np.asarray([[1.0, 0.0, 0.0]], dtype=np.float32), (len(texts), 1))

    def health(self) -> ProviderHealth:
        return ProviderHealth(True, "2026-08-14T00:00:00Z")


class TransientFailingEmbedding(FakeEmbedding):
    def __init__(self) -> None:
        self.query_calls = 0

    def embed_query(self, texts: list[str]) -> np.ndarray:
        del texts
        self.query_calls += 1
        raise ProviderError(ProviderFailureCode.UNAVAILABLE)


class FakeChat:
    def __init__(self, *, failure: ProviderError | None = None) -> None:
        self.failure = failure
        self.calls = 0

    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(False, True, True, True, True, 8192, 1000)

    def generate(self, messages, response_schema, max_output_tokens, timeout):
        del response_schema, max_output_tokens
        self.calls += 1
        assert 0 < timeout <= 45
        if self.failure is not None:
            raise self.failure
        if "UNTRUSTED OWNER DRAFT" in messages[-1].content:
            content = {
                "role": {"zh-TW": "共同維護者", "en": "Co-maintainer"},
                "summary": {"zh-TW": "維護公開模組", "en": "Maintained public modules"},
                "claims": [
                    {
                        "id": "demo_context",
                        "kind": "context",
                        "statement": {
                            "zh-TW": "依照原始說明整理",
                            "en": "Structured from the original statement",
                        },
                    }
                ],
            }
        else:
            evidence_ids = re.findall(r"persistent_id=(E_[0-9a-f]+)", messages[-1].content)
            assert evidence_ids
            content = {
                "inferences": [
                    {
                        "statement": {
                            "zh-TW": "此儲存庫包含架構說明",
                            "en": "The repository contains an architecture overview",
                        },
                        "supporting_evidence_ids": [evidence_ids[0]],
                    }
                ]
            }
        return ProviderResult(content, "stop", None, None, 1.0)

    def health(self) -> ProviderHealth:
        return ProviderHealth(True, "2026-08-14T00:00:00Z")


def _metadata() -> PublicRepositoryMetadata:
    return PublicRepositoryMetadata(
        slug="octocat/demo",
        name="demo",
        description="Public demo",
        primary_language="Python",
        default_branch="main",
        is_fork=False,
        is_archived=False,
        updated_at="2026-08-14T00:00:00Z",
        html_url="https://github.com/octocat/demo",
    )


def _service(
    tmp_path: Path,
    *,
    chat: FakeChat | None = None,
    embedding: FakeEmbedding | None = None,
) -> tuple[GuidedOnboardingService, RuntimeDatabase, FakeResolver, FakeChat]:
    database = RuntimeDatabase(tmp_path / "runtime")
    database.initialize()
    limits = ChatLimits(
        database,
        ip_hash_key=b"fixture-guided-key",
        requests_per_minute=1,
        daily_budget=1,
        global_concurrency=1,
    )
    resolver = FakeResolver()
    selected_chat = chat or FakeChat()
    selected_embedding = embedding or FakeEmbedding()
    providers = ProviderRuntime(chat=selected_chat, embedding=selected_embedding)  # type: ignore[arg-type]
    service = GuidedOnboardingService(
        source_resolver=resolver,  # type: ignore[arg-type]
        providers_supplier=lambda: providers,
        limits_supplier=lambda: limits,
        staging_root=tmp_path / "staging",
        provider_timeout_seconds=45,
    )
    return service, database, resolver, selected_chat


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("octocat", "octocat"),
        ("https://github.com/octocat", "octocat"),
    ],
)
def test_github_account_normalization_accepts_only_exact_github_identity(
    value: str, expected: str
) -> None:
    assert normalize_github_account(value) == expected


@pytest.mark.parametrize(
    "value",
    [
        "https://evil.example/octocat",
        "https://github.com/octocat/demo",
        "https://github.com/octocat?tab=repositories",
        "https://github.com:invalid/octocat",
        "http://github.com/octocat",
    ],
)
def test_github_account_normalization_rejects_hostile_or_nonprofile_values(value: str) -> None:
    with pytest.raises(SourceResolutionError):
        normalize_github_account(value)


def test_github_repository_normalization_rejects_malformed_port() -> None:
    with pytest.raises(SourceResolutionError):
        normalize_github_repository("https://github.com:invalid/octocat/demo")


def test_discovery_and_resolution_are_metadata_only(tmp_path: Path) -> None:
    service, _database, resolver, chat = _service(tmp_path)

    discovered = service.discover_repositories(account="octocat", page=1)
    resolved = service.resolve_repository(repository="https://github.com/octocat/demo", ref="main")

    assert discovered["repositories"][0]["slug"] == "octocat/demo"  # type: ignore[index]
    assert resolved["slug"] == "octocat/demo"
    assert resolver.source_calls == 0
    assert chat.calls == 0


def test_public_discovery_uses_fixed_page_bounds_and_filters_private_rows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    requested: list[str] = []

    def payload(_resolver: GitHubSourceResolver, path: str) -> list[dict[str, object]]:
        requested.append(path)
        return [
            {
                "full_name": f"octocat/demo-{index}",
                "name": f"demo-{index}",
                "description": "Public demo",
                "language": "Python",
                "default_branch": "main",
                "fork": False,
                "archived": False,
                "private": index == 49,
                "updated_at": "2026-08-14T00:00:00Z",
                "html_url": f"https://github.com/octocat/demo-{index}",
            }
            for index in range(50)
        ]

    monkeypatch.setattr(GitHubSourceResolver, "_get_json_list", payload)
    resolver = GitHubSourceResolver()

    result = resolver.discover(account="https://github.com/octocat", page=5)

    assert len(result.repositories) == 49
    assert result.has_more is False
    assert requested == [
        "/users/octocat/repos?type=public&sort=updated&direction=desc&per_page=50&page=5"
    ]
    with pytest.raises(SourceResolutionError):
        resolver.discover(account="octocat", page=6)


def test_analysis_reuses_exclusions_returns_distinct_evidence_and_cleans_staging(
    tmp_path: Path,
) -> None:
    service, database, resolver, chat = _service(tmp_path)

    result = service.analyze_repository(
        session_hash="session-a",
        slug="octocat/demo",
        ref=None,
        include=(),
        exclude=(),
        cancel_requested=threading.Event(),
    )

    assert resolver.source_calls == 1
    assert chat.calls == 1
    assert result["repository"]["commit_sha"] == SHA  # type: ignore[index]
    assert result["facts"]
    assert all(item["evidence_class"] == "REPOSITORY_FACT" for item in result["facts"])  # type: ignore[union-attr]
    assert all(item["path"] != ".env" for item in result["facts"])  # type: ignore[union-attr]
    assert result["inferences"][0]["evidence_class"] == "MODEL_INFERENCE"  # type: ignore[index]
    assert not any((tmp_path / "staging").iterdir())
    with database.connection() as connection:
        assert connection.execute("SELECT COUNT(*) FROM daily_usage").fetchone()[0] == 0


def test_analysis_calls_configured_provider_once_and_releases_session_on_failure(
    tmp_path: Path,
) -> None:
    chat = FakeChat(failure=ProviderError(ProviderFailureCode.UNAVAILABLE))
    service, _database, _resolver, _chat = _service(tmp_path, chat=chat)

    with pytest.raises(GuidedOnboardingError) as error:
        service.analyze_repository(
            session_hash="session-a",
            slug="octocat/demo",
            ref=None,
            include=(),
            exclude=(),
            cancel_requested=threading.Event(),
        )

    assert error.value.code == "MODEL_UNAVAILABLE"
    assert chat.calls == 1
    with service._session_operation("session-a"):
        pass


def test_analysis_never_retries_transient_query_embedding_failure(tmp_path: Path) -> None:
    embedding = TransientFailingEmbedding()
    service, _database, _resolver, chat = _service(tmp_path, embedding=embedding)

    with pytest.raises(GuidedOnboardingError) as error:
        service.analyze_repository(
            session_hash="session-a",
            slug="octocat/demo",
            ref=None,
            include=(),
            exclude=(),
            cancel_requested=threading.Event(),
        )

    assert error.value.code == "MODEL_UNAVAILABLE"
    assert embedding.query_calls == 1
    assert chat.calls == 0
    assert not any((tmp_path / "staging").iterdir())


def test_analysis_cancellation_before_source_access_cleans_staging(tmp_path: Path) -> None:
    service, _database, resolver, chat = _service(tmp_path)
    cancelled = threading.Event()
    cancelled.set()

    with pytest.raises(GuidedOnboardingError) as error:
        service.analyze_repository(
            session_hash="session-a",
            slug="octocat/demo",
            ref=None,
            include=(),
            exclude=(),
            cancel_requested=cancelled,
        )

    assert error.value.code == "CANCELLED"
    assert resolver.source_calls == 0
    assert chat.calls == 0
    assert not any((tmp_path / "staging").iterdir())


def test_same_session_operation_is_fail_closed(tmp_path: Path) -> None:
    service, _database, _resolver, _chat = _service(tmp_path)

    with (
        service._session_operation("session-a"),
        pytest.raises(GuidedOnboardingError) as error,
        service._session_operation("session-a"),
    ):
        pass

    assert error.value.code == "CONCURRENCY_LIMIT"


def test_suggestion_preserves_original_and_remains_unconfirmed(tmp_path: Path) -> None:
    service, _database, _resolver, _chat = _service(tmp_path)
    original = "I maintained the parser with another contributor."

    result = service.suggest_contributions(
        session_hash="session-a",
        slug="octocat/demo",
        owner_statement=original,
    )

    assert result["original_statement"] == original
    assert result["confirmed"] is False
    assert ContributionProposal.model_validate(result["proposal"])


def test_draft_requires_confirmation_and_round_trips_schema_v1(tmp_path: Path) -> None:
    service, _database, _resolver, _chat = _service(tmp_path)
    providers, _limits = service._provider_dependencies()
    config, _content = _analysis_config(
        slug="octocat/demo",
        ref=None,
        include=(),
        exclude=(),
        identity=providers.embedding.identity(),
    )
    profile = GuidedProfileDraft.model_validate(
        {
            "display_name": "Example Developer",
            "headline": {"zh-TW": "可靠系統", "en": "Reliable systems"},
            "bio": {"zh-TW": "開發者工具", "en": "Developer tooling"},
            "greeting": {"zh-TW": "你好", "en": "Hello"},
        }
    )
    repository = GuidedRepositoryDraft.model_validate(
        {
            "slug": "octocat/demo",
            "role": {"zh-TW": "共同維護者", "en": "Co-maintainer"},
            "summary": {"zh-TW": "維護解析器", "en": "Maintained the parser"},
        }
    )

    with pytest.raises(GuidedOnboardingError):
        service.create_draft(
            profile=profile,
            repositories=(repository,),
            base_config=config,
            confirmed_assertions=False,
        )

    draft = service.create_draft(
        profile=profile,
        repositories=(repository,),
        base_config=config,
        confirmed_assertions=True,
    )
    assert draft["content"].startswith("schema_version: 1")
    assert draft["validation"]["valid"] is True  # type: ignore[index]


def test_draft_without_provider_or_github_uses_safe_documented_defaults(
    tmp_path: Path,
) -> None:
    resolver = FakeResolver()
    service = GuidedOnboardingService(
        source_resolver=resolver,  # type: ignore[arg-type]
        providers_supplier=lambda: None,
        limits_supplier=lambda: None,
        staging_root=tmp_path / "staging",
        provider_timeout_seconds=45,
    )
    profile = GuidedProfileDraft.model_validate(
        {
            "display_name": "Example Developer",
            "headline": {"zh-TW": "可靠系統", "en": "Reliable systems"},
            "bio": {"zh-TW": "開發者工具", "en": "Developer tooling"},
            "greeting": {"zh-TW": "你好", "en": "Hello"},
        }
    )
    repository = GuidedRepositoryDraft.model_validate(
        {
            "slug": "octocat/demo",
            "role": {"zh-TW": "共同維護者", "en": "Co-maintainer"},
            "summary": {"zh-TW": "維護解析器", "en": "Maintained the parser"},
        }
    )

    draft = service.create_draft(
        profile=profile,
        repositories=(repository,),
        base_config=None,
        confirmed_assertions=True,
    )

    assert draft["validation"]["valid"] is True  # type: ignore[index]
    assert "intfloat/multilingual-e5-small" in str(draft["content"])
    assert resolver.source_calls == 0
