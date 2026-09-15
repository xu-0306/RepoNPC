"""Analysis output policy reaches each production wire format without public drift."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from reponpc.admin.onboarding import AnalysisEnvelope
from reponpc.config.environment import load_environment
from reponpc.main import _analysis_chat_capabilities, _chat_provider_from_connection
from reponpc.providers.contracts import ProviderMessage
from reponpc.providers.http_transport import ProviderHttpResponse, UrllibProviderHttpTransport


@pytest.mark.parametrize("provider_name", ["ollama", "openai_compatible", "vllm"])
@pytest.mark.parametrize("budget", [None, "16384"])
def test_analysis_and_public_budgets_reach_production_transport(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, provider_name: str, budget: str | None
) -> None:
    environment = {
        "REPONPC_DATA_DIR": str(tmp_path),
        "REPONPC_PUBLIC_BASE_URL": "https://portfolio.example.com",
        "REPONPC_CONFIG_REPOSITORY": "example/portfolio",
        "REPONPC_INDEX_MANIFEST_URL": (
            "https://raw.githubusercontent.com/example/portfolio/main/stable-manifest.json"
        ),
        "REPONPC_CHAT_PROVIDER": provider_name,
        "REPONPC_CHAT_MODEL": "fixture-chat",
        "REPONPC_CHAT_BASE_URL": "https://model.example.com/v1",
        "REPONPC_EMBEDDING_MODEL": "fixture-embed",
        "REPONPC_EMBEDDING_BASE_URL": "http://127.0.0.1:11434",
    }
    if budget is not None:
        environment["REPONPC_ANALYSIS_MAX_OUTPUT_TOKENS"] = budget
    settings = load_environment(environment, secret_roots=(tmp_path,))
    requests: list[dict[str, Any]] = []

    def fake_request(
        _transport: UrllibProviderHttpTransport,
        method: str,
        url: str,
        **kwargs: Any,
    ) -> ProviderHttpResponse:
        assert method == "POST"
        requests.append(json.loads(kwargs["body"]))
        message = {"content": '{"inferences":[]}'}
        if provider_name == "ollama":
            assert url.endswith("/api/chat")
            response = {"message": message, "done_reason": "stop"}
        else:
            assert url.endswith("/chat/completions")
            response = {"choices": [{"message": message, "finish_reason": "stop"}]}
        return ProviderHttpResponse(200, {}, json.dumps(response).encode())

    monkeypatch.setattr(UrllibProviderHttpTransport, "request", fake_request)
    for capabilities, output_tokens in (
        (_analysis_chat_capabilities(settings), settings.analysis_max_output_tokens),
        (None, settings.chat_max_output_tokens),
    ):
        provider = _chat_provider_from_connection(
            settings,
            provider_name,
            settings.chat_model,
            settings.chat_base_url,
            None,
            capabilities=capabilities,
        )
        provider.generate(
            (ProviderMessage("user", "Return the repository analysis as JSON."),),
            AnalysisEnvelope.model_json_schema(),
            output_tokens,
            45,
        )

    assert len(requests) == 2
    limits = [
        request["options"]["num_predict"] if provider_name == "ollama" else request["max_tokens"]
        for request in requests
    ]
    assert limits == [8192 if budget is None else 16384, 4096]
