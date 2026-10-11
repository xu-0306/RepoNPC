"""Version-one password-encrypted runtime backup bytes, without storage side effects."""

from __future__ import annotations

import json
import re
import secrets
import struct
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

MAGIC = b"RepoNPCBackup\x00\x01"
MAX_SQLITE_BYTES = 128 * 1024 * 1024
MAX_METADATA_BYTES = 4096
_SQLITE_HEADER = b"SQLite format 3\x00"
_HEADER_BYTES = len(MAGIC) + 16 + 12
_TAG_BYTES = 16
_ERROR_CODES = frozenset(
    {
        "BACKUP_PASSWORD_INVALID",
        "BACKUP_METADATA_INVALID",
        "BACKUP_SQLITE_INVALID",
        "BACKUP_TOO_LARGE",
        "BACKUP_FORMAT_INVALID",
        "BACKUP_VERSION_UNSUPPORTED",
        "BACKUP_DECRYPT_FAILED",
        "BACKUP_ENCRYPT_FAILED",
    }
)
_TIMESTAMP = re.compile(
    r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(?:\.[0-9]{1,6})?(?:Z|\+00:00)"
)
_VERSION = re.compile(r"[0-9][0-9A-Za-z.+-]{0,63}")


class BackupEncryptionError(ValueError):
    """Closed safe error code; exception text never contains caller or crypto data."""

    def __init__(self, code: str) -> None:
        self.code = code if type(code) is str and code in _ERROR_CODES else "BACKUP_FORMAT_INVALID"
        super().__init__("backup encryption operation failed")


@dataclass(frozen=True, slots=True, repr=False)
class BackupMetadata:
    created_at: str
    schema_version: int
    application_version: str

    def __post_init__(self) -> None:
        if (
            type(self.created_at) is not str
            or len(self.created_at) > 32
            or _TIMESTAMP.fullmatch(self.created_at) is None
            or type(self.schema_version) is not int
            or self.schema_version <= 0
            or type(self.application_version) is not str
            or _VERSION.fullmatch(self.application_version) is None
        ):
            raise BackupEncryptionError("BACKUP_METADATA_INVALID")
        try:
            instant = datetime.fromisoformat(self.created_at)
            if instant.utcoffset() != timedelta(0):
                raise ValueError
        except ValueError:
            raise BackupEncryptionError("BACKUP_METADATA_INVALID") from None

    def __repr__(self) -> str:
        return "BackupMetadata(<redacted>)"


def _password_bytes(password: str) -> bytes:
    if type(password) is not str or not 12 <= len(password) <= 1024:
        raise BackupEncryptionError("BACKUP_PASSWORD_INVALID")
    try:
        encoded = password.encode("utf-8")
    except UnicodeError:
        raise BackupEncryptionError("BACKUP_PASSWORD_INVALID") from None
    if len(encoded) > 4096:
        raise BackupEncryptionError("BACKUP_PASSWORD_INVALID")
    return encoded


def _validate_sqlite(sqlite_bytes: bytes) -> None:
    if type(sqlite_bytes) is not bytes or not sqlite_bytes.startswith(_SQLITE_HEADER):
        raise BackupEncryptionError("BACKUP_SQLITE_INVALID")
    if len(sqlite_bytes) > MAX_SQLITE_BYTES:
        raise BackupEncryptionError("BACKUP_TOO_LARGE")


def _derive_key(password: bytes, salt: bytes) -> bytes:
    return Scrypt(salt=salt, length=32, n=2**17, r=8, p=1).derive(password)


def _metadata_bytes(metadata: BackupMetadata) -> bytes:
    if type(metadata) is not BackupMetadata:
        raise BackupEncryptionError("BACKUP_METADATA_INVALID")
    metadata.__post_init__()
    try:
        encoded = json.dumps(
            {
                "created_at": metadata.created_at,
                "schema_version": metadata.schema_version,
                "application_version": metadata.application_version,
            },
            ensure_ascii=True,
            allow_nan=False,
            separators=(",", ":"),
        ).encode("ascii")
    except (ValueError, OverflowError):
        raise BackupEncryptionError("BACKUP_METADATA_INVALID") from None
    if len(encoded) > MAX_METADATA_BYTES:
        raise BackupEncryptionError("BACKUP_METADATA_INVALID")
    return encoded


