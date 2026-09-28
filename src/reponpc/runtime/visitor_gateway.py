"""Mutable owner-controlled visitor gateway settings."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass

from reponpc.runtime.database import RuntimeDatabase


class VisitorGatewayStoreError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__("visitor gateway settings could not be updated")


@dataclass(frozen=True, slots=True)
class VisitorGatewaySettings:
    revision: int
    enabled: bool
    gateway_origin: str | None
    pages_origin: str | None
    verification_gateway_origin: str | None
    verification_pages_origin: str | None
    verification_bundle_id: str | None
    verified_at: str | None
    verification_method: str | None


class VisitorGatewayStore:
    def __init__(self, database: RuntimeDatabase) -> None:
        self._database = database

    def get(self) -> VisitorGatewaySettings:
        with self._database.connection() as connection:
            row = connection.execute(
                "SELECT * FROM visitor_gateway_settings WHERE id = 1"
            ).fetchone()
        if row is None:
            raise VisitorGatewayStoreError("GATEWAY_UNAVAILABLE")
        return _settings(row)

    def configure(
        self, *, revision: int, gateway_origin: str | None, pages_origin: str | None
    ) -> VisitorGatewaySettings:
        with self._database.connection() as connection:
            try:
                connection.execute("BEGIN IMMEDIATE")
                row = _current(connection, revision)
                if row["enabled"]:
                    raise VisitorGatewayStoreError("GATEWAY_CONFIGURATION_INVALID")
                connection.execute(
                    "UPDATE visitor_gateway_settings SET gateway_origin = ?, pages_origin = ?, "
                    "revision = revision + 1 WHERE id = 1 AND revision = ?",
                    (gateway_origin, pages_origin, revision),
                )
                connection.commit()
            except Exception:
                connection.rollback()
                raise
        return self.get()

    def set_enabled(self, *, revision: int, enabled: bool) -> VisitorGatewaySettings:
        with self._database.connection() as connection:
            try:
                connection.execute("BEGIN IMMEDIATE")
                row = _current(connection, revision)
                if enabled and (row["gateway_origin"] is None or row["pages_origin"] is None):
                    raise VisitorGatewayStoreError("GATEWAY_CONFIGURATION_INVALID")
                if bool(row["enabled"]) != enabled:
                    connection.execute(
                        "UPDATE visitor_gateway_settings SET enabled = ?, revision = revision + 1 "
                        "WHERE id = 1 AND revision = ?",
                        (int(enabled), revision),
                    )
                connection.commit()
            except Exception:
                connection.rollback()
                raise
        return self.get()

    def verify(
        self,
        *,
        revision: int,
        gateway_origin: str,
        pages_origin: str,
        bundle_id: str,
        verified_at: str,
    ) -> VisitorGatewaySettings:
        with self._database.connection() as connection:
            try:
                connection.execute("BEGIN IMMEDIATE")
                row = _current(connection, revision)
                if (
                    not row["enabled"]
                    or row["gateway_origin"] != gateway_origin
                    or row["pages_origin"] != pages_origin
                ):
                    raise VisitorGatewayStoreError("GATEWAY_VERIFICATION_STALE")
                connection.execute(
                    "UPDATE visitor_gateway_settings SET revision = revision + 1, "
                    "verification_gateway_origin = ?, verification_pages_origin = ?, "
                    "verification_bundle_id = ?, verified_at = ?, "
                    "verification_method = 'owner_reported' "
                    "WHERE id = 1 AND revision = ?",
                    (gateway_origin, pages_origin, bundle_id, verified_at, revision),
                )
                connection.commit()
            except Exception:
                connection.rollback()
                raise
        return self.get()


def _current(connection: sqlite3.Connection, revision: int) -> sqlite3.Row:
    row = connection.execute("SELECT * FROM visitor_gateway_settings WHERE id = 1").fetchone()
    if row is None:
        raise VisitorGatewayStoreError("GATEWAY_UNAVAILABLE")
    if row["revision"] != revision:
        raise VisitorGatewayStoreError("GATEWAY_CONFLICT")
    return row


def _settings(row: sqlite3.Row) -> VisitorGatewaySettings:
    return VisitorGatewaySettings(
        revision=int(row["revision"]),
        enabled=bool(row["enabled"]),
        gateway_origin=row["gateway_origin"],
        pages_origin=row["pages_origin"],
        verification_gateway_origin=row["verification_gateway_origin"],
        verification_pages_origin=row["verification_pages_origin"],
        verification_bundle_id=row["verification_bundle_id"],
        verified_at=row["verified_at"],
        verification_method=row["verification_method"],
    )
