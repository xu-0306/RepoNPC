"""Revisioned chat profiles backed by explicitly tested model connections."""

from __future__ import annotations

import json
import re
import sqlite3
import uuid
from collections.abc import Callable
from contextlib import suppress
from dataclasses import dataclass, field
from datetime import UTC, datetime

from reponpc.admin.model_connections import ModelConnectionRegistry
from reponpc.admin.model_probe_errors import provider_probe_error_code
from reponpc.providers.contracts import (
    ChatProvider,
    ProviderError,
    ProviderMessage,
    ProviderResult,
)
from reponpc.providers.response_diagnostics import ProviderResponseError, ResponseIssue
from reponpc.runtime.database import RuntimeDatabase, RuntimeDatabaseError

_PROFILE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")
_MODEL_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:/-]{0,255}$")


class ChatProfileError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__("chat profile operation failed")


@dataclass(frozen=True, slots=True)
class ChatProfileInput:
    connection_id: str
    model_id: str

    def validate(self) -> None:
        if (
            not isinstance(self.connection_id, str)
            or not _PROFILE_ID.fullmatch(self.connection_id)
            or not isinstance(self.model_id, str)
            or not _MODEL_ID.fullmatch(self.model_id)
        ):
            raise ChatProfileError("VALIDATION_ERROR")


@dataclass(frozen=True, slots=True)
class ChatProfile:
    profile_id: str
    connection_id: str
    connection_revision: int
    model_id: str
    status: str
    active: bool
    observed_model_id: str | None
    last_error_code: str | None
    created_at: str
    updated_at: str
    last_probed_at: str | None
    last_error_message: str | None = field(default=None, repr=False)

    def safe_dict(self) -> dict[str, object]:
        return {
            "profile_id": self.profile_id,
            "connection_id": self.connection_id,
            "connection_revision": self.connection_revision,
            "model_id": self.model_id,
            "status": self.status,
            "active": self.active,
            "observed_model_id": self.observed_model_id,
            "last_error_code": self.last_error_code,
            "last_error_message": self.last_error_message,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "last_probed_at": self.last_probed_at,
        }


