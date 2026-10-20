"""Maintenance HTTP boundaries using real authentication, SQLite, crypto and lifespans."""

from __future__ import annotations

import asyncio
import json
import os
import re
import sqlite3
from contextlib import closing
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from importlib.metadata import version
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from reponpc.admin import maintenance as maintenance_module
from reponpc.admin.auth import SESSION_COOKIE, AdminSessionService, issue_admin_setup_code
from reponpc.admin.backup_encryption import BackupMetadata, seal, unseal
from reponpc.admin.maintenance import MaintenanceService
from reponpc.admin.maintenance_host import MaintenanceHost
from reponpc.admin.operations import AdminOperations
from reponpc.api import admin as admin_api
from reponpc.main import create_app
from reponpc.runtime.database import RuntimeDatabase

ORIGIN = "https://maintenance.example.test"
OWNER_PASSWORD = "fixture owner password not real"
BACKUP_PASSWORD = "fixture backup password 漢字"
BASE = "/api/admin/maintenance"


def create_owner(database: RuntimeDatabase) -> AdminSessionService:
    auth = AdminSessionService(database=database, identity_hmac_key=b"m" * 32)
    auth.setup_owner(
        setup_code=issue_admin_setup_code(database),
        username="owner",
        password=OWNER_PASSWORD,
        password_confirmation=OWNER_PASSWORD,
    )
    return auth


@pytest.fixture(scope="module")
def encrypted_backup(tmp_path_factory: pytest.TempPathFactory) -> bytes:
    directory = tmp_path_factory.mktemp("maintenance-source")
    database = RuntimeDatabase(directory / "data")
    database.initialize()
    create_owner(database)
    destination = directory / "snapshot.sqlite"
    database.backup_to(destination)
    metadata = BackupMetadata(
        datetime.now(UTC).isoformat(), database.schema_version(), version("reponpc")
    )
    return seal(destination.read_bytes(), BACKUP_PASSWORD, metadata)


@dataclass
class Harness:
    database: RuntimeDatabase
    host: MaintenanceHost
    client: TestClient
    headers: dict[str, str]

    @property
    def service(self) -> MaintenanceService:
        return self.host.current.state.maintenance_service


def login(client: TestClient) -> dict[str, str]:
    result = client.post(
        "/api/admin/session",
        headers={"Origin": ORIGIN},
        json={"username": "owner", "password": OWNER_PASSWORD},
    )
    assert result.status_code == 200, result.text
    return {"Origin": ORIGIN, "X-CSRF-Token": result.json()["csrf_token"]}


@pytest.fixture
def harness(tmp_path: Path):
    database = RuntimeDatabase(tmp_path / "data")
    database.initialize()
    create_owner(database)

    def application() -> FastAPI:
        auth = AdminSessionService(database=database, identity_hmac_key=b"m" * 32)
        app = create_app(
            runtime_database=database,
            admin_session_service=auth,
            admin_origins=(ORIGIN,),
            admin_operations=AdminOperations(database=database, public_base_url=ORIGIN),
            web_dist=tmp_path / "absent-web",
        )
        app.state.deployment_profile = "production"
        app.state.maintenance_service = MaintenanceService(
            database,
            resource_check=lambda path: None,
            application_factory=application,
            idle_check=lambda: None,
        )
        return app

    host = MaintenanceHost(application(), restart_old=application)
    with TestClient(host, base_url=ORIGIN) as client:
        yield Harness(database, host, client, login(client))


def inspect_backup(
    harness: Harness,
    artifact: bytes,
    *,
    password: str = BACKUP_PASSWORD,
    filename: str = "fixture.reponpc-backup",
    headers: dict[str, str] | None = None,
) -> httpx.Response:
    return harness.client.post(
        BASE + "/restore/inspect",
        headers=headers or harness.headers,
        files={"backup": (filename, artifact, "application/octet-stream")},
        data={"password": password},
    )


def preview(harness: Harness, artifact: bytes) -> dict[str, Any]:
    result = inspect_backup(harness, artifact)
    assert result.status_code == 200, result.text
    return result.json()


def assert_safe(result: httpx.Response, harness: Harness) -> None:
    assert result.headers["cache-control"] == "no-store"
    assert OWNER_PASSWORD not in result.text and BACKUP_PASSWORD not in result.text
    assert str(harness.database.database_path) not in result.text
    assert "SQLite format 3" not in result.text and "$argon2id$" not in result.text


