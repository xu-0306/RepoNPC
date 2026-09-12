"""Real adapter -> profile persistence checks, with synthetic HTTP responses."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path

import pytest

from reponpc.admin.chat_profiles import ChatProfileInput, ChatProfileRegistry
from reponpc.admin.model_connections import (
    ModelConnectionInput,
    ModelConnectionRegistry,
    ProtectedModelSecretStore,
)
from reponpc.providers.contracts import ProviderCapabilities
from reponpc.providers.http_transport import ProviderHttpResponse
from reponpc.providers.ollama import OllamaChatProvider
from reponpc.providers.openai_compatible import OpenAICompatibleChatProvider
from reponpc.providers.response_diagnostics import ResponseIssue
from reponpc.runtime.database import RuntimeDatabase

CANARY = "SYNTHETIC_PRIVATE_RESPONSE_DO_NOT_REFLECT"


class ResponseTransport:
    def __init__(self, failure: str, adapter: str) -> None:
        self.failure = failure
        self.adapter = adapter
        self.budgets: list[int] = []

    def request(
        self,
        method: str,
        url: str,
        *,
        headers: Mapping[str, str],
        body: bytes | None,
        timeout: float,
    ) -> ProviderHttpResponse:
        assert method == "POST"
        assert timeout == 10.0
        assert body is not None
        request = json.loads(body)
        budget = request.get("max_tokens", request.get("options", {}).get("num_predict"))
        self.budgets.append(budget)
        failure = self.failure
        if failure == "budget":
            # This synthetic model needs more than 32 tokens before answering.
            failure = "length" if budget < 64 else "success"
        if failure == "json":
            return ProviderHttpResponse(200, {}, CANARY.encode())
        content = None if failure in {"length", "content"} else '{"ok":true}'
        finish = "length" if failure in {"length", "partial_length"} else "stop"
        message: object = {"content": content, "reasoning_content": CANARY}
        if failure == "message":
            message = CANARY
        if failure == "finish":
            finish = ""
        if self.adapter == "openai_compatible":
            payload: dict[str, object] = {
                "choices": [{"message": message, "finish_reason": finish}],
            }
            if failure == "choices":
                payload["choices"] = []
            if failure == "usage":
                payload["usage"] = {"prompt_tokens": CANARY, "completion_tokens": 3}
            if failure == "id":
                payload["id"] = {"private": CANARY}
        else:
            payload = {"message": message, "done_reason": finish}
            if failure == "usage":
                payload["prompt_eval_count"] = CANARY
                payload["eval_count"] = 3
        payload["private_metadata"] = CANARY
        return ProviderHttpResponse(200, {}, json.dumps(payload).encode())


def registry(
    tmp_path: Path, adapter: str, transport: ResponseTransport, limit: int = 1000
) -> tuple[ChatProfileRegistry, str]:
    database = RuntimeDatabase(tmp_path / "runtime")
    database.initialize()
    connections = ModelConnectionRegistry(
        database, ProtectedModelSecretStore(tmp_path / "secrets" / "model.key")
    )
    connection = connections.create(
        ModelConnectionInput("Synthetic service", adapter, "https://fixture.example.test", None)
    )
    capabilities = ProviderCapabilities(False, True, True, True, True, 8192, limit)
    cls = OpenAICompatibleChatProvider if adapter == "openai_compatible" else OllamaChatProvider
    provider = cls(
        "https://fixture.example.test", "arbitrary/model", capabilities, transport=transport
    )
    profiles = ChatProfileRegistry(database, connections, lambda _: provider)
    profile = profiles.create(ChatProfileInput(connection.connection_id, "arbitrary/model"))
    return profiles, profile.profile_id


@pytest.mark.parametrize("adapter", ["openai_compatible", "ollama"])
@pytest.mark.parametrize(
    "failure,issue",
    [
        ("json", ResponseIssue.JSON),
        ("message", ResponseIssue.MESSAGE),
        ("content", ResponseIssue.CONTENT),
        ("length", ResponseIssue.OUTPUT_LIMIT),
        ("partial_length", ResponseIssue.OUTPUT_LIMIT),
        ("finish", ResponseIssue.FINISH_REASON),
        ("usage", ResponseIssue.USAGE),
    ],
)
def test_parse_failure_is_specific_persisted_and_cleared_without_raw_body(
    tmp_path: Path, adapter: str, failure: str, issue: ResponseIssue
) -> None:
    transport = ResponseTransport(failure, adapter)
    profiles, profile_id = registry(tmp_path, adapter, transport)
    failed = profiles.probe(profile_id)
    assert failed.status == "probe_failed"
    assert failed.last_error_code == "PROVIDER_INVALID_RESPONSE"
    assert failed.last_error_message == f"RepoNPC response check: {issue.value}"
    assert profiles.get(profile_id).last_error_message == failed.last_error_message
    assert CANARY not in json.dumps(failed.safe_dict())
    transport.failure = "success"
    passed = profiles.probe(profile_id)
    assert passed.status == "ready"
    assert passed.last_error_code is None
    assert passed.last_error_message is None
    assert not passed.active
    assert len(transport.budgets) == 2


@pytest.mark.parametrize("adapter", ["openai_compatible", "ollama"])
@pytest.mark.parametrize("limit", [16, 128, 1000])
def test_probe_uses_configured_budget_without_retry_or_exceeding_it(
    tmp_path: Path, adapter: str, limit: int
) -> None:
    transport = ResponseTransport("budget", adapter)
    profiles, profile_id = registry(tmp_path, adapter, transport, limit)
    result = profiles.probe(profile_id)
    assert transport.budgets == [limit]
    assert result.status == ("ready" if limit >= 64 else "probe_failed")
    assert not result.active


@pytest.mark.parametrize(
    "failure,issue", [("choices", ResponseIssue.CHOICES), ("id", ResponseIssue.REQUEST_ID)]
)
def test_openai_envelope_checks(tmp_path: Path, failure: str, issue: ResponseIssue) -> None:
    transport = ResponseTransport(failure, "openai_compatible")
    profiles, profile_id = registry(tmp_path, "openai_compatible", transport)
    result = profiles.probe(profile_id)
    assert result.last_error_message == f"RepoNPC response check: {issue.value}"
    assert CANARY not in json.dumps(result.safe_dict())
