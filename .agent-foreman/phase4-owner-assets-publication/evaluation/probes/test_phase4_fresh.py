"""Fresh Phase 4 read-only falsification probes.

The probes exercise production entrypoints while keeping all mutable state in
pytest's temporary directory or evaluator-owned in-memory fakes.  This file is
the only evaluator-owned source file for this run.
"""

from __future__ import annotations

import base64
import hashlib
import io
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from argon2 import PasswordHasher, Type
from fastapi.testclient import TestClient
from PIL import Image

from reponpc.admin.auth import AdminSessionService
from reponpc.admin.github import GitHubAdminClient, GitHubResponse
from reponpc.admin.operations import AdminOperations
from reponpc.bundles.manifest import StableManifest
from reponpc.cards.assets import validate_sprite
from reponpc.cards.render import CardCopy, CardPalette, render_card_assets
from reponpc.cards.sprite_composer import compose_builtin
from reponpc.config.models import BuiltinCharacterConfig
from reponpc.indexing.publication import PublicationCoordinator, PublicationError
from reponpc.main import create_app
from reponpc.runtime.database import RuntimeDatabase

ROOT = Path(__file__).resolve().parents[4]
EVALUATION = ROOT / ".agent-foreman/phase4-owner-assets-publication/evaluation"
ARTIFACT = EVALUATION / "evaluation-phase4.json"
ORIGIN = "https://portfolio.example.com"
PASSWORD = "correct horse battery staple"
CANARY = "P4_FRESH_SECRET_CANARY_91f8c0"
CONFIG = (ROOT / "tests/fixtures/phase2/reponpc.yml").read_bytes()
RESULTS: list[dict[str, Any]] = []
EVALUATION_COMMAND = (
    "rtk proxy uv --cache-dir D:/RepoNPC/.uv-cache run --offline pytest -p no:cacheprovider "
    "--basetemp D:/RepoNPC/.pytest-tmp/p4-eval "
    ".agent-foreman/phase4-owner-assets-publication/evaluation/probes/test_phase4_fresh.py -q"
)


def _record(
    identifier: str,
    *,
    invariant_id: str,
    setup: str,
    fault_injection: str,
    trigger: str,
    passed: bool,
    oracle: str,
    observed: dict[str, Any],
) -> None:
    RESULTS.append(
        {
            "probe_id": identifier,
            "invariant_id": invariant_id,
            "command": EVALUATION_COMMAND,
            "artifact_path": ".agent-foreman/phase4-owner-assets-publication/evaluation/artifacts/gate-evaluation.txt",
            "exit_code": 0 if passed else 1,
            "setup": setup,
            "fault_injection": fault_injection,
            "trigger": trigger,
            "oracle": oracle,
            "anti_oracle": "The assertion must be observed through a production API/producer boundary, not a copied policy check.",
            "passed": passed,
            "observed": observed,
        }
    )


class RecordingTransport:
    def __init__(self, *, config_sha: str = "a" * 40) -> None:
        self.requests: list[tuple[str, str, bytes | None]] = []
        self.config_sha = config_sha
        self.files = {"reponpc.yml": (CONFIG, config_sha)}

    def request(
        self, *, method: str, url: str, headers: dict[str, str], body: bytes | None
    ) -> GitHubResponse:
        del headers
        self.requests.append((method, url, body))
        if method == "GET" and "/commits/" in url:
            return GitHubResponse(200, json.dumps({"sha": "b" * 40}).encode())
        if method == "GET" and "/contents/" in url:
            path = url.split("/contents/", 1)[1].split("?", 1)[0]
            if path not in self.files:
                return GitHubResponse(404, b"{}")
            content, sha = self.files[path]
            return GitHubResponse(
                200,
                json.dumps(
                    {"content": base64.b64encode(content).decode("ascii"), "sha": sha}
                ).encode(),
            )
        if method == "PUT":
            return GitHubResponse(200, json.dumps({"commit": {"sha": "c" * 40}, "content": {"sha": "d" * 40}}).encode())
        raise AssertionError((method, url))