def receive_chunks(
    harness: Harness,
    path: str,
    chunks: list[bytes],
    *,
    headers: list[tuple[str, str]] | None = None,
    omit: frozenset[str] = frozenset(),
) -> tuple[httpx.Response, int]:
    """Drive actual ASGI receive boundaries; HTTPX TestClient otherwise joins generator chunks."""
    changes = headers or []
    overridden = {key.casefold() for key, _value in changes} | omit
    standard = [
        ("host", "maintenance.example.test"),
        ("origin", ORIGIN),
        ("cookie", f"{SESSION_COOKIE}={harness.client.cookies.get(SESSION_COOKIE)}"),
        ("x-csrf-token", harness.headers["X-CSRF-Token"]),
        ("content-type", "application/json"),
        ("content-length", str(sum(map(len, chunks)))),
    ]
    raw_headers = [
        (key.encode("ascii"), value.encode("latin1"))
        for key, value in [*(item for item in standard if item[0] not in overridden), *changes]
    ]

    async def scenario() -> tuple[httpx.Response, int]:
        consumed = 0
        messages: list[Any] = []
        scope: dict[str, Any] = {
            "type": "http",
            "http_version": "1.1",
            "asgi": {"version": "3.0"},
            "scheme": "https",
            "method": "POST",
            "path": BASE + path,
            "raw_path": (BASE + path).encode(),
            "root_path": "",
            "query_string": b"",
            "headers": raw_headers,
            "client": ("127.0.0.1", 54321),
            "server": ("maintenance.example.test", 443),
            "state": {},
        }

        async def receive() -> dict[str, Any]:
            nonlocal consumed
            assert consumed < len(chunks), "body reader must stop at the declared end"
            chunk = chunks[consumed]
            consumed += 1
            return {"type": "http.request", "body": chunk, "more_body": consumed < len(chunks)}

        async def send(message: Any) -> None:
            messages.append(message)

        await harness.host(scope, receive, send)
        start = next(message for message in messages if message["type"] == "http.response.start")
        content = b"".join(
            message.get("body", b"")
            for message in messages
            if message["type"] == "http.response.body"
        )
        return httpx.Response(start["status"], headers=start["headers"], content=content), consumed

    assert harness.client.portal is not None
    return harness.client.portal.call(scenario)


@pytest.mark.parametrize("path", ["/backup", "/restore", "/pin"])
@pytest.mark.parametrize("boundary", ["session", "csrf", "origin"])
def test_small_json_preauth_rejects_without_consuming_untrusted_body(
    harness: Harness,
    path: str,
    boundary: str,
) -> None:
    headers = {
        "session": [("cookie", "")],
        "csrf": [("x-csrf-token", "wrong-fixture-csrf")],
        "origin": [("origin", "https://attacker.example")],
    }[boundary]
    result, consumed = receive_chunks(
        harness,
        path,
        [BACKUP_PASSWORD.encode() * 1000],
        headers=headers,
    )
    assert result.status_code == (401 if boundary == "session" else 403)
    assert consumed == 0
    assert_safe(result, harness)
    assert harness.host._maintenance is None
    assert not (harness.database.database_path.parent / "private" / "maintenance").exists()


@pytest.mark.parametrize("path", ["/backup", "/restore", "/pin"])
@pytest.mark.parametrize("kind", ["missing", "oversized", "duplicate", "transfer"])
def test_small_json_rejects_bad_transport_headers_before_body(
    harness: Harness,
    path: str,
    kind: str,
) -> None:
    choices = {
        "missing": [],
        "oversized": [("content-length", "8193")],
        "duplicate": [("content-length", "2"), ("content-length", "2")],
        "transfer": [("transfer-encoding", "chunked")],
    }
    result, consumed = receive_chunks(
        harness,
        path,
        [b"{}"],
        headers=choices[kind],
        omit=frozenset({"content-length"}) if kind == "missing" else frozenset(),
    )
    assert result.status_code == 413 and result.json()["error"]["code"] == "BACKUP_TOO_LARGE"
    assert consumed == 0
    assert_safe(result, harness)