def seal(sqlite_bytes: bytes, password: str, metadata: BackupMetadata) -> bytes:
    """Encrypt bounded SQLite bytes with fresh salt/nonce and an authenticated header."""

    password_bytes = _password_bytes(password)
    encoded_metadata = _metadata_bytes(metadata)
    _validate_sqlite(sqlite_bytes)
    salt = secrets.token_bytes(16)
    nonce = secrets.token_bytes(12)
    header = MAGIC + salt + nonce
    plaintext = struct.pack(">I", len(encoded_metadata)) + encoded_metadata + sqlite_bytes
    try:
        key = _derive_key(password_bytes, salt)
        return header + AESGCM(key).encrypt(nonce, plaintext, header)
    except Exception:
        raise BackupEncryptionError("BACKUP_ENCRYPT_FAILED") from None


def _strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError
        result[key] = value
    return result


def _reject_constant(value: str) -> Any:
    raise ValueError


def _decode_plaintext(plaintext: bytes) -> tuple[BackupMetadata, bytes]:
    if len(plaintext) < 4:
        raise BackupEncryptionError("BACKUP_FORMAT_INVALID")
    metadata_size = struct.unpack(">I", plaintext[:4])[0]
    if not 0 < metadata_size <= MAX_METADATA_BYTES or 4 + metadata_size > len(plaintext):
        raise BackupEncryptionError("BACKUP_FORMAT_INVALID")
    try:
        value = json.loads(
            plaintext[4 : 4 + metadata_size].decode("utf-8"),
            object_pairs_hook=_strict_object,
            parse_constant=_reject_constant,
        )
        if type(value) is not dict or set(value) != {
            "created_at",
            "schema_version",
            "application_version",
        }:
            raise ValueError
        metadata = BackupMetadata(**value)
    except (ValueError, TypeError, UnicodeError, RecursionError):
        raise BackupEncryptionError("BACKUP_FORMAT_INVALID") from None
    sqlite_bytes = plaintext[4 + metadata_size :]
    _validate_sqlite(sqlite_bytes)
    return metadata, sqlite_bytes


def unseal(artifact: bytes, password: str) -> tuple[BackupMetadata, bytes]:
    """Authenticate before returning any metadata or database bytes."""

    password_bytes = _password_bytes(password)
    if type(artifact) is not bytes:
        raise BackupEncryptionError("BACKUP_FORMAT_INVALID")
    if len(artifact) > _HEADER_BYTES + _TAG_BYTES + 4 + MAX_METADATA_BYTES + MAX_SQLITE_BYTES:
        raise BackupEncryptionError("BACKUP_TOO_LARGE")
    if len(artifact) < _HEADER_BYTES + _TAG_BYTES + 4 + len(_SQLITE_HEADER):
        raise BackupEncryptionError("BACKUP_FORMAT_INVALID")
    if not artifact.startswith(MAGIC):
        code = (
            "BACKUP_VERSION_UNSUPPORTED"
            if artifact.startswith(MAGIC[:-1])
            else "BACKUP_FORMAT_INVALID"
        )
        raise BackupEncryptionError(code)
    header = artifact[:_HEADER_BYTES]
    salt = header[len(MAGIC) : len(MAGIC) + 16]
    nonce = header[-12:]
    try:
        key = _derive_key(password_bytes, salt)
        plaintext = AESGCM(key).decrypt(nonce, artifact[_HEADER_BYTES:], header)
    except Exception:
        raise BackupEncryptionError("BACKUP_DECRYPT_FAILED") from None
    return _decode_plaintext(plaintext)
