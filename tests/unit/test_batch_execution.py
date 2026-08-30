from __future__ import annotations

import hashlib

from reponpc.admin.batch_execution import PinnedBatchItemRunner
from reponpc.admin.batch_resolver import BatchCapacity, CredentialPurpose, PublicReadCredential
from reponpc.admin.batch_runtime import BatchCreateRequest, BatchItemInput, BatchRuntimeStore
from reponpc.admin.batches import BatchStageGates
from reponpc.runtime.database import RuntimeDatabase


class Source:
    def __init__(self) -> None:
        self.calls = 0

    def fetch(self, **_values: object) -> object:
        self.calls += 1
        return object()


class Onboarding:
    def __init__(self) -> None:
        self.calls = 0

    def analyze_resolved_repository(self, **values: object) -> dict[str, object]:
        self.calls += 1
        stage_changed = values["stage_changed"]
        assert callable(stage_changed)
        stage_changed("filtering")
        stage_changed("indexing")
        stage_changed("embedding")
        stage_changed("generating")
        stage_changed("validating")
        return {
            "repository": {"slug": "octocat/demo", "commit_sha": "a" * 40},
            "facts": [{"excerpt": "untrusted repository source must not persist"}],
            "inferences": [{"statement": {"zh-TW": "摘要", "en": "Summary"}}],
            "skipped_summary": {"count": 0, "reasons": []},
        }


def _request(key: str) -> BatchCreateRequest:
    return BatchCreateRequest(
        plan_id=f"plan-{key}",
        selection_hash=hashlib.sha256(b"selection").hexdigest(),
        idempotency_key=key,
        selected_credential_id=1,
        items=(
            BatchItemInput(
                slug="octocat/demo",
                ref="main",
                include=("src/**",),
                exclude=(),
                commit_sha="a" * 40,
            ),
        ),
    )


def test_validated_result_cache_is_commit_complete_and_excludes_source_excerpt(tmp_path) -> None:
    database = RuntimeDatabase(tmp_path / "runtime")
    database.initialize()
    store = BatchRuntimeStore(database)
    source = Source()
    onboarding = Onboarding()
    runner = PinnedBatchItemRunner(
        store=store,
        source=source,  # type: ignore[arg-type]
        onboarding=onboarding,  # type: ignore[arg-type]
        credentials_supplier=lambda: (
            PublicReadCredential(
                credential_id=1,
                purpose=CredentialPurpose.IDENTITY_PUBLIC_READ,
                status="ready",
                token="cache-test-token",
            ),
        ),
        gates=BatchStageGates(BatchCapacity(1, 1, 2, 1, 4)),
        parser_identity="parser-a",
        embedding_identity="embedding-a",
        chat_model="chat-a",
        prompt_version="prompt-a",
        output_schema_version="schema-a",
        validation_version="validation-a",
    )

    first, _ = store.create_batch(_request("key-one"))
    claimed = store.claim_next_item(first.batch_id)
    assert claimed is not None
    result = runner(claimed, lambda: False)
    store.complete_item(claimed, result=result)

    second, _ = store.create_batch(_request("key-two"))
    cached = store.claim_next_item(second.batch_id)
    assert cached is not None
    cached_result = runner(cached, lambda: False)

    assert source.calls == onboarding.calls == 1
    assert cached_result["facts"] == []
    raw_cache = database.connection()
    with raw_cache as connection:
        serialized = connection.execute(
            "SELECT payload_json FROM analysis_cache_entries "
            "WHERE cache_kind = 'validated_analysis'"
        ).fetchone()[0]
    assert "untrusted repository source" not in serialized
    assert "cache-test-token" not in serialized