@pytest.mark.parametrize(
    "headers",
    [
        [("content-length", "9" * 5000)],
        [("content-length", "²")],
        [("transfer-encoding", ""), ("transfer-encoding", "chunked")],
    ],
)
def test_small_json_ambiguous_transport_headers_are_safe_closed(
    harness: Harness,
    headers: list[tuple[str, str]],
) -> None:
    result, consumed = receive_chunks(harness, "/backup", [b"{}"], headers=headers)
    assert result.status_code == 413 and result.json()["error"]["code"] == "BACKUP_TOO_LARGE"
    assert consumed == 0
    assert_safe(result, harness)


@pytest.mark.parametrize(
    "headers,omit",
    [
        ([("origin", ORIGIN), ("origin", ORIGIN)], frozenset()),
        ([("host", "maintenance.example.test"), ("host", "maintenance.example.test")], frozenset()),
        ([], frozenset({"origin"})),
    ],
)
def test_small_json_invalid_origin_authority_before_body(
    harness: Harness,
    headers: list[tuple[str, str]],
    omit: frozenset[str],
) -> None:
    result, consumed = receive_chunks(
        harness, "/backup", [BACKUP_PASSWORD.encode()], headers=headers, omit=omit
    )
    assert result.status_code == 403 and consumed == 0
    assert_safe(result, harness)


@pytest.mark.parametrize("path", ["/backup", "/restore", "/pin"])
def test_small_json_cumulative_chunk_limit_rejects_lie_without_reading_tail(
    harness: Harness,
    path: str,
) -> None:
    chunks = [b" " * 3000, b" " * 3000, b" " * 3000, b"unread-sensitive-tail"]
    result, consumed = receive_chunks(harness, path, chunks, headers=[("content-length", "100")])
    assert result.status_code == 413 and consumed < len(chunks)
    assert result.json()["error"]["code"] == "BACKUP_TOO_LARGE"
    assert_safe(result, harness)
    assert "unread-sensitive-tail" not in result.text


def test_small_json_exact_limit_reaches_semantic_validation(harness: Harness) -> None:
    body = json.dumps({"preview_id": "x" * 43, "confirmed": True}).encode().ljust(8192, b" ")
    result, consumed = receive_chunks(harness, "/restore", [body[:3000], body[3000:]])
    assert result.status_code == 400 and result.json()["error"]["code"] == "RESTORE_PREVIEW_EXPIRED"
    assert consumed == 2
    assert_safe(result, harness)


def test_small_json_invalid_syntax_never_echoes_secret_body(
    harness: Harness,
    caplog: pytest.LogCaptureFixture,
) -> None:
    result, consumed = receive_chunks(
        harness, "/backup", [b'{"password":', BACKUP_PASSWORD.encode()]
    )
    assert result.status_code == 400 and result.json()["error"]["code"] == "VALIDATION_ERROR"
    assert consumed == 2
    assert_safe(result, harness)
    assert BACKUP_PASSWORD not in caplog.text


@pytest.mark.parametrize("kind", ["oversized-stream", "false-length"])
def test_multipart_actual_stream_bounds_and_length_match_fail_without_preview(
    harness: Harness,
    monkeypatch: pytest.MonkeyPatch,
    kind: str,
) -> None:
    monkeypatch.setattr(admin_api, "MAX_SQLITE_BYTES", 256)
    prefix = (
        b'--fixture\r\nContent-Disposition: form-data; name="backup"; filename="ignored"\r\n\r\n'
    )
    suffix = (
        b'\r\n--fixture\r\nContent-Disposition: form-data; name="password"\r\n\r\n'
        b"fixture backup password\r\n--fixture--\r\n"
    )
    if kind == "oversized-stream":
        chunks = [prefix, b"x" * 12000, b"x" * 12000, b"x" * 1000, suffix]
    else:
        chunks = [prefix, b"x" * 100, suffix]
    result, consumed = receive_chunks(
        harness,
        "/restore/inspect",
        chunks,
        headers=[
            ("content-type", "multipart/form-data; boundary=fixture"),
            ("content-length", "100"),
        ],
    )
    assert result.status_code == 400
    assert result.json()["error"]["code"] == "BACKUP_TOO_LARGE"
    if kind == "oversized-stream":
        assert consumed < len(chunks)
    assert_safe(result, harness)
    assert harness.service._preview is None


def test_status_contains_only_safe_local_fields(harness: Harness) -> None:
    result = harness.client.get(BASE + "/status", headers=harness.headers)
    assert result.status_code == 200
    assert result.json() == {
        "active_bundle_id": None,
        "previous_bundle_id": None,
        "pinned_bundle_id": None,
        "last_backup_at": None,
        "local_ready": False,
        "gateway_configured": False,
        "externally_verified": False,
    }
    assert_safe(result, harness)