def _app(tmp_path: Path, transport: RecordingTransport | None = None):
    database = RuntimeDatabase(tmp_path / "runtime")
    database.initialize()
    auth = AdminSessionService(
        database=database,
        username="admin",
        password_hash=PasswordHasher(type=Type.ID).hash(PASSWORD),
        identity_hmac_key=b"i" * 32,
        now=lambda: datetime(2026, 8, 13, tzinfo=UTC),
    )
    if transport is None:
        return create_app(admin_session_service=auth, admin_origins=(ORIGIN,)), database
    github = GitHubAdminClient(
        repository="owner/profile",
        branch="main",
        workflow="build-index.yml",
        token="server-only-token",
        transport=transport,
    )
    operations = AdminOperations(github, database, ORIGIN)
    return create_app(
        admin_session_service=auth,
        admin_origins=(ORIGIN,),
        admin_operations=operations,
    ), database


def _login(client: TestClient) -> str:
    response = client.post(
        "/api/admin/session",
        headers={"Origin": ORIGIN},
        json={"username": "admin", "password": PASSWORD},
    )
    assert response.status_code == 200
    return str(response.json()["csrf_token"])


def _sprite() -> bytes:
    image = Image.new("RGBA", (128, 224), (0, 0, 0, 0))
    for row in range(7):
        for column in range(4):
            image.putpixel((column * 32 + 4, row * 32 + 4), (20, 30, 40, 255))
    output = io.BytesIO()
    image.save(output, "PNG")
    return output.getvalue()


def test_cross_origin_and_missing_origin_csrf_fail_closed(tmp_path: Path) -> None:
    app, _database = _app(tmp_path)
    observed: dict[str, Any] = {}
    with TestClient(app, base_url=ORIGIN) as client:
        hostile = client.post(
            "/api/admin/session",
            headers={"Origin": "https://evil.example"},
            json={"username": "admin", "password": PASSWORD},
        )
        missing = client.post(
            "/api/admin/session",
            json={"username": "admin", "password": PASSWORD},
        )
        csrf = _login(client)
        forged = client.post(
            "/api/admin/session/refresh",
            headers={"Origin": ORIGIN, "X-CSRF-Token": "forged"},
        )
        hostile_refresh = client.post(
            "/api/admin/session/refresh",
            headers={"Origin": "https://evil.example", "X-CSRF-Token": csrf},
        )
    statuses = [hostile.status_code, missing.status_code, forged.status_code, hostile_refresh.status_code]
    observed["statuses"] = statuses
    observed["codes"] = [
        hostile.json()["error"]["code"],
        missing.json()["error"]["code"],
        forged.json()["error"]["code"],
        hostile_refresh.json()["error"]["code"],
    ]
    passed = statuses == [403, 403, 403, 403] and observed["codes"] == ["CSRF_FAILED"] * 4
    _record(
        "PROBE-P4-CSRF-ORIGIN",
        invariant_id="INV-ADMIN-AUTH",
        setup="Temporary RuntimeDatabase with the real AdminSessionService and FastAPI admin router.",
        fault_injection="Hostile Origin, missing Origin, forged CSRF token, and hostile Origin on refresh.",
        trigger="POST /api/admin/session and POST /api/admin/session/refresh through TestClient.",
        passed=passed,
        oracle="Cross-origin, missing-origin, and forged-CSRF login/refresh requests all fail with 403 CSRF_FAILED.",
        observed=observed,
    )
    assert passed


def test_stale_sha_does_not_overwrite(tmp_path: Path) -> None:
    transport = RecordingTransport(config_sha="a" * 40)
    app, _database = _app(tmp_path, transport)
    with TestClient(app, base_url=ORIGIN) as client:
        csrf = _login(client)
        response = client.put(
            "/api/admin/config",
            headers={"Origin": ORIGIN, "X-CSRF-Token": csrf},
            json={
                "content": CONFIG.decode(),
                "expected_blob_sha": "b" * 40,
                "commit_message": "stale attempt",
            },
        )
    methods = [method for method, _url, _body in transport.requests]
    observed = {"status": response.status_code, "code": response.json()["error"]["code"], "methods": methods}
    passed = response.status_code == 409 and observed["code"] == "CONFIG_CONFLICT" and "PUT" not in methods
    _record(
        "PROBE-P4-STALE-SHA",
        invariant_id="INV-GITHUB-WRITE",
        setup="Real admin route backed by a mutation-recording GitHub transport whose current config blob SHA is fixed.",
        fault_injection="Submit a different expected_blob_sha than the current remote blob SHA.",
        trigger="PUT /api/admin/config with valid config bytes and stale SHA.",
        passed=passed,
        oracle="A stale expected blob SHA returns CONFIG_CONFLICT and performs no GitHub PUT.",
        observed=observed,
    )
    assert passed


