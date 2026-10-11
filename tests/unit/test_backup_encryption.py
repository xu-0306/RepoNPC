"""Real cryptography checks for the bounded, side-effect-free backup format."""

from __future__ import annotations

import secrets
import struct
from dataclasses import FrozenInstanceError
from typing import Any

import pytest
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from reponpc.admin import backup_encryption as crypto

PASSWORD = "example-backup-password-漢字"
SQLITE = b"SQLite format 3\x00" + bytes(range(256))
METADATA = crypto.BackupMetadata("2026-10-03T05:06:07.123456+00:00", 32, "0.4.6-dev+example")


@pytest.fixture(scope="module")
def artifact() -> bytes:
    return crypto.seal(SQLITE, PASSWORD, METADATA)


@pytest.fixture(scope="module")
def forge() -> Any:
    salt = b"example-salt-123"
    key = crypto._derive_key(PASSWORD.encode(), salt)

    def encrypt(plaintext: bytes) -> bytes:
        nonce = secrets.token_bytes(12)
        header = crypto.MAGIC + salt + nonce
        return header + AESGCM(key).encrypt(nonce, plaintext, header)

    return encrypt


def assert_error(code: str, operation: Any, *args: Any) -> crypto.BackupEncryptionError:
    with pytest.raises(crypto.BackupEncryptionError) as captured:
        operation(*args)
    assert captured.value.code == code
    assert str(captured.value) == "backup encryption operation failed"
    assert PASSWORD not in repr(captured.value)
    assert captured.value.__cause__ is None
    return captured.value


def test_real_round_trip_exact_bytes_and_metadata(artifact: bytes) -> None:
    assert artifact.startswith(crypto.MAGIC)
    assert SQLITE not in artifact and METADATA.created_at.encode() not in artifact
    assert crypto.unseal(artifact, PASSWORD) == (METADATA, SQLITE)


def test_fresh_salt_nonce_ciphertext_for_same_input(artifact: bytes) -> None:
    other = crypto.seal(SQLITE, PASSWORD, METADATA)
    magic_size = len(crypto.MAGIC)
    assert other[magic_size : magic_size + 16] != artifact[magic_size : magic_size + 16]
    assert other[magic_size + 16 : magic_size + 28] != artifact[magic_size + 16 : magic_size + 28]
    assert other != artifact
    assert crypto.unseal(other, PASSWORD) == (METADATA, SQLITE)


def test_wrong_password_has_same_safe_error_as_tamper(artifact: bytes) -> None:
    assert_error("BACKUP_DECRYPT_FAILED", crypto.unseal, artifact, "different-example-password")


@pytest.mark.parametrize("position", [len(crypto.MAGIC), len(crypto.MAGIC) + 16, -17, -1])
def test_salt_nonce_ciphertext_and_tag_authenticated(artifact: bytes, position: int) -> None:
    changed = bytearray(artifact)
    changed[position] ^= 1
    assert_error("BACKUP_DECRYPT_FAILED", crypto.unseal, bytes(changed), PASSWORD)