def test_download_is_ciphertext_with_constant_filename_and_round_trip(
    harness: Harness,
    caplog: pytest.LogCaptureFixture,
) -> None:
    result = harness.client.post(
        BASE + "/backup", headers=harness.headers, json={"password": BACKUP_PASSWORD}
    )
    assert result.status_code == 200
    assert result.headers["content-type"] == "application/octet-stream"
    assert (
        result.headers["content-disposition"]
        == 'attachment; filename="reponpc-backup.reponpc-backup"'
    )
    assert_safe(result, harness)
    location = result.headers["content-location"]
    assert re.fullmatch(BASE + r"/backup/[0-9]{8}T[0-9]{6}-[0-9a-f]{16}", location)
    for _ in range(2):
        downloaded = harness.client.get(location, headers={"Referer": ORIGIN + "/admin"})
        assert downloaded.status_code == 200
        assert downloaded.content == result.content
        assert downloaded.headers["content-type"] == "application/octet-stream"
        assert downloaded.headers["content-disposition"] == result.headers["content-disposition"]
        assert_safe(downloaded, harness)
    metadata, content = unseal(result.content, BACKUP_PASSWORD)
    assert metadata.schema_version == harness.database.schema_version()
    assert metadata.application_version == version("reponpc")
    assert content.startswith(b"SQLite format 3\x00") and b"$argon2id$" in content
    status = harness.client.get(BASE + "/status", headers=harness.headers)
    assert status.json()["last_backup_at"] is not None
    assert (
        len(
            list(
                (harness.database.database_path.parent / "private" / "maintenance").glob(
                    "*.reponpc-backup"
                )
            )
        )
        == 1
    )
    assert BACKUP_PASSWORD not in caplog.text and OWNER_PASSWORD not in caplog.text


@pytest.fixture
def saved_download(harness: Harness, encrypted_backup: bytes) -> tuple[str, Path]:
    path = harness.service._save_encrypted(encrypted_backup)
    backup_id = path.name.removeprefix("backup-").removesuffix(".reponpc-backup")
    return BASE + "/backup/" + backup_id, path


@pytest.mark.parametrize("cookie", ["missing", "wrong"])
def test_saved_backup_requires_owner_session_even_with_known_id(
    harness: Harness, saved_download: tuple[str, Path], cookie: str
) -> None:
    location, path = saved_download
    before = path.read_bytes()
    harness.client.cookies.clear()
    if cookie == "wrong":
        harness.client.cookies.set(SESSION_COOKIE, "wrong-fixture-session")
    result = harness.client.get(location, headers={"Referer": ORIGIN + "/admin"})
    assert result.status_code == 401
    assert_safe(result, harness)
    assert path.read_bytes() == before


@pytest.mark.parametrize(
    "headers",
    [
        [],
        [("Referer", "https://attacker.example/admin")],
        [("Origin", "https://attacker.example"), ("Referer", ORIGIN + "/admin")],
        [("Referer", ORIGIN + ".attacker.example/admin")],
        [("Referer", "http://maintenance.example.test/admin")],
        [("Referer", ORIGIN + "/admin"), ("Host", "attacker.example")],
        [("Referer", ORIGIN + "/admin"), ("Referer", ORIGIN + "/admin")],
        [("Origin", ORIGIN), ("Origin", ORIGIN)],
        [
            ("Origin", ORIGIN),
            ("Host", "maintenance.example.test"),
            ("Host", "maintenance.example.test"),
        ],
    ],
)
def test_saved_backup_rejects_missing_foreign_or_ambiguous_origin(
    harness: Harness, saved_download: tuple[str, Path], headers: list[tuple[str, str]]
) -> None:
    location, path = saved_download
    before = path.read_bytes()
    result = harness.client.get(location, headers=headers)
    assert result.status_code == 403
    assert_safe(result, harness)
    assert path.read_bytes() == before