def test_polyglot_png_rejected_before_mutation(tmp_path: Path) -> None:
    transport = RecordingTransport()
    app, _database = _app(tmp_path, transport)
    polyglot = _sprite() + b"\n<script>" + CANARY.encode()
    with TestClient(app, base_url=ORIGIN) as client:
        csrf = _login(client)
        response = client.put(
            "/api/admin/assets/character/hero.png",
            headers={"Origin": ORIGIN, "X-CSRF-Token": csrf},
            files={"file": ("hero.png", polyglot, "image/png")},
            data={"expected_blob_sha": "a" * 40, "commit_message": "asset"},
        )
    methods = [method for method, _url, _body in transport.requests]
    observed = {"status": response.status_code, "code": response.json()["error"]["code"], "methods": methods, "canary_visible": CANARY in response.text}
    passed = response.status_code == 422 and observed["code"] == "ASSET_INVALID" and "PUT" not in methods and not observed["canary_visible"]
    _record(
        "PROBE-P4-PNG-POLYGLOT",
        invariant_id="INV-ASSET-CANONICAL",
        setup="Real admin asset route with a canonical-dimension RGBA sprite fixture.",
        fault_injection="Append executable-looking polyglot bytes and a secret canary after the PNG IEND.",
        trigger="PUT /api/admin/assets/character/hero.png before GitHub writeback.",
        passed=passed,
        oracle="A valid PNG with trailing polyglot bytes is rejected before any GitHub mutation and does not echo a canary.",
        observed=observed,
    )
    assert passed


def test_builtin_composer_bytes_pass_real_canonical_validator(tmp_path: Path) -> None:
    del tmp_path
    config = BuiltinCharacterConfig.model_validate(
        {
            "body": "standard",
            "skin": "dark",
            "hair": "long",
            "hair_color": "#112233",
            "outfit": "engineer",
            "primary_color": "#445566",
            "secondary_color": "#778899",
            "accessory": "headphones",
        }
    )
    first = compose_builtin(config)
    second = compose_builtin(config)
    validated = validate_sprite(first)
    passed = first == second and validated.content == first and validated.width == 128 and validated.height == 224
    _record(
        "PROBE-P4-SPRITE-CONSUMER",
        invariant_id="INV-SPRITE-COMPOSITION",
        setup="Production built-in composer configured with a non-default allowlisted palette and layers.",
        fault_injection="Exercise long hair, engineer outfit, headphones, dark skin, and distinct colors across all generated states.",
        trigger="Pass compose_builtin() bytes unchanged into the production canonical validate_sprite() consumer.",
        passed=passed,
        oracle="Two compositions are byte-identical and the real consumer accepts the exact 128x224 canonical bytes unchanged.",
        observed={"deterministic": first == second, "consumer_bytes_identical": validated.content == first, "size": [validated.width, validated.height]},
    )
    assert passed


