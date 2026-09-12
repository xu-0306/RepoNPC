"""Protected, revisioned model connections for the owner setup flow."""

from __future__ import annotations

import ipaddress
import json
import os
import socket
import sqlite3
import stat
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Final, cast
from urllib.parse import unquote, urlsplit

from cryptography.fernet import Fernet, InvalidToken

from reponpc.runtime.database import RuntimeDatabase

_PROVIDERS: Final = frozenset({"ollama", "openai_compatible", "vllm"})
_MAX_SECRET_BYTES: Final = 64 * 1024


class ModelConnectionError(RuntimeError):
    """Safe model-connection failure identified by a stable code."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__("model connection operation failed")


class ModelSecretStoreError(ModelConnectionError):
    """Protected key material is missing, invalid, or unavailable."""


@dataclass(frozen=True, slots=True)
class ModelConnectionInput:
    """Owner input; api_key is accepted only at the write-only boundary."""

    display_name: str
    provider: str
    base_url: str | None
    api_key: str | None = None
    credential_action: str = "retain"
    endpoint_action: str = "replace"

    def validate(self, *, allow_retain: bool = False) -> None:
        if (
            not isinstance(self.display_name, str)
            or not isinstance(self.provider, str)
            or not self.display_name.strip()
            or len(self.display_name) > 120
            or self.provider not in _PROVIDERS
            or self.credential_action not in {"retain", "replace", "remove"}
            or self.endpoint_action not in {"retain", "replace"}
        ):
            raise ModelConnectionError("VALIDATION_ERROR")
        if self.endpoint_action == "retain":
            if not allow_retain or self.base_url is not None:
                raise ModelConnectionError("VALIDATION_ERROR")
        else:
            validate_provider_base_url(self.base_url, provider=self.provider)
        if self.api_key is not None and (
            not isinstance(self.api_key, str) or len(self.api_key) > 4096
        ):
            raise ModelConnectionError("VALIDATION_ERROR")
        if self.credential_action == "replace" and not self.api_key:
            raise ModelConnectionError("CREDENTIAL_REPLACE_REQUIRED")
        if self.credential_action != "replace" and self.api_key is not None:
            raise ModelConnectionError("VALIDATION_ERROR")


@dataclass(frozen=True, slots=True)
class ModelConnection:
    connection_id: str
    display_name: str
    provider: str
    source: str
    revision: int
    endpoint_configured: bool
    key_configured: bool
    status: str
    created_at: str
    updated_at: str

    def safe_dict(self) -> dict[str, object]:
        return {
            "connection_id": self.connection_id,
            "display_name": self.display_name,
            "provider": self.provider,
            "source": self.source,
            "revision": self.revision,
            "endpoint_configured": self.endpoint_configured,
            "key_configured": self.key_configured,
            "status": self.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


class ModelConnectionSecret:
    """Private decrypted material whose representation never contains values."""

    __slots__ = ("_api_key", "_base_url")

    def __init__(self, base_url: str, api_key: str | None) -> None:
        self._base_url = base_url
        self._api_key = api_key

    @property
    def base_url(self) -> str:
        return self._base_url

    @property
    def api_key(self) -> str | None:
        return self._api_key

    def __repr__(self) -> str:
        return "ModelConnectionSecret(<redacted>)"


class ProtectedModelSecretStore:
    """Fernet-backed store with host-local key material separate from SQLite."""

    def __init__(self, key_path: Path) -> None:
        self._key_path = key_path

    def encrypt(self, secret: ModelConnectionSecret) -> bytes:
        payload = _secret_payload(secret)
        if len(payload) > _MAX_SECRET_BYTES:
            raise ModelSecretStoreError("MODEL_SECRET_STORAGE_UNAVAILABLE")
        try:
            return self._fernet().encrypt(payload)
        except ModelSecretStoreError:
            raise
        except Exception:
            raise ModelSecretStoreError("MODEL_SECRET_STORAGE_UNAVAILABLE") from None

    def decrypt(self, ciphertext: bytes) -> ModelConnectionSecret:
        try:
            # Decryption is recovery-only: an absent master key must never be
            # replaced, because a fresh key can only turn recoverable data loss
            # into an ambiguous permanent failure.
            payload = json.loads(Fernet(self._read_key()).decrypt(ciphertext).decode("utf-8"))
            base_url = payload["base_url"]
            api_key = payload["api_key"]
            if (
                not isinstance(base_url, str)
                or not base_url
                or (api_key is not None and not isinstance(api_key, str))
            ):
                raise ValueError
            return ModelConnectionSecret(base_url, api_key)
        except (InvalidToken, KeyError, TypeError, ValueError, json.JSONDecodeError):
            raise ModelSecretStoreError("MODEL_SECRET_STORAGE_UNAVAILABLE") from None
        except ModelSecretStoreError:
            raise
        except Exception:
            raise ModelSecretStoreError("MODEL_SECRET_STORAGE_UNAVAILABLE") from None

    def current_key(self) -> bytes:
        return self._read_or_create_key()

    def rotate(self) -> bytes:
        value = Fernet.generate_key()
        self.install_key(value)
        return value

    def install_key(self, value: bytes) -> None:
        try:
            Fernet(value)
        except (TypeError, ValueError):
            raise ModelSecretStoreError("MODEL_SECRET_STORAGE_UNAVAILABLE") from None
        self._write_key(value)

    def _write_key(self, value: bytes) -> None:
        temporary = self._key_path.with_name(f".{self._key_path.name}.{uuid.uuid4().hex}.tmp")
        try:
            self._key_path.parent.mkdir(parents=True, exist_ok=True)
            temporary.write_bytes(value)
            _restrict_file(temporary)
            temporary.replace(self._key_path)
        except OSError:
            raise ModelSecretStoreError("MODEL_SECRET_STORAGE_UNAVAILABLE") from None
        finally:
            temporary.unlink(missing_ok=True)

    def _fernet(self) -> Fernet:
        return Fernet(self._read_or_create_key())

    def _read_or_create_key(self) -> bytes:
        try:
            if self._key_path.exists():
                return self._read_key()
            self._key_path.parent.mkdir(parents=True, exist_ok=True)
            value = Fernet.generate_key()
            try:
                with self._key_path.open("xb") as handle:
                    handle.write(value)
                _restrict_file(self._key_path)
            except FileExistsError:
                return self._read_or_create_key()
            return value
        except ModelSecretStoreError:
            raise
        except (OSError, ValueError, TypeError):
            raise ModelSecretStoreError("MODEL_SECRET_STORAGE_UNAVAILABLE") from None

    def _read_key(self) -> bytes:
        try:
            if (
                not self._key_path.exists()
                or self._key_path.is_symlink()
                or not self._key_path.is_file()
            ):
                raise OSError
            _check_file_permissions(self._key_path)
            value = self._key_path.read_bytes()
            Fernet(value)
            return value
        except ModelSecretStoreError:
            raise
        except (OSError, ValueError, TypeError):
            raise ModelSecretStoreError("MODEL_SECRET_STORAGE_UNAVAILABLE") from None


class ModelConnectionRegistry:
    """Persist safe metadata and encrypted endpoint/key revisions."""

    def __init__(self, database: RuntimeDatabase, secret_store: ProtectedModelSecretStore) -> None:
        self._database = database
        self._secret_store = secret_store

    def list(self) -> tuple[ModelConnection, ...]:
        with self._database.connection() as connection:
            rows = connection.execute(
                "SELECT * FROM model_connections ORDER BY created_at, connection_id"
            ).fetchall()
        return tuple(_connection(row) for row in rows)

    def get(self, connection_id: str) -> ModelConnection:
        with self._database.connection() as connection:
            row = connection.execute(
                "SELECT * FROM model_connections WHERE connection_id = ?", (connection_id,)
            ).fetchone()
        if row is None:
            raise ModelConnectionError("NOT_FOUND")
        return _connection(row)

    def create(
        self, values: ModelConnectionInput, *, connection_id: str | None = None
    ) -> ModelConnection:
        values.validate()
        if values.base_url is None:
            raise ModelConnectionError("VALIDATION_ERROR")
        if values.credential_action == "remove":
            raise ModelConnectionError("VALIDATION_ERROR")
        identifier = connection_id or f"conn-{uuid.uuid4().hex[:16]}"
        _validate_connection_id(identifier)
        now = _now()
        secret_ref = f"model-connection:{identifier}:1"
        ciphertext = self._secret_store.encrypt(
            ModelConnectionSecret(values.base_url, values.api_key)
        )
        try:
            with self._database.connection() as connection:
                connection.execute("BEGIN IMMEDIATE")
                connection.execute(
                    """
                    INSERT INTO model_connections(
                      connection_id, display_name, provider, source, revision, secret_ref,
                      endpoint_configured, key_configured, status, created_at, updated_at
                    ) VALUES (?, ?, ?, 'managed', 1, ?, 1, ?, 'configured', ?, ?)
                    """,
                    (
                        identifier,
                        values.display_name.strip(),
                        values.provider,
                        secret_ref,
                        int(bool(values.api_key)),
                        now,
                        now,
                    ),
                )
                connection.execute(
                    """
                    INSERT INTO model_connection_secrets(
                      secret_ref, connection_id, revision, ciphertext, created_at
                    ) VALUES (?, ?, 1, ?, ?)
                    """,
                    (secret_ref, identifier, ciphertext, now),
                )
                connection.execute("COMMIT")
        except ModelConnectionError:
            raise
        except Exception:
            raise ModelConnectionError("MODEL_CONNECTION_SAVE_FAILED") from None
        return self.get(identifier)

    def ensure_host_managed(
        self,
        connection_id: str,
        *,
        display_name: str,
        provider: str,
        base_url: str,
        api_key: str | None,
    ) -> ModelConnection:
        """Mirror explicit deployment settings without exposing or overwriting them."""

        _validate_connection_id(connection_id)
        values = ModelConnectionInput(
            display_name=display_name,
            provider=provider,
            base_url=base_url,
            api_key=api_key,
            credential_action="replace" if api_key is not None else "retain",
        )
        values.validate()
        current: ModelConnection | None = None
        try:
            current = self.get(connection_id)
        except ModelConnectionError as exc:
            if exc.code != "NOT_FOUND":
                raise
        if current is not None:
            if current.source != "host-managed":
                raise ModelConnectionError("MODEL_CONNECTION_ID_CONFLICT")
            try:
                secret = self.secret_for(connection_id)
            except ModelConnectionError:
                raise ModelConnectionError("MODEL_SECRET_STORAGE_UNAVAILABLE") from None
            if (
                current.provider == provider
                and secret.base_url == base_url
                and secret.api_key == api_key
                and current.display_name == display_name
            ):
                return current
            revision = current.revision + 1
        else:
            revision = 1
        secret_ref = f"model-connection:{connection_id}:{revision}"
        ciphertext = self._secret_store.encrypt(ModelConnectionSecret(base_url, api_key))
        now = _now()
        try:
            with self._database.connection() as connection:
                connection.execute("BEGIN IMMEDIATE")
                if current is None:
                    connection.execute(
                        """
                        INSERT INTO model_connections(
                          connection_id, display_name, provider, source, revision, secret_ref,
                          endpoint_configured, key_configured, status, created_at, updated_at
                        ) VALUES (?, ?, ?, 'host-managed', ?, ?, 1, ?, 'configured', ?, ?)
                        """,
                        (
                            connection_id,
                            display_name.strip(),
                            provider,
                            revision,
                            secret_ref,
                            int(bool(api_key)),
                            now,
                            now,
                        ),
                    )
                else:
                    connection.execute(
                        """
                        UPDATE model_connections SET display_name = ?, provider = ?, revision = ?,
                          secret_ref = ?, endpoint_configured = 1, key_configured = ?,
                          status = 'configured', updated_at = ? WHERE connection_id = ?
                        """,
                        (
                            display_name.strip(),
                            provider,
                            revision,
                            secret_ref,
                            int(bool(api_key)),
                            now,
                            connection_id,
                        ),
                    )
                connection.execute(
                    "INSERT INTO model_connection_secrets("
                    "secret_ref, connection_id, revision, ciphertext, created_at) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (secret_ref, connection_id, revision, ciphertext, now),
                )
                connection.execute("COMMIT")
        except ModelConnectionError:
            raise
        except Exception:
            raise ModelConnectionError("MODEL_CONNECTION_SAVE_FAILED") from None
        return self.get(connection_id)

    def update(self, connection_id: str, values: ModelConnectionInput) -> ModelConnection:
        current = self.get(connection_id)
        values.validate(allow_retain=True)
        # Every revision update must prove the existing encrypted lineage is
        # still recoverable.  A replacement credential must not bootstrap a
        # new key beside unreadable historical ciphertext.
        current_secret = self.secret_for(connection_id, current.revision)
        base_url = (
            current_secret.base_url if values.endpoint_action == "retain" else values.base_url
        )
        if base_url is None:
            raise ModelConnectionError("VALIDATION_ERROR")
        if values.credential_action == "retain":
            if values.provider != current.provider:
                raise ModelConnectionError("CREDENTIAL_REPLACE_REQUIRED")
            if base_url != current_secret.base_url:
                raise ModelConnectionError("CREDENTIAL_REPLACE_REQUIRED")
        api_key = (
            values.api_key
            if values.credential_action == "replace"
            else None
            if values.credential_action == "remove"
            else current_secret.api_key
        )
        if (
            values.provider == current.provider
            and base_url == current_secret.base_url
            and api_key == current_secret.api_key
        ):
            # A display-label edit does not change a tested connection identity.
            with self._database.connection() as connection:
                updated = connection.execute(
                    "UPDATE model_connections SET display_name = ?, updated_at = ? "
                    "WHERE connection_id = ? AND revision = ?",
                    (values.display_name.strip(), _now(), connection_id, current.revision),
                )
                if updated.rowcount != 1:
                    raise ModelConnectionError("MODEL_CONNECTION_SAVE_FAILED")
            return self.get(connection_id)
        revision = current.revision + 1
        secret_ref = f"model-connection:{connection_id}:{revision}"
        ciphertext = self._secret_store.encrypt(ModelConnectionSecret(base_url, api_key))
        now = _now()
        try:
            with self._database.connection() as connection:
                connection.execute("BEGIN IMMEDIATE")
                connection.execute(
                    """
                    UPDATE model_connections SET
                      display_name = ?, provider = ?, revision = ?, secret_ref = ?,
                      endpoint_configured = 1, key_configured = ?, status = 'configured',
                      updated_at = ? WHERE connection_id = ?
                    """,
                    (
                        values.display_name.strip(),
                        values.provider,
                        revision,
                        secret_ref,
                        int(bool(api_key)),
                        now,
                        connection_id,
                    ),
                )
                connection.execute(
                    """
                    INSERT INTO model_connection_secrets(
                      secret_ref, connection_id, revision, ciphertext, created_at
                    ) VALUES (?, ?, ?, ?, ?)
                    """,
                    (secret_ref, connection_id, revision, ciphertext, now),
                )
                connection.execute("COMMIT")
        except ModelConnectionError:
            raise
        except Exception:
            raise ModelConnectionError("MODEL_CONNECTION_SAVE_FAILED") from None
        return self.get(connection_id)

    def delete(self, connection_id: str) -> None:
        self.get(connection_id)
        with self._database.connection() as connection:
            try:
                connection.execute("BEGIN IMMEDIATE")
                if (
                    connection.execute(
                        "SELECT 1 FROM chat_profiles WHERE connection_id = ?",
                        (connection_id,),
                    ).fetchone()
                    is not None
                ):
                    raise ModelConnectionError("MODEL_CONNECTION_IN_USE")
                if (
                    connection.execute(
                        "SELECT 1 FROM embedding_profiles WHERE connection_reference = ?",
                        (connection_id,),
                    ).fetchone()
                    is not None
                ):
                    raise ModelConnectionError("MODEL_CONNECTION_IN_USE")
                connection.execute(
                    "DELETE FROM model_connections WHERE connection_id = ?", (connection_id,)
                )
                connection.execute("COMMIT")
            except ModelConnectionError:
                _rollback(connection)
                raise
            except Exception:
                _rollback(connection)
                raise ModelConnectionError("MODEL_CONNECTION_DELETE_FAILED") from None

    def secret_for(self, connection_id: str, revision: int | None = None) -> ModelConnectionSecret:
        current = self.get(connection_id)
        selected_revision = current.revision if revision is None else revision
        with self._database.connection() as connection:
            row = connection.execute(
                """
                SELECT ciphertext FROM model_connection_secrets
                WHERE connection_id = ? AND revision = ?
                """,
                (connection_id, selected_revision),
            ).fetchone()
        if row is None:
            raise ModelConnectionError("MODEL_SECRET_STORAGE_UNAVAILABLE")
        return self._secret_store.decrypt(bytes(row["ciphertext"]))

    def rotate_key(self) -> None:
        material: list[tuple[str, ModelConnectionSecret]] = []
        for model_connection in self.list():
            for revision in range(1, model_connection.revision + 1):
                secret = self.secret_for(model_connection.connection_id, revision)
                material.append(
                    (
                        f"model-connection:{model_connection.connection_id}:{revision}",
                        secret,
                    )
                )
        previous_key = self._secret_store.current_key()
        new_key = self._secret_store.rotate()
        encrypted = [
            (reference, Fernet(new_key).encrypt(_secret_payload(secret)))
            for reference, secret in material
        ]
        try:
            with self._database.connection() as connection:
                try:
                    connection.execute("BEGIN IMMEDIATE")
                    for reference, ciphertext in encrypted:
                        connection.execute(
                            "UPDATE model_connection_secrets SET ciphertext = ? "
                            "WHERE secret_ref = ?",
                            (ciphertext, reference),
                        )
                    connection.execute("COMMIT")
                except Exception:
                    _rollback(connection)
                    raise
        except Exception:
            self._secret_store.install_key(previous_key)
            raise ModelConnectionError("MODEL_SECRET_STORAGE_UNAVAILABLE") from None


def validate_provider_base_url(base_url: str | None, *, provider: str) -> None:
    if (
        provider not in _PROVIDERS
        or not isinstance(base_url, str)
        or len(base_url) > 2048
        or any(char.isspace() or ord(char) < 0x20 for char in base_url)
    ):
        raise ModelConnectionError("VALIDATION_ERROR")
    try:
        parsed = urlsplit(base_url)
        hostname = parsed.hostname
        port = parsed.port
    except ValueError:
        raise ModelConnectionError("INVALID_PROVIDER_URL") from None
    if (
        parsed.scheme not in {"http", "https"}
        or not hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
        or (port is not None and not 1 <= port <= 65535)
        or any(part == ".." for part in unquote(parsed.path).split("/"))
    ):
        raise ModelConnectionError("INVALID_PROVIDER_URL")
    if parsed.scheme == "http" and not _private_provider_name(hostname):
        raise ModelConnectionError("INSECURE_PROVIDER_URL")


def validate_resolved_provider_addresses(
    hostname: str,
    *,
    resolver: Callable[..., list[tuple[object, ...]]] | None = None,
) -> tuple[str, ...]:
    """Reject link-local, multicast, unspecified, and reserved destinations."""

    try:
        resolve = resolver or socket.getaddrinfo
        addresses = {
            str(cast(tuple[object, ...], item[4])[0])
            for item in resolve(hostname, None, type=socket.SOCK_STREAM)
        }
        parsed = tuple(ipaddress.ip_address(address) for address in addresses)
    except (OSError, ValueError, IndexError, TypeError):
        raise ModelConnectionError("PROVIDER_NETWORK_UNAVAILABLE") from None
    if not parsed or any(_forbidden_provider_address(address) for address in parsed):
        raise ModelConnectionError("PROVIDER_NETWORK_BLOCKED")
    return tuple(sorted(address.compressed for address in parsed))


def _private_provider_name(hostname: str) -> bool:
    normalized = hostname.rstrip(".").casefold()
    if (
        normalized in {"localhost", "host.docker.internal"}
        or "." not in normalized
        or normalized.endswith(".local")
    ):
        return True
    try:
        address = ipaddress.ip_address(normalized)
    except ValueError:
        return False
    return address.is_loopback or (address.is_private and not address.is_link_local)


def _validate_connection_id(value: str) -> None:
    if (
        not isinstance(value, str)
        or not value
        or len(value) > 64
        or not value[0].isalnum()
        or any(not (char.isalnum() or char in "_.-") for char in value)
    ):
        raise ModelConnectionError("VALIDATION_ERROR")


def _connection(row: sqlite3.Row) -> ModelConnection:
    return ModelConnection(
        connection_id=str(row["connection_id"]),
        display_name=str(row["display_name"]),
        provider=str(row["provider"]),
        source=str(row["source"]),
        revision=int(row["revision"]),
        endpoint_configured=bool(row["endpoint_configured"]),
        key_configured=bool(row["key_configured"]),
        status=str(row["status"]),
        created_at=str(row["created_at"]),
        updated_at=str(row["updated_at"]),
    )


def _now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _restrict_file(path: Path) -> None:
    if os.name == "posix":
        path.chmod(stat.S_IRUSR | stat.S_IWUSR)


def _check_file_permissions(path: Path) -> None:
    if os.name == "posix" and path.stat().st_mode & (stat.S_IRGRP | stat.S_IROTH):
        raise ModelSecretStoreError("MODEL_SECRET_STORAGE_UNAVAILABLE")


def _rollback(connection: sqlite3.Connection) -> None:
    if connection.in_transaction:
        connection.execute("ROLLBACK")


def _secret_payload(secret: ModelConnectionSecret) -> bytes:
    return json.dumps(
        {"base_url": secret.base_url, "api_key": secret.api_key},
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _forbidden_provider_address(address: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    candidate = (
        address.ipv4_mapped or address if isinstance(address, ipaddress.IPv6Address) else address
    )
    return (
        candidate.is_link_local
        or candidate.is_multicast
        or candidate.is_unspecified
        or candidate.is_reserved
    )