@pytest.mark.parametrize(
    "backup_id",
    [
        "not-a-backup",
        "20261003T120000-0123456789ABCDEFFF",
        "20261003T120000-0123456789abcde",
        "..%5Coutside",
        "%2Foutside",
    ],
)
def test_saved_backup_rejects_invalid_id_without_creating_storage(
    harness: Harness, backup_id: str
) -> None:
    result = harness.client.get(BASE + "/backup/" + backup_id, headers={"Origin": ORIGIN})
    assert result.status_code in {400, 404}
    assert_safe(result, harness)
    assert not (harness.database.database_path.parent / "private" / "maintenance").exists()


def test_saved_backup_missing_id_does_not_create_a_backup(harness: Harness) -> None:
    result = harness.client.get(
        BASE + "/backup/20261003T120000-0123456789abcdef", headers={"Origin": ORIGIN}
    )
    assert result.status_code == 404
    assert result.json()["error"]["code"] == "BACKUP_DOWNLOAD_UNAVAILABLE"
    assert_safe(result, harness)
    root = harness.database.database_path.parent / "private" / "maintenance"
    assert not list(root.glob("*.reponpc-backup"))


@pytest.mark.parametrize(
    "kind", ["noncipher", "sqlite", "directory", "hardlink", "symlink", "oversized"]
)
def test_saved_backup_refuses_unsafe_files_without_exposing_content(
    harness: Harness,
    saved_download: tuple[str, Path],
    kind: str,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    location, path = saved_download
    original = path.read_bytes()
    outside = tmp_path / "outside-private-payload"
    outside.write_bytes(original)
    if kind == "noncipher":
        path.write_bytes(b"fixture-private-payload-canary")
    elif kind == "sqlite":
        path.write_bytes(harness.database.database_path.read_bytes())
    elif kind == "directory":
        path.unlink()
        path.mkdir()
    elif kind == "hardlink":
        path.unlink()
        os.link(outside, path)
    elif kind == "symlink":
        path.unlink()
        try:
            path.symlink_to(outside)
        except OSError:
            pytest.skip("symlink creation is unavailable for this test account")
    else:
        monkeypatch.setattr(maintenance_module, "MAX_SQLITE_BYTES", 16)
        path.write_bytes(original[:16] + b"x" * 16384)
    result = harness.client.get(location, headers={"Referer": ORIGIN + "/admin"})
    invalid_format = kind in {"noncipher", "sqlite"}
    assert result.status_code == (400 if invalid_format else 503)
    assert result.json()["error"]["code"] == (
        "BACKUP_FORMAT_INVALID" if invalid_format else "BACKUP_STORAGE_UNAVAILABLE"
    )
    assert_safe(result, harness)
    assert "fixture-private-payload-canary" not in result.text
    assert str(outside) not in result.text
    assert outside.read_bytes() == original
    assert path.exists()
    assert not list(path.parent.glob("preview-*"))


def test_inspect_returns_opaque_metadata_ttl_only_and_ignores_uploaded_path(
    harness: Harness,
    encrypted_backup: bytes,
    tmp_path: Path,
) -> None:
    before = datetime.now(UTC)
    result = inspect_backup(harness, encrypted_backup, filename="../../outside.sqlite")
    assert result.status_code == 200
    assert_safe(result, harness)
    payload = result.json()
    assert set(payload) == {
        "preview_id",
        "created_at",
        "schema_version",
        "application_version",
        "expires_at",
    }
    assert re.fullmatch(r"[A-Za-z0-9_-]{43}", payload["preview_id"])
    assert payload["schema_version"] == harness.database.schema_version()
    assert payload["application_version"] == version("reponpc")
    assert (
        before + timedelta(minutes=9)
        < datetime.fromisoformat(payload["expires_at"])
        < before + timedelta(minutes=11)
    )
    assert "outside.sqlite" not in result.text
    assert not (tmp_path / "outside.sqlite").exists()
    assert not (tmp_path.parent / "outside.sqlite").exists()


@pytest.mark.parametrize("failure", ["password", "tamper"])
def test_inspect_wrong_password_and_tamper_safe(
    harness: Harness,
    encrypted_backup: bytes,
    failure: str,
) -> None:
    password = BACKUP_PASSWORD if failure == "tamper" else "different fixture password"
    artifact = (
        encrypted_backup[:-1] + bytes([encrypted_backup[-1] ^ 1])
        if failure == "tamper"
        else encrypted_backup
    )
    result = inspect_backup(harness, artifact, password=password)
    assert result.status_code == 400 and result.json()["error"]["code"] == "BACKUP_DECRYPT_FAILED"
    assert_safe(result, harness)
    assert harness.service._preview is None


@pytest.mark.parametrize(
    "path,method,body",
    [
        ("/status", "GET", None),
        ("/backup", "POST", {"password": BACKUP_PASSWORD}),
        ("/restore", "POST", {"preview_id": "x" * 43, "confirmed": True}),
        ("/pin", "POST", {"bundle_id": "fixture-previous", "confirmed": True}),
        ("/gateway/stop", "POST", {}),
    ],
)
def test_all_maintenance_actions_require_owner_session(
    harness: Harness,
    path: str,
    method: str,
    body: Any,
) -> None:
    harness.client.cookies.clear()
    result = harness.client.request(method, BASE + path, headers={"Origin": ORIGIN}, json=body)
    assert result.status_code == 401
    assert_safe(result, harness)


@pytest.mark.parametrize(
    "headers", [{"Origin": ORIGIN}, {"Origin": "https://attacker.example", "X-CSRF-Token": "bad"}]
)
def test_backup_csrf_and_cross_origin_rejected(harness: Harness, headers: dict[str, str]) -> None:
    result = harness.client.post(
        BASE + "/backup", headers=headers, json={"password": BACKUP_PASSWORD}
    )
    assert result.status_code == 403
    assert_safe(result, harness)
    assert not (harness.database.database_path.parent / "private" / "maintenance").exists()


@pytest.mark.parametrize("boundary", ["unauthorized", "csrf", "origin"])
def test_upload_requires_auth_csrf_and_origin_before_inspection(
    harness: Harness,
    encrypted_backup: bytes,
    boundary: str,
) -> None:
    headers = dict(harness.headers)
    expected = 403
    if boundary == "unauthorized":
        harness.client.cookies.clear()
        expected = 401
    elif boundary == "csrf":
        del headers["X-CSRF-Token"]
    else:
        headers["Origin"] = "https://attacker.example"
    result = inspect_backup(harness, encrypted_backup, headers=headers)
    assert result.status_code == expected
    assert harness.service._preview is None
    assert_safe(result, harness)


@pytest.mark.parametrize(
    "headers",
    [
        [],
        [("Origin", "https://attacker.example")],
        [("Origin", ORIGIN), ("Origin", ORIGIN)],
        [("Origin", ORIGIN), ("Host", "attacker.example")],
    ],
)
def test_status_requires_strict_private_origin(
    harness: Harness, headers: list[tuple[str, str]]
) -> None:
    result = harness.client.get(BASE + "/status", headers=headers)
    assert result.status_code == 403
    assert_safe(result, harness)


@pytest.mark.parametrize("kind", ["missing", "oversized", "duplicate", "negative", "transfer"])
def test_upload_content_length_boundary_before_inspection(
    harness: Harness,
    encrypted_backup: bytes,
    kind: str,
) -> None:
    request = harness.client.build_request(
        "POST",
        BASE + "/restore/inspect",
        headers=harness.headers,
        files={"backup": ("fixture", encrypted_backup)},
        data={"password": BACKUP_PASSWORD},
    )
    del request.headers["content-length"]
    if kind == "oversized":
        request.headers["Content-Length"] = str(128 * 1024 * 1024 + 24577)
    elif kind == "duplicate":
        request.headers = httpx.Headers(
            [*request.headers.multi_items(), ("content-length", "1"), ("content-length", "1")]
        )
    elif kind == "negative":
        request.headers["Content-Length"] = "-1"
    elif kind == "transfer":
        request.headers["Content-Length"] = "1"
        request.headers["Transfer-Encoding"] = "chunked"
    result = harness.client.send(request)
    assert result.status_code == 400
    assert result.json()["error"]["code"] == "BACKUP_TOO_LARGE"
    assert_safe(result, harness)
    assert harness.service._preview is None


@pytest.mark.parametrize(
    "kind", ["duplicate-password", "duplicate-backup", "wrong-field", "password-file"]
)
def test_multipart_duplicate_and_wrong_fields_rejected(
    harness: Harness,
    encrypted_backup: bytes,
    kind: str,
) -> None:
    fields: list[tuple[str, Any]] = [
        ("backup", ("fixture", encrypted_backup)),
        ("password", (None, BACKUP_PASSWORD)),
    ]
    if kind == "duplicate-password":
        fields.append(("password", (None, BACKUP_PASSWORD)))
    elif kind == "duplicate-backup":
        fields.append(("backup", ("other", encrypted_backup)))
    elif kind == "wrong-field":
        fields[0] = ("wrong", ("fixture", encrypted_backup))
    else:
        fields[1] = ("password", ("password.txt", BACKUP_PASSWORD))
    result = harness.client.post(BASE + "/restore/inspect", headers=harness.headers, files=fields)
    assert result.status_code == 400 and result.json()["error"]["code"] == "BACKUP_FORMAT_INVALID"
    assert_safe(result, harness)
    assert harness.service._preview is None


def test_preview_cancel_is_bound_to_session_and_clears_plaintext(
    harness: Harness,
    encrypted_backup: bytes,
) -> None:
    selected = preview(harness, encrypted_backup)
    original_cookie = harness.client.cookies.get(SESSION_COOKIE)
    original_headers = harness.headers
    harness.headers = login(harness.client)
    route = BASE + "/restore/" + selected["preview_id"]
    refused = harness.client.delete(route, headers=harness.headers)
    assert (
        refused.status_code == 400 and refused.json()["error"]["code"] == "RESTORE_PREVIEW_EXPIRED"
    )
    assert harness.service._preview is not None
    preview_directory = harness.service._preview.directory
    cancelled = harness.client.delete(
        route, headers={**original_headers, "Cookie": f"{SESSION_COOKIE}={original_cookie}"}
    )
    assert cancelled.status_code == 204 and cancelled.content == b""
    assert cancelled.headers["cache-control"] == "no-store"
    assert harness.service._preview is None and not preview_directory.exists()


@pytest.mark.parametrize("confirmation", [False, 1, "true", None])
def test_restore_requires_strict_true_consent(harness: Harness, confirmation: Any) -> None:
    result = harness.client.post(
        BASE + "/restore",
        headers=harness.headers,
        json={"preview_id": "x" * 43, "confirmed": confirmation},
    )
    assert result.status_code == 400 and result.json()["error"]["code"] == "VALIDATION_ERROR"
    assert_safe(result, harness)
    assert harness.host._maintenance is None


@pytest.mark.parametrize("confirmation", [False, 1, "true"])
def test_pin_requires_strict_true_consent(harness: Harness, confirmation: Any) -> None:
    result = harness.client.post(
        BASE + "/pin",
        headers=harness.headers,
        json={"bundle_id": "fixture-previous", "confirmed": confirmation},
    )
    assert result.status_code == 400 and result.json()["error"]["code"] == "VALIDATION_ERROR"
    assert_safe(result, harness)


def test_expired_restore_preview_cannot_schedule(harness: Harness, encrypted_backup: bytes) -> None:
    selected = preview(harness, encrypted_backup)
    assert harness.service._preview is not None
    harness.service._preview.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    result = harness.client.post(
        BASE + "/restore",
        headers=harness.headers,
        json={"preview_id": selected["preview_id"], "confirmed": True},
    )
    assert result.status_code == 400 and result.json()["error"]["code"] == "RESTORE_PREVIEW_EXPIRED"
    assert harness.host._maintenance is None
    assert_safe(result, harness)


def test_restore_202_replaces_real_app_revokes_sessions_and_saves_current_ciphertext(
    harness: Harness,
    encrypted_backup: bytes,
    tmp_path: Path,
) -> None:
    old_app = harness.host.current
    with harness.database.connection() as connection:
        connection.execute(
            "UPDATE admin_owner SET username='changed-owner' WHERE state_key='current'"
        )
    selected = preview(harness, encrypted_backup)
    result = harness.client.post(
        BASE + "/restore",
        headers=harness.headers,
        json={"preview_id": selected["preview_id"], "confirmed": True},
    )
    assert result.status_code == 202 and result.json() == {"status": "restoring"}
    assert_safe(result, harness)

    async def settle() -> None:
        assert harness.host._maintenance is not None
        await asyncio.wait_for(asyncio.shield(harness.host._maintenance), 10)

    assert harness.client.portal is not None
    harness.client.portal.call(settle)
    assert harness.host.current is not old_app and not harness.host.busy
    assert harness.host.last_error is None
    assert harness.service._preview is None
    refused = harness.client.get(BASE + "/status", headers=harness.headers)
    assert refused.status_code == 401
    with harness.database.connection() as connection:
        assert (
            connection.execute(
                "SELECT username FROM admin_owner WHERE state_key='current'"
            ).fetchone()[0]
            == "owner"
        )
        assert connection.execute("SELECT count(*) FROM admin_sessions").fetchone()[0] == 0
        assert (
            connection.execute("SELECT count(*) FROM admin_local_launch_grants").fetchone()[0] == 0
        )
    root = harness.database.database_path.parent / "private" / "maintenance"
    artifacts = list(root.glob("*.reponpc-backup"))
    assert len(artifacts) == 1 and not list(root.glob("preview-*"))
    _metadata, content = unseal(artifacts[0].read_bytes(), BACKUP_PASSWORD)
    snapshot = tmp_path / "automatic-before-restore.sqlite"
    snapshot.write_bytes(content)
    with closing(sqlite3.connect(snapshot)) as saved:
        assert (
            saved.execute("SELECT username FROM admin_owner WHERE state_key='current'").fetchone()[
                0
            ]
            == "changed-owner"
        )
    harness.headers = login(harness.client)
    assert harness.client.get(BASE + "/status", headers=harness.headers).status_code == 200


def test_pin_only_previous_and_gateway_stop_exposes_only_status(harness: Harness) -> None:
    database = harness.database
    database.save_bundle_state(
        replace(
            database.bundle_state(),
            active_bundle_id="fixture-active",
            previous_bundle_id="fixture-previous",
        )
    )
    pins: list[str] = []

    class Manager:
        def status(self) -> Any:
            return SimpleNamespace(previous_bundle_id="fixture-previous")

        def active_public_directory(self) -> None:
            return None

        def pin(self, bundle_id: str, *, require_previous: bool = False) -> Any:
            assert require_previous is True
            pins.append(bundle_id)
            database.save_bundle_state(
                replace(
                    database.bundle_state(), active_bundle_id=bundle_id, pinned_bundle_id=bundle_id
                )
            )
            return SimpleNamespace(active_bundle_id=bundle_id)

    class Gateway:
        stopped = False

        def snapshot(self) -> dict[str, Any]:
            return {
                "revision": 1,
                "local_ready": True,
                "gateway_origin": "https://fixture.ts.net",
                "pages_origin": "https://fixture.github.io",
                "external_verified": not self.stopped,
                "private_canary": "FIXTURE_GATEWAY_PRIVATE_CANARY",
            }

        async def stop(self, *, revision: int) -> None:
            assert revision == 1
            self.stopped = True

    gateway = Gateway()
    harness.host.current.state.bundle_manager = Manager()
    harness.host.current.state.visitor_gateway = gateway
    rejected = harness.client.post(
        BASE + "/pin",
        headers=harness.headers,
        json={"bundle_id": "arbitrary-id", "confirmed": True},
    )
    assert rejected.status_code == 400 and pins == []
    assert database.bundle_state().active_bundle_id == "fixture-active"
    assert harness.host.current.state.reponpc.index_version is None
    pinned = harness.client.post(
        BASE + "/pin",
        headers=harness.headers,
        json={"bundle_id": "fixture-previous", "confirmed": True},
    )
    assert pinned.status_code == 200 and pins == ["fixture-previous"]
    assert pinned.json()["active_bundle_id"] == "fixture-previous"
    assert harness.host.current.state.reponpc.index_ready is True
    assert harness.host.current.state.reponpc.index_version == "fixture-previous"
    assert harness.host.current.state.reponpc.public_directory is None
    stopped = harness.client.post(BASE + "/gateway/stop", headers=harness.headers, json={})
    assert stopped.status_code == 200 and gateway.stopped
    assert stopped.json()["externally_verified"] is False
    assert "FIXTURE_GATEWAY_PRIVATE_CANARY" not in stopped.text
    assert "fixture.ts.net" not in stopped.text
    assert_safe(stopped, harness)


def test_no_public_maintenance_routes_or_secret_validation_echo(harness: Harness) -> None:
    for path in (
        "/api/public/maintenance/status",
        "/api/public/maintenance/backup",
        "/api/public/maintenance/restore",
    ):
        assert harness.client.get(path).status_code == 404
    invalid = harness.client.post(
        BASE + "/backup", headers=harness.headers, json={"password": "tiny-sensitive"[:5]}
    )
    assert invalid.status_code == 400
    assert "tiny-" not in invalid.text
    assert_safe(invalid, harness)
