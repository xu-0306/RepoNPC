"""Validate provider model-list payloads without retaining upstream data."""

from __future__ import annotations

from typing import Any


def openai_model_available(payload: dict[str, Any], selected_model: str) -> bool:
    """Return whether an OpenAI-compatible model list contains the selected ID."""

    records = payload.get("data")
    if not isinstance(records, list):
        raise ValueError("OpenAI-compatible model catalog is invalid")
    model_ids: set[str] = set()
    for record in records:
        if not isinstance(record, dict) or not isinstance(record.get("id"), str):
            raise ValueError("OpenAI-compatible model catalog is invalid")
        model_ids.add(record["id"])
    return selected_model in model_ids


def ollama_model_available(payload: dict[str, Any], selected_model: str) -> bool:
    """Return whether an Ollama tag list contains the selected model name."""

    model_ids = ollama_model_ids(payload)
    if selected_model in model_ids:
        return True
    return ":" not in selected_model and f"{selected_model}:latest" in model_ids


def ollama_model_ids(payload: dict[str, Any]) -> tuple[str, ...]:
    """Return validated model IDs from an Ollama tag-list response."""

    records = payload.get("models")
    if not isinstance(records, list):
        raise ValueError("Ollama model catalog is invalid")
    model_ids: set[str] = set()
    for record in records:
        if not isinstance(record, dict):
            raise ValueError("Ollama model catalog is invalid")
        values = (record.get("name"), record.get("model"))
        if any(value is not None and not isinstance(value, str) for value in values):
            raise ValueError("Ollama model catalog is invalid")
        if not any(isinstance(value, str) for value in values):
            raise ValueError("Ollama model catalog is invalid")
        model_ids.update(value for value in values if isinstance(value, str))
    return tuple(sorted(model_ids))