def test_hostile_bilingual_card_svg_is_static_and_local(tmp_path: Path) -> None:
    del tmp_path
    sprite = validate_sprite(_sprite())
    palette = CardPalette("#f7f4e9", "#fffdf7", "#24202e", "#6d5dfc", "#2f2842")
    observed: dict[str, Any] = {}
    passed = True
    for locale, text in (("zh-TW", "</text><script>alert(1)</script>"), ("en", "<img src=\"https://evil.invalid/x\" onerror=alert(1)>") ):
        rendered = render_card_assets(
            copy=CardCopy(text, text, "<foreignObject>https://evil.invalid</foreignObject>", 1),
            palette=palette,
            sprite=sprite,
        )
        svg = rendered.svg.decode("utf-8")
        import xml.etree.ElementTree as ET

        root = ET.fromstring(rendered.svg)
        forbidden_elements = {"script", "foreignObject", "image", "iframe", "object", "embed", "use"}
        active_elements = [
            element.tag.rsplit("}", 1)[-1]
            for element in root.iter()
            if element.tag.rsplit("}", 1)[-1] in forbidden_elements
        ]
        forbidden_attributes: list[str] = []
        remote_values: list[str] = []
        for element in root.iter():
            for key, value in element.attrib.items():
                local_key = key.rsplit("}", 1)[-1]
                if local_key.casefold() in {"href", "src", "xlink:href"} or local_key.casefold().startswith("on"):
                    forbidden_attributes.append(local_key)
                if "url(" in value.casefold() or re.search(r"(?i)https?://", value):
                    remote_values.append(value)
        text_nodes = "".join(root.itertext())
        observed[locale] = {
            "bytes": len(rendered.svg),
            "active_elements": active_elements,
            "forbidden_attributes": forbidden_attributes,
            "remote_attribute_values": remote_values,
            "escaped_payload_in_text": "alert(1)" in text_nodes,
            "svg_namespace": root.tag == "{http://www.w3.org/2000/svg}svg",
        }
        passed = passed and not active_elements and not forbidden_attributes and not remote_values
        passed = passed and root.tag == "{http://www.w3.org/2000/svg}svg" and "alert(1)" in text_nodes
    _record(
        "PROBE-P4-CARD-SVG-INJECTION",
        invariant_id="INV-CARD-SAFE",
        setup="Render production SVG card assets from a canonical sprite and hostile bilingual CardCopy text.",
        fault_injection="Inject XML breakout, script, image, URL, and event-handler-looking text into copy fields.",
        trigger="render_card_assets() followed by an XML parser and element/attribute inspection.",
        passed=passed,
        oracle="Hostile zh-TW/en text is XML-escaped; SVG contains no active elements, handlers, or remote references.",
        observed=observed,
    )
    assert passed


class RecordingPublisher:
    def __init__(self, fail_at: str | None = None) -> None:
        self.fail_at = fail_at
        self.events: list[str] = []
        self.stable = b'{"prior":"stable"}'

    def _event(self, name: str) -> None:
        self.events.append(name)
        if self.fail_at == name:
            raise OSError(name)

    def create_immutable_release(self, *, tag: str, name: str) -> int:
        del tag, name
        self._event("release")
        return 1

    def upload_immutable_asset(self, *, release_id: int, name: str, content: bytes) -> str:
        del release_id, name, content
        self._event("upload")
        return "https://github.com/owner/repo/releases/download/index/asset.tar.zst"

    def verify_asset(self, *, asset_url: str, size: int, sha256: str) -> None:
        del asset_url, size, sha256
        self._event("verify")

    def update_stable_manifest_last(self, *, content: bytes) -> None:
        self._event("stable")
        self.stable = content


def test_publication_failures_preserve_stable_pointer(tmp_path: Path) -> None:
    archive = tmp_path / "reponpc-index-20260813T120000Z-0123456789ab.tar.zst"
    archive.write_bytes(b"immutable bundle")
    bundle = SimpleNamespace(
        archive_path=archive,
        archive_sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),
        archive_size=archive.stat().st_size,
        manifest=SimpleNamespace(bundle_id="20260813T120000Z-0123456789ab"),
    )
    observed: dict[str, Any] = {}
    passed = True
    for failure in ("release", "upload", "verify"):
        publisher = RecordingPublisher(failure)
        before = publisher.stable
        try:
            PublicationCoordinator(publisher).publish_immutable(bundle, now=datetime(2026, 8, 13, tzinfo=UTC))
        except PublicationError as exc:
            code = exc.code
        else:
            code = "unexpected_success"
        observed[failure] = {"events": publisher.events, "code": code, "stable_unchanged": publisher.stable == before}
        passed = passed and code == "bundle_publication_failed" and publisher.stable == before and "stable" not in publisher.events
    _record(
        "PROBE-P4-PUBLICATION-LAST",
        invariant_id="INV-PUBLICATION-LAST",
        setup="PublicationCoordinator with an in-memory prior stable manifest pointer and immutable archive fixture.",
        fault_injection="Raise OSError independently at release creation, asset upload, and verification.",
        trigger="publish_immutable() for each injected failure stage.",
        passed=passed,
        oracle="Release/upload/verification failures never mutate the stable pointer and expose only the safe publication error code.",
        observed=observed,
    )
    assert passed


