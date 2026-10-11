"""Responses selection uses the existing authenticated, CSRF-protected form."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from tests.integration.test_model_connections_api import (
    CANARY_KEY,
    CANARY_URL,
    ORIGIN,
    _application,
    _body,
    _login,
)


def test_interface_selection_is_explicit_protected_and_revisioned(tmp_path: Path) -> None:
    with TestClient(_application(tmp_path), base_url=ORIGIN) as client:
        csrf = _login(client)
        headers = {"Origin": ORIGIN, "X-CSRF-Token": csrf}
        body = {**_body(), "chat_api": "responses"}
        denied = client.post("/api/admin/model-connections", headers={"Origin": ORIGIN}, json=body)
        assert denied.status_code == 403
        created = client.post("/api/admin/model-connections", headers=headers, json=body)
        assert created.status_code == 201 and created.json()["chat_api"] == "responses"
        assert CANARY_KEY not in created.text and CANARY_URL not in created.text
        identifier = created.json()["connection_id"]
        retained = client.put(
            f"/api/admin/model-connections/{identifier}",
            headers=headers,
            json={
                "display_name": "Renamed",
                "provider": "openai_compatible",
                "endpoint_action": "retain",
                "credential_action": "retain",
            },
        )
        assert retained.status_code == 200 and retained.json()["revision"] == 1
        assert retained.json()["chat_api"] == "responses"
        changed = client.put(
            f"/api/admin/model-connections/{identifier}",
            headers=headers,
            json={
                "display_name": "Legacy",
                "provider": "openai_compatible",
                "endpoint_action": "retain",
                "credential_action": "retain",
                "chat_api": "chat_completions",
            },
        )
        assert changed.status_code == 200 and changed.json()["revision"] == 2
        assert changed.json()["chat_api"] == "chat_completions"


@pytest.mark.parametrize(
    "interface,provider", [("unknown", "openai_compatible"), ("responses", "ollama")]
)
def test_invalid_interface_selection_fails_without_saving(
    tmp_path: Path, interface: str, provider: str
) -> None:
    with TestClient(_application(tmp_path), base_url=ORIGIN) as client:
        csrf = _login(client)
        response = client.post(
            "/api/admin/model-connections",
            headers={"Origin": ORIGIN, "X-CSRF-Token": csrf},
            json={**_body(), "chat_api": interface, "provider": provider},
        )
        assert response.status_code in {400, 422}
        assert CANARY_KEY not in response.text and CANARY_URL not in response.text
        assert client.get("/api/admin/model-connections", headers={"Origin": ORIGIN}).json() == {
            "connections": []
        }
