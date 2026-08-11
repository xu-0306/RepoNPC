"""Falsify the public profile locale-selection contract through the real route."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from fastapi.testclient import TestClient

from reponpc.api.public import SetupState
from reponpc.main import create_app


with tempfile.TemporaryDirectory() as temporary_directory:
    public_directory = Path(temporary_directory)
    (public_directory / "profile.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "locale": "zh-TW",
                "profile": {"headline": "zh only"},
            }
        ),
        encoding="utf-8",
    )
    application = create_app(
        setup_state=SetupState(
            index_ready=True,
            index_version="probe",
            model_ready=False,
            public_directory=public_directory,
        )
    )
    with TestClient(application) as client:
        zh_tw = client.get("/api/public/profile?locale=zh-TW")
        english = client.get("/api/public/profile?locale=en")

    observation = {
        "zh_status": zh_tw.status_code,
        "en_status": english.status_code,
        "same_payload": zh_tw.json() == english.json(),
        "zh_locale": zh_tw.json().get("locale"),
        "en_locale": english.json().get("locale"),
        "en_headline": english.json().get("profile", {}).get("headline"),
    }
    print(json.dumps(observation, ensure_ascii=False, sort_keys=True))
    if english.status_code != 200 or english.json().get("locale") != "en":
        raise SystemExit(1)