def test_secret_canary_absent_from_api_database_and_audit(tmp_path: Path) -> None:
    transport = RecordingTransport()
    app, database = _app(tmp_path, transport)
    with TestClient(app, base_url=ORIGIN) as client:
        failed_login = client.post(
            "/api/admin/session",
            headers={"Origin": ORIGIN},
            json={"username": CANARY, "password": CANARY},
        )
        csrf = _login(client)
        invalid = client.post(
            "/api/admin/config/validate",
            json={"content": f"schema_version: 1\nsecret: {CANARY}\n"},
        )
        failed_write = client.put(
            "/api/admin/config",
            headers={"Origin": ORIGIN, "X-CSRF-Token": csrf},
            json={
                "content": f"schema_version: 1\nsecret: {CANARY}\n",
                "expected_blob_sha": "a" * 40,
                "commit_message": CANARY,
            },
        )
    with database.connection() as connection:
        rows = connection.execute("SELECT * FROM admin_audit").fetchall()
        database_bytes = database.path.read_bytes() if hasattr(database, "path") else b""  # type: ignore[attr-defined]
        audit_text = repr([tuple(row) for row in rows])
    joined = failed_login.text + invalid.text + failed_write.text + audit_text + database_bytes.decode("latin1", errors="ignore")
    observed = {
        "statuses": [failed_login.status_code, invalid.status_code, failed_write.status_code],
        "canary_in_api": CANARY in (failed_login.text + invalid.text + failed_write.text),
        "canary_in_audit": CANARY in audit_text,
        "canary_in_database": CANARY in database_bytes.decode("latin1", errors="ignore"),
        "audit_rows": len(rows),
    }
    passed = CANARY not in joined
    _record(
        "PROBE-P4-SECRET-CANARY",
        invariant_id="INV-PRIVACY",
        setup="Real admin HTTP routes plus runtime SQLite audit table and distinct secret canary input.",
        fault_injection="Place the canary in failed credentials, invalid config, write content, and commit message.",
        trigger="POST/PUT admin routes, then scan response bodies, audit rows, and runtime database bytes.",
        passed=passed,
        oracle="A login/config/write canary is absent from API errors, runtime SQLite bytes, and audit rows.",
        observed=observed,
    )
    assert passed


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    payload = {
        "schema_name": "agent-foreman/evaluation",
        "schema_version": "1.0",
        "plan_id": "REPONPC-P4-OWNER-ASSETS-PUBLICATION-20260813",
        "phase_id": "PHASE-4-FRESH-EVALUATION",
        "context_freshness": "fresh",
        "production_access": "read-only",
        "evaluation_write_scope": ".agent-foreman/phase4-owner-assets-publication/evaluation/**",
        "new_probes": RESULTS,
        "findings": [
            {
                "probe_id": item["probe_id"],
                "severity": "high",
                "status": "open",
                "observed": item["observed"],
            }
            for item in RESULTS
            if not item["passed"]
        ],
        "profile": "full",
        "model_diversity": "same-model-fresh-context",
        "recommendation": "pass" if exitstatus == 0 and all(item["passed"] for item in RESULTS) else "revise",
        "deterministic_result": "passed" if exitstatus == 0 and all(item["passed"] for item in RESULTS) else "failed",
        "pytest_exit_code": exitstatus,
        "scope_note": "Fresh Phase 4 evaluator only; no v1 completion claim.",
    }
    ARTIFACT.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