class ChatProfileRegistry:
    """Persist candidates and make only explicitly tested profiles active."""

    def __init__(
        self,
        database: RuntimeDatabase,
        connections: ModelConnectionRegistry,
        provider_resolver: Callable[[ChatProfile], ChatProvider | None],
        *,
        now: Callable[[], datetime] | None = None,
        on_activated: (
            Callable[[ChatProfile, ChatProvider], Callable[[], None] | None] | None
        ) = None,
    ) -> None:
        self._database = database
        self._connections = connections
        self._provider_resolver = provider_resolver
        self._now = now or (lambda: datetime.now(UTC))
        self._on_activated = on_activated

    def list(self) -> tuple[ChatProfile, ...]:
        with self._database.connection() as connection:
            rows = connection.execute(
                "SELECT * FROM chat_profiles ORDER BY active DESC, created_at, profile_id"
            ).fetchall()
        return tuple(_profile(row) for row in rows)

    def get(self, profile_id: str) -> ChatProfile:
        if not _PROFILE_ID.fullmatch(profile_id):
            raise ChatProfileError("VALIDATION_ERROR")
        with self._database.connection() as connection:
            row = connection.execute(
                "SELECT * FROM chat_profiles WHERE profile_id = ?", (profile_id,)
            ).fetchone()
        if row is None:
            raise ChatProfileError("NOT_FOUND")
        return _profile(row)

    def active(self) -> ChatProfile | None:
        with self._database.connection() as connection:
            row = connection.execute("SELECT * FROM chat_profiles WHERE active = 1").fetchone()
        return _profile(row) if row is not None else None

    def resolve_provider(self, profile: ChatProfile) -> ChatProvider | None:
        return self._provider_resolver(profile)

    def create(self, values: ChatProfileInput) -> ChatProfile:
        values.validate()
        connection = self._connections.get(values.connection_id)
        profile_id = f"chat-{uuid.uuid4().hex[:16]}"
        now = _time(self._now())
        try:
            with self._database.connection() as database_connection:
                database_connection.execute(
                    """
                    INSERT INTO chat_profiles(
                      profile_id, connection_id, connection_revision, model_id,
                      status, active, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, 'probe', 0, ?, ?)
                    """,
                    (
                        profile_id,
                        connection.connection_id,
                        connection.revision,
                        values.model_id,
                        now,
                        now,
                    ),
                )
        except sqlite3.Error as exc:
            raise RuntimeDatabaseError("runtime_chat_profile_failed") from exc
        return self.get(profile_id)

    def update(self, profile_id: str, values: ChatProfileInput) -> ChatProfile:
        values.validate()
        current = self.get(profile_id)
        if current.active:
            raise ChatProfileError("CHAT_PROFILE_ACTIVE_IMMUTABLE")
        connection = self._connections.get(values.connection_id)
        now = _time(self._now())
        with self._database.connection() as database_connection:
            database_connection.execute(
                """
                UPDATE chat_profiles SET connection_id = ?, connection_revision = ?,
                  model_id = ?, status = 'probe', observed_model_id = NULL,
                  last_error_code = NULL, last_error_message = NULL,
                  updated_at = ?, last_probed_at = NULL
                WHERE profile_id = ?
                """,
                (connection.connection_id, connection.revision, values.model_id, now, profile_id),
            )
        return self.get(profile_id)

    def delete(self, profile_id: str) -> None:
        current = self.get(profile_id)
        if current.active:
            raise ChatProfileError("CHAT_PROFILE_ACTIVE_IMMUTABLE")
        with self._database.connection() as connection:
            connection.execute("DELETE FROM chat_profiles WHERE profile_id = ?", (profile_id,))

    def probe(self, profile_id: str) -> ChatProfile:
        profile = self.get(profile_id)
        error_code: str | None = None
        error_message: str | None = None
        try:
            provider = self._provider_resolver(profile)
            if provider is None:
                raise ChatProfileError("CHAT_CONNECTION_REQUIRED")
            result = provider.generate(
                (ProviderMessage("user", 'Reply only with JSON: {"ok":true}.'),),
                {
                    "type": "object",
                    "properties": {"ok": {"type": "boolean"}},
                    "required": ["ok"],
                    "additionalProperties": False,
                },
                max_output_tokens=provider.capabilities().max_output_tokens,
                timeout=10.0,
            )
            if result.finish_reason == "length":
                raise ProviderResponseError(ResponseIssue.OUTPUT_LIMIT)
            payload = _result_object(result)
            if payload.get("ok") is not True:
                raise ChatProfileError("CHAT_PROBE_INVALID_RESPONSE")
        except ChatProfileError as exc:
            error_code = exc.code
        except ProviderError as exc:
            error_code = provider_probe_error_code(exc)
            error_message = (
                exc.diagnostic_message
                if isinstance(exc, ProviderResponseError)
                else exc.upstream_message
            )
        except Exception:
            error_code = "CHAT_PROBE_FAILED"
        now = _time(self._now())
        status = (
            "last_known_good"
            if error_code and profile.active
            else "probe_failed"
            if error_code
            else "ready"
        )
        with self._database.connection() as connection:
            connection.execute(
                """
                UPDATE chat_profiles SET status = ?, observed_model_id = ?,
                  last_error_code = ?, last_error_message = ?, updated_at = ?, last_probed_at = ?
                WHERE profile_id = ?
                """,
                (
                    status,
                    profile.model_id if error_code is None else None,
                    error_code,
                    error_message,
                    now,
                    now,
                    profile_id,
                ),
            )
        return self.get(profile_id)

    def activate(self, profile_id: str) -> ChatProfile:
        profile = self.get(profile_id)
        if profile.status != "ready" or profile.last_probed_at is None:
            raise ChatProfileError("CHAT_PROBE_REQUIRED")
        current_connection = self._connections.get(profile.connection_id)
        if current_connection.revision != profile.connection_revision:
            raise ChatProfileError("CHAT_PROFILE_STALE")
        provider = self._provider_resolver(profile)
        if provider is None:
            raise ChatProfileError("CHAT_CONNECTION_REQUIRED")
        previous = self.active()
        previous_provider = self._provider_resolver(previous) if previous is not None else None
        now = _time(self._now())
        runtime_switched = False
        undo_runtime_switch: Callable[[], None] | None = None

        def restore_previous_runtime() -> None:
            if undo_runtime_switch is not None:
                with suppress(Exception):
                    undo_runtime_switch()
                return
            if self._on_activated is None or previous is None or previous_provider is None:
                return
            with suppress(Exception):
                self._on_activated(previous, previous_provider)

        try:
            with self._database.connection() as connection:
                connection.execute("BEGIN IMMEDIATE")
                connection.execute(
                    "UPDATE chat_profiles SET active = 0, status = CASE "
                    "WHEN active = 1 THEN 'last_known_good' ELSE status END, "
                    "updated_at = ? WHERE active = 1",
                    (now,),
                )
                connection.execute(
                    "UPDATE chat_profiles SET active = 1, status = 'ready', "
                    "updated_at = ? WHERE profile_id = ?",
                    (now, profile_id),
                )
                if self._on_activated is not None:
                    try:
                        undo_runtime_switch = self._on_activated(profile, provider)
                        runtime_switched = True
                    except Exception:
                        connection.execute("ROLLBACK")
                        restore_previous_runtime()
                        raise ChatProfileError("CHAT_RUNTIME_SWITCH_FAILED") from None
                connection.execute("COMMIT")
        except ChatProfileError:
            raise
        except sqlite3.Error as exc:
            if runtime_switched:
                restore_previous_runtime()
            raise RuntimeDatabaseError("runtime_chat_profile_failed") from exc
        return self.get(profile_id)


def _profile(row: sqlite3.Row) -> ChatProfile:
    return ChatProfile(
        profile_id=str(row["profile_id"]),
        connection_id=str(row["connection_id"]),
        connection_revision=int(row["connection_revision"]),
        model_id=str(row["model_id"]),
        status=str(row["status"]),
        active=bool(row["active"]),
        observed_model_id=str(row["observed_model_id"]) if row["observed_model_id"] else None,
        last_error_code=str(row["last_error_code"]) if row["last_error_code"] else None,
        last_error_message=row["last_error_message"]
        if "last_error_message" in row.keys()  # noqa: SIM118 - sqlite3.Row iterates values.
        else None,
        created_at=str(row["created_at"]),
        updated_at=str(row["updated_at"]),
        last_probed_at=str(row["last_probed_at"]) if row["last_probed_at"] else None,
    )


def _result_object(result: ProviderResult) -> dict[str, object]:
    payload: object = result.content
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except json.JSONDecodeError:
            raise ChatProfileError("CHAT_PROBE_INVALID_RESPONSE") from None
    if not isinstance(payload, dict):
        raise ChatProfileError("CHAT_PROBE_INVALID_RESPONSE")
    return payload


def _time(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")