@pytest.mark.parametrize("size", [0, 1, 13, 14, 41, 77])
def test_short_artifact_rejected_before_kdf(
    artifact: bytes, size: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(crypto, "_derive_key", forbidden_kdf)
    assert_error("BACKUP_FORMAT_INVALID", crypto.unseal, artifact[:size], PASSWORD)


def test_ciphertext_truncation_and_append_fail_authentication(artifact: bytes) -> None:
    for invalid in (artifact[:-1], artifact + b"trailing-data"):
        assert_error("BACKUP_DECRYPT_FAILED", crypto.unseal, invalid, PASSWORD)


def forbidden_kdf(*args: Any, **kwargs: Any) -> Any:
    pytest.fail("invalid or oversized inputs must be rejected before KDF")


@pytest.mark.parametrize(
    "prefix,code",
    [
        (b"Other", "BACKUP_FORMAT_INVALID"),
        (crypto.MAGIC[:-1] + b"\x02", "BACKUP_VERSION_UNSUPPORTED"),
    ],
)
def test_bad_magic_version_before_kdf(
    artifact: bytes, prefix: bytes, code: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(crypto, "_derive_key", forbidden_kdf)
    assert_error(code, crypto.unseal, prefix + artifact[len(prefix) :], PASSWORD)


@pytest.mark.parametrize(
    "password", ["", "x" * 11, "x" * 1025, "\ud800" * 12, None, b"example-password"]
)
def test_bad_password_rejected_before_kdf(
    artifact: bytes, password: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(crypto, "_derive_key", forbidden_kdf)
    assert_error("BACKUP_PASSWORD_INVALID", crypto.seal, SQLITE, password, METADATA)
    assert_error("BACKUP_PASSWORD_INVALID", crypto.unseal, artifact, password)


@pytest.mark.parametrize("password", ["x" * 12, "🧪" * 1024], ids=["min-ascii", "max-unicode"])
def test_password_boundaries_unicode_not_trimmed(password: str) -> None:
    result = crypto.seal(SQLITE, password, METADATA)
    assert crypto.unseal(result, password) == (METADATA, SQLITE)
    assert_error("BACKUP_DECRYPT_FAILED", crypto.unseal, result, password[:-1] + " ")


@pytest.mark.parametrize(
    "created",
    [
        "2026-10-03",
        "2026-10-03T05:06:07",
        "2026-10-03T05:06:07+01:00",
        "2026-02-30T05:06:07Z",
        "2026-10-03T25:06:07Z",
        "2026-10-03T05:06:07.1234567Z",
        None,
    ],
)
def test_invalid_metadata_timestamp(created: Any) -> None:
    assert_error("BACKUP_METADATA_INVALID", crypto.BackupMetadata, created, 32, "0.4.6")


@pytest.mark.parametrize("schema", [True, False, 0, -1, 1.0, "32", None])
def test_positive_strict_schema_version(schema: Any) -> None:
    assert_error(
        "BACKUP_METADATA_INVALID", crypto.BackupMetadata, METADATA.created_at, schema, "0.4.6"
    )


@pytest.mark.parametrize(
    "version", ["", "x" * 65, "0.4.6 中文", "0.4.6/path", "0.4.6\n", "v0.4.6", 1, None]
)
def test_bounded_ascii_version(version: Any) -> None:
    assert_error("BACKUP_METADATA_INVALID", crypto.BackupMetadata, METADATA.created_at, 32, version)


def test_metadata_is_frozen_and_repr_redacted() -> None:
    metadata = crypto.BackupMetadata("2026-10-03T05:06:07Z", 1, "1")
    assert metadata.created_at.endswith("Z")
    assert repr(metadata) == "BackupMetadata(<redacted>)"
    with pytest.raises(FrozenInstanceError):
        metadata.schema_version = 3  # type: ignore[misc]


def test_wrong_metadata_type_and_bypassed_frozen_validation_before_kdf(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(crypto, "_derive_key", forbidden_kdf)
    assert_error("BACKUP_METADATA_INVALID", crypto.seal, SQLITE, PASSWORD, {})
    invalid = crypto.BackupMetadata(METADATA.created_at, 32, "0.4.6")
    object.__setattr__(invalid, "schema_version", True)
    assert_error("BACKUP_METADATA_INVALID", crypto.seal, SQLITE, PASSWORD, invalid)


@pytest.mark.parametrize(
    "sqlite", [b"", b"not-sqlite", b"SQLite format 3", bytearray(SQLITE), None]
)
def test_sqlite_header_and_bytes_type_before_kdf(
    sqlite: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(crypto, "_derive_key", forbidden_kdf)
    assert_error("BACKUP_SQLITE_INVALID", crypto.seal, sqlite, PASSWORD, METADATA)


def test_sqlite_size_limit_and_boundary(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(crypto, "MAX_SQLITE_BYTES", len(SQLITE))
    artifact = crypto.seal(SQLITE, PASSWORD, METADATA)
    assert crypto.unseal(artifact, PASSWORD) == (METADATA, SQLITE)
    monkeypatch.setattr(crypto, "_derive_key", forbidden_kdf)
    assert_error("BACKUP_TOO_LARGE", crypto.seal, SQLITE + b"x", PASSWORD, METADATA)


def test_metadata_size_rejected_before_kdf(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(crypto, "MAX_METADATA_BYTES", 1)
    monkeypatch.setattr(crypto, "_derive_key", forbidden_kdf)
    assert_error("BACKUP_METADATA_INVALID", crypto.seal, SQLITE, PASSWORD, METADATA)


def test_authenticated_sqlite_size_limit(forge: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(crypto, "MAX_SQLITE_BYTES", len(SQLITE) - 1)
    metadata = crypto._metadata_bytes(METADATA)
    artifact = forge(struct.pack(">I", len(metadata)) + metadata + SQLITE)
    assert_error("BACKUP_TOO_LARGE", crypto.unseal, artifact, PASSWORD)


def test_authenticated_metadata_maximum_boundary(forge: Any) -> None:
    metadata = crypto._metadata_bytes(METADATA).ljust(crypto.MAX_METADATA_BYTES, b" ")
    artifact = forge(struct.pack(">I", len(metadata)) + metadata + SQLITE)
    assert crypto.unseal(artifact, PASSWORD) == (METADATA, SQLITE)


def test_artifact_limit_before_kdf(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(crypto, "MAX_SQLITE_BYTES", 16)
    monkeypatch.setattr(crypto, "_derive_key", forbidden_kdf)
    maximum = len(crypto.MAGIC) + 28 + 16 + 4 + 4096 + 16
    assert_error("BACKUP_TOO_LARGE", crypto.unseal, crypto.MAGIC + b"x" * maximum, PASSWORD)


@pytest.mark.parametrize("value", [bytearray(b"x" * 100), "x" * 100, None])
def test_artifact_strict_bytes(value: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(crypto, "_derive_key", forbidden_kdf)
    assert_error("BACKUP_FORMAT_INVALID", crypto.unseal, value, PASSWORD)


@pytest.mark.parametrize(
    "metadata",
    [
        b"{",
        b"{}",
        b"[]",
        b"\xff",
        b'{"created_at":"2026-10-03T05:06:07Z","schema_version":32,"schema_version":33,"application_version":"0.4.6"}',
        b'{"created_at":"2026-10-03T05:06:07Z","schema_version":NaN,"application_version":"0.4.6"}',
        b'{"created_at":"2026-10-03T05:06:07Z","schema_version":Infinity,"application_version":"0.4.6"}',
        b'{"created_at":"2026-10-03T05:06:07Z","schema_version":true,"application_version":"0.4.6"}',
        b'{"created_at":"2026-10-03T05:06:07Z","schema_version":32,"application_version":"0.4.6","extra":"untrusted"}',
    ],
)
def test_authenticated_malformed_metadata_rejected(forge: Any, metadata: bytes) -> None:
    artifact = forge(struct.pack(">I", len(metadata)) + metadata + SQLITE)
    assert_error("BACKUP_FORMAT_INVALID", crypto.unseal, artifact, PASSWORD)


@pytest.mark.parametrize(
    "plaintext",
    [
        b"x",
        struct.pack(">I", 0) + SQLITE,
        struct.pack(">I", 4097) + b" " * 4097 + SQLITE,
        struct.pack(">I", 4096) + b"short" + SQLITE,
    ],
)
def test_authenticated_metadata_length_rejected(forge: Any, plaintext: bytes) -> None:
    assert_error("BACKUP_FORMAT_INVALID", crypto.unseal, forge(plaintext), PASSWORD)


def test_authenticated_bad_sqlite_rejected(forge: Any) -> None:
    metadata = crypto._metadata_bytes(METADATA)
    artifact = forge(struct.pack(">I", len(metadata)) + metadata + b"invalid-sqlite")
    assert_error("BACKUP_SQLITE_INVALID", crypto.unseal, artifact, PASSWORD)


def test_fixed_scrypt_parameters_use_real_implementation(monkeypatch: pytest.MonkeyPatch) -> None:
    real_scrypt = crypto.Scrypt
    observed: list[dict[str, Any]] = []

    def scrypt(**kwargs: Any) -> Any:
        observed.append(kwargs)
        return real_scrypt(**kwargs)

    monkeypatch.setattr(crypto, "Scrypt", scrypt)
    artifact = crypto.seal(SQLITE, PASSWORD, METADATA)
    assert crypto.unseal(artifact, PASSWORD) == (METADATA, SQLITE)
    assert len(observed) == 2
    for kwargs in observed:
        assert {key: value for key, value in kwargs.items() if key != "salt"} == {
            "length": 32,
            "n": 2**17,
            "r": 8,
            "p": 1,
        }
        assert len(kwargs["salt"]) == 16


def test_crypto_failures_and_arbitrary_error_code_never_leak(
    artifact: bytes, monkeypatch: pytest.MonkeyPatch, capsys: Any
) -> None:
    def broken(*args: Any) -> bytes:
        raise RuntimeError(PASSWORD + " example-private-path sqlite-body")

    monkeypatch.setattr(crypto, "_derive_key", broken)
    assert_error("BACKUP_ENCRYPT_FAILED", crypto.seal, SQLITE, PASSWORD, METADATA)
    assert_error("BACKUP_DECRYPT_FAILED", crypto.unseal, artifact, PASSWORD)
    exception = crypto.BackupEncryptionError(PASSWORD)
    assert exception.code == "BACKUP_FORMAT_INVALID" and PASSWORD not in repr(exception)
    assert not capsys.readouterr().out
