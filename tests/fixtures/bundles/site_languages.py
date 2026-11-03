"""Registry-derived localized configuration for data-plane contract tests."""

from pathlib import Path
from typing import Any

import yaml

from reponpc.i18n.languages import language_tags

FIXTURE_CONFIG = Path(__file__).parents[1] / "phase2" / "reponpc.yml"


def site_data(tags: tuple[str, ...], *, default: str | None = None) -> dict[str, Any]:
    registry = set(language_tags())

    def localize(value: Any) -> Any:
        if isinstance(value, dict):
            if value and set(value) <= registry:
                original = next(iter(value.values()))
                return {tag: value.get(tag, original) for tag in tags}
            return {key: localize(item) for key, item in value.items()}
        if isinstance(value, list):
            return [localize(item) for item in value]
        return value

    data = localize(yaml.safe_load(FIXTURE_CONFIG.read_text(encoding="utf-8")))
    data["locales"] = {"default": default or tags[0], "supported": list(tags)}
    data["profile"]["links"] = [
        {"label": {tag: "GitHub" for tag in tags}, "url": "https://github.com/fixture-owner"}
    ]
    for repository in data["repositories"]:
        repository["summary"] = {
            tag: f"{tag}: {text}" for tag, text in repository["summary"].items()
        }
    return data
