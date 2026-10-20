"""Main's independent A5 boundary checks, separate from implementer tests."""

from __future__ import annotations

import io
import json
import sqlite3
import struct
import threading
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml
from fastapi.testclient import TestClient
from PIL import Image, ImageDraw

from reponpc.admin.batch_resolver import (
    GitHubHttpResponse,
    GitHubRateLimiter,
    GitHubRESTMetadataResolver,
    RepositorySelection,
)
from reponpc.admin.local_portfolio import LocalPortfolioError, LocalPortfolioStore
from reponpc.admin.scene import AdminSceneService
from reponpc.api.visitor_document import (
    render_published_visitor_document,
    render_visitor_document,
)
from reponpc.cards.assets import validate_sprite
from reponpc.config.models import SceneConfig
from reponpc.indexing.github import GitHubSourceResolver
from reponpc.indexing.public_profile import CharacterMetadata, PublicRepository
from reponpc.main import create_app
from reponpc.runtime.database import MIGRATIONS, Migration, RuntimeDatabase, RuntimeDatabaseError
from reponpc.scene.images import SceneImageError, validate_scene_image
from reponpc.scene.registry import (
    SceneRegistryError,
    default_scene_registry,
    fallback_stylesheet,
    parse_scene_registry,
)
from reponpc.scene.resolve import PublicScene, resolve_scene

ROOT = Path(__file__).resolve().parents[2]

_VISITOR_HTML = (
    b'<!doctype html><html lang="en" data-owner-mode="system" '
    b'data-visitor-toggle="true"><head><script src="./scene-mode.js"></script>'
    b'<link rel="stylesheet" href="./visitor.css"></head><body></body></html>'
)


@pytest.mark.parametrize("primary_size", [(16384, 16384), (800, 400)], ids=["bomb", "mismatch"])
def test_webp_rejects_primary_dimensions_before_open(
    primary_size: tuple[int, int], monkeypatch: pytest.MonkeyPatch
) -> None:
    def chunk(kind: bytes, payload: bytes) -> bytes:
        return kind + struct.pack("<I", len(payload)) + payload + b"\0" * (len(payload) & 1)

    canvas = b"\0" * 4 + (639).to_bytes(3, "little") + (359).to_bytes(3, "little")
    width, height = primary_size
    packed = (width - 1) | ((height - 1) << 14)
    body = b"WEBP" + chunk(b"VP8X", canvas) + chunk(b"VP8L", b"\x2f" + packed.to_bytes(4, "little"))
    content = b"RIFF" + struct.pack("<I", len(body)) + body

    def unexpected_decode(*args: object, **kwargs: object) -> None:
        pytest.fail("primary dimension rejection must precede Image.open")

    monkeypatch.setattr(Image, "open", unexpected_decode)
    with pytest.raises(SceneImageError):
        validate_scene_image(content, filename="review.webp")


@pytest.mark.parametrize("format_name", ["PNG", "WEBP"])
def test_image_canonicalization_strips_private_icc_and_exif(format_name: str) -> None:
    image = Image.new("RGBA", (640, 360), (20, 30, 40, 255))
    metadata = Image.Exif()
    metadata[270] = "A5_PRIVATE_EXIF_CANARY"
    encoded = io.BytesIO()
    image.save(
        encoded,
        format=format_name,
        lossless=True,
        icc_profile=b"A5_PRIVATE_ICC_CANARY",
        exif=metadata,
    )
    canonical = validate_scene_image(encoded.getvalue(), filename="review." + format_name.lower())
    with Image.open(io.BytesIO(canonical.content)) as result:
        assert not {"icc_profile", "exif", "xmp"} & result.info.keys()
        assert result.convert("RGBA").tobytes() == image.tobytes()
    assert b"A5_PRIVATE_EXIF_CANARY" not in canonical.content
    assert b"A5_PRIVATE_ICC_CANARY" not in canonical.content


def test_character_canonicalization_strips_private_metadata_without_pixel_changes() -> None:
    with Image.open(io.BytesIO(_sheet())) as source:
        image = source.convert("RGBA")
    metadata = Image.Exif()
    metadata[270] = "A5_PRIVATE_CHARACTER_EXIF_CANARY"
    encoded = io.BytesIO()
    image.save(
        encoded,
        format="PNG",
        icc_profile=b"A5_PRIVATE_CHARACTER_ICC_CANARY",
        exif=metadata,
    )
    canonical = validate_sprite(encoded.getvalue())
    with Image.open(io.BytesIO(canonical.content)) as result:
        assert not {"icc_profile", "exif", "xmp"} & result.info.keys()
        assert result.convert("RGBA").tobytes() == image.tobytes()
    assert validate_sprite(canonical.content).content == canonical.content


def test_first_paint_policy_is_closed_and_keeps_external_script() -> None:
    result = render_visitor_document(_VISITOR_HTML, color_mode="light", visitor_mode_toggle=False)
    assert result == _VISITOR_HTML.replace(b'owner-mode="system"', b'owner-mode="light"').replace(
        b'visitor-toggle="true"', b'visitor-toggle="false"'
    )


def test_first_paint_reads_one_published_snapshot_and_rejects_unavailable_policy() -> None:
    scene = resolve_scene(
        SceneConfig(color_mode="dark", visitor_mode_toggle=False),
        sprite_content=_sheet(),
        revision=11,
    ).public
    observations: list[str] = []

    @contextmanager
    def published():
        observations.append("acquired")
        yield SimpleNamespace(document=SimpleNamespace(character=SimpleNamespace(scene=scene)))
        observations.append("released")

    manager = SimpleNamespace(status=lambda: SimpleNamespace(active_bundle_id="applied-source"))
    service = SimpleNamespace(published_profile=published)
    document = render_published_visitor_document(
        _VISITOR_HTML, bundle_manager=manager, scene_supplier=lambda: service
    )
    assert b'data-owner-mode="dark"' in document
    assert b'data-visitor-toggle="false"' in document
    assert observations == ["acquired", "released"]
    with pytest.raises(ValueError):
        render_published_visitor_document(
            _VISITOR_HTML, bundle_manager=manager, scene_supplier=lambda: None
        )


def test_gateway_only_serves_the_fixed_bootstrap_and_binds_html_policy(tmp_path: Path) -> None:
    from tests.security.test_visitor_gateway_review import _gateway

    root = tmp_path / "web"
    (root / ".vite").mkdir(parents=True)
    (root / "assets").mkdir()
    (root / "index.html").write_bytes(_VISITOR_HTML)
    (root / "scene-mode.js").write_text("document.documentElement.dataset.visitorMode='light';")
    (root / "private.js").write_text("PRIVATE_ADMIN_CANARY")
    (root / "assets/visitor.js").write_text("visitor")
    (root / ".vite/manifest.json").write_text(
        json.dumps({"index.html": {"isEntry": True, "file": "assets/visitor.js"}})
    )
    app, _ = _gateway(tmp_path, web_dist=root)
    with TestClient(app, base_url="https://fixture.ts.net") as client:
        page = client.get("/")
        assert page.status_code == 200 and page.content == _VISITOR_HTML
        assert page.headers["cache-control"] == "no-store"
        head = client.head("/")
        assert head.status_code == 200 and not head.content
        assert head.headers["content-length"] == str(len(_VISITOR_HTML))
        assert client.get("/scene-mode.js?file=private.js").status_code == 200
        assert client.get("/private.js").status_code == 404
        assert client.get("/.vite/manifest.json").status_code == 404
        (root / "index.html").write_bytes(_VISITOR_HTML + b'data-owner-mode="system"')
        assert client.get("/").status_code == 503


def test_real_html_boundary_injects_onboarding_policy_without_changing_csp(tmp_path: Path) -> None:
    (tmp_path / "index.html").write_bytes(_VISITOR_HTML)
    with TestClient(create_app(web_dist=tmp_path)) as client:
        page = client.get("/")
        assert page.status_code == 200 and page.content == _VISITOR_HTML
        assert page.headers["cache-control"] == "no-store"
        assert "unsafe-inline" not in page.headers["content-security-policy"]
        assert "unsafe-eval" not in page.headers["content-security-policy"]
        head = client.head("/")
        assert head.status_code == 200 and not head.content
        assert head.headers["content-length"] == str(len(_VISITOR_HTML))
        assert client.get("/admin").content == _VISITOR_HTML
        assert client.get("/api/missing").status_code == 404
        (tmp_path / "index.html").write_bytes(_VISITOR_HTML + b'data-owner-mode="system"')
        assert client.get("/").status_code == 503


def test_gateway_prefers_the_dedicated_visitor_entry_and_never_falls_back(tmp_path: Path) -> None:
    from tests.security.test_visitor_gateway_review import _gateway

    root = tmp_path / "web"
    (root / ".vite").mkdir(parents=True)
    (root / "assets").mkdir()
    (root / "index.html").write_text("PRIVATE_ADMIN_ENTRANCE")
    (root / "visitor.html").write_bytes(_VISITOR_HTML)
    (root / "scene-mode.js").write_text("visitor mode bootstrap")
    (root / "assets/admin.js").write_text("PRIVATE_ADMIN_CANARY")
    (root / "assets/visitor.js").write_text("public visitor")
    manifest = {
        "index.html": {"isEntry": True, "file": "assets/admin.js"},
        "visitor.html": {"isEntry": True, "file": "assets/visitor.js"},
    }
    manifest_path = root / ".vite/manifest.json"
    manifest_path.write_text(json.dumps(manifest))
    app, _ = _gateway(tmp_path, web_dist=root)
    with TestClient(app, base_url="https://fixture.ts.net") as client:
        assert client.get("/").content == _VISITOR_HTML
        assert client.get("/assets/visitor.js").status_code == 200
        for private in ("/assets/admin.js", "/index.html", "/visitor.html"):
            assert client.get(private).status_code == 404
    manifest["visitor.html"]["isEntry"] = False
    manifest_path.write_text(json.dumps(manifest))
    closed, _ = _gateway(tmp_path, web_dist=root)
    with TestClient(closed, base_url="https://fixture.ts.net") as client:
        assert client.get("/").status_code == 404
        assert client.get("/assets/admin.js").status_code == 404


def test_primary_public_entrance_uses_visitor_build_and_keeps_admin_entrance(
    tmp_path: Path,
) -> None:
    visitor = _VISITOR_HTML + b"\n<!-- dedicated visitor -->"
    administrator = _VISITOR_HTML + b"\n<!-- private administration -->"
    (tmp_path / "visitor.html").write_bytes(visitor)
    (tmp_path / "index.html").write_bytes(administrator)
    with TestClient(create_app(web_dist=tmp_path)) as client:
        for path in ("/", "/index.html"):
            page = client.get(path)
            assert page.status_code == 200 and page.content == visitor
            head = client.head(path)
            assert head.status_code == 200 and not head.content
            assert head.headers["content-length"] == str(len(visitor))
        assert client.get("/admin").content == administrator


@pytest.mark.parametrize(
    "document,mode,toggle",
    [
        (_VISITOR_HTML, 'dark" onload="alert(1)', True),
        (_VISITOR_HTML, "dark", "false"),
        (_VISITOR_HTML.replace(b'data-owner-mode="system"', b""), "dark", False),
        (_VISITOR_HTML + b'data-visitor-toggle="true"', "light", True),
        (_VISITOR_HTML.replace(b"<html ", b"<body "), "dark", True),
    ],
)
def test_first_paint_policy_rejects_injection_and_ambiguous_markers(
    document: bytes, mode: str, toggle: bool
) -> None:
    with pytest.raises(ValueError, match="invalid visitor document"):
        render_visitor_document(document, color_mode=mode, visitor_mode_toggle=toggle)


def test_scene_migration_rolls_back_and_keeps_existing_faq(tmp_path: Path) -> None:
    database = RuntimeDatabase(tmp_path)
    previous = tuple(m for m in MIGRATIONS if m.version < 31)
    database.initialize(migrations=previous)
    with database.connection() as connection:
        connection.execute(
            "INSERT INTO faq_entries(entry_id,question_key,bundle_id,locale,question,claim_kind) "
            "VALUES ('review-faq','review-key','review-bundle','en','Review?','context')"
        )
    current = next(m for m in MIGRATIONS if m.version == 31)
    broken = Migration(31, current.name, (*current.statements[:2], "INVALID SQL"))
    with pytest.raises(RuntimeDatabaseError):
        database.initialize(migrations=(*previous, broken))
    assert database.schema_version() == 30
    with database.connection() as connection:
        assert (
            connection.execute(
                "SELECT count(*) FROM sqlite_master WHERE name = 'scene_appearance_state'"
            ).fetchone()[0]
            == 0
        )
        assert connection.execute("SELECT question FROM faq_entries").fetchone()[0] == "Review?"
    database.initialize()
    database.initialize()
    with database.connection() as connection:
        row = connection.execute("SELECT * FROM scene_appearance_state").fetchone()
        assert row["singleton"] == 1 and row["issued_revision"] == 0
        assert row["scene_json"] is None and row["journal_json"] is None
        assert connection.execute("SELECT question FROM faq_entries").fetchone()[0] == "Review?"
        connection.execute(
            "UPDATE scene_appearance_state SET issued_revision=1,source_bundle_id='legacy',"
            "sprite_sha256=?,character_revision=0,appearance_revision=1,scene_json='{}'",
            ("a" * 64,),
        )
        assert (
            connection.execute("SELECT character_revision FROM scene_appearance_state").fetchone()[
                0
            ]
            == 0
        )


@pytest.mark.parametrize(
    "assignment,value",
    [
        ("issued_revision", -1),
        ("source_bundle_id", "isolated-binding"),
        ("background_sha256", "a" * 64),
        ("journal_json", "x" * 65537),
        ("singleton", 2),
    ],
    ids=[
        "negative-counter",
        "partial-binding",
        "unpaired-background",
        "large-journal",
        "singleton",
    ],
)
def test_scene_state_database_rejects_partial_or_unbounded_state(
    tmp_path: Path, assignment: str, value: str | int
) -> None:
    database = RuntimeDatabase(tmp_path)
    database.initialize()
    with database.connection() as connection:
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                f"UPDATE scene_appearance_state SET {assignment}=? WHERE singleton=1", (value,)
            )
        assert (
            connection.execute("SELECT issued_revision FROM scene_appearance_state").fetchone()[0]
            == 0
        )


def test_background_draft_database_has_one_known_session_owner(tmp_path: Path) -> None:
    database = RuntimeDatabase(tmp_path)
    database.initialize()
    with database.connection() as connection:
        connection.execute(
            "INSERT INTO admin_sessions(session_hash,csrf_hash,created_at,last_seen_at,"
            "idle_expires_at,absolute_expires_at,session_epoch) VALUES (?,?, 'now','now',"
            "'later','later',0)",
            ("a" * 64, "b" * 64),
        )
        insert = (
            "INSERT INTO scene_background_drafts(draft_id_hash,session_hash,content_sha256,"
            "extension,created_at,expires_at) VALUES (?,?,?,'png','now','later')"
        )
        connection.execute(insert, ("c" * 64, "a" * 64, "d" * 64))
        attempts = (("e" * 64, "a" * 64), ("e" * 64, "f" * 64), ("E" * 64, "a" * 64))
        for draft_id, session in attempts:
            with pytest.raises(sqlite3.IntegrityError):
                connection.execute(insert, (draft_id, session, "d" * 64))
        assert connection.execute("SELECT count(*) FROM scene_background_drafts").fetchone()[0] == 1
        connection.execute("DELETE FROM admin_sessions WHERE session_hash=?", ("a" * 64,))
        assert connection.execute("SELECT count(*) FROM scene_background_drafts").fetchone()[0] == 0


@pytest.mark.parametrize(
    "field,value",
    [("content", "not-configuration"), ("revision", "f" * 64)],
    ids=["content", "digest"],
)
def test_invalid_recovery_copy_cannot_replace_a_valid_draft(
    tmp_path: Path, field: str, value: str
) -> None:
    store = LocalPortfolioStore(tmp_path)
    store.save(
        content=(ROOT / "tests/fixtures/phase2/reponpc.yml").read_text(encoding="utf-8"),
        sprite_base64=None,
        expected_revision=None,
    )
    path = tmp_path / "local-portfolio/draft.json"
    before = path.read_bytes()
    corrupted = json.loads(before)
    corrupted[field] = value
    with store.mutation_lock(), pytest.raises(LocalPortfolioError):
        store.restore_raw_locked(json.dumps(corrupted).encode("utf-8"))
    assert path.read_bytes() == before


def test_concurrent_draft_cleanup_preserves_an_upload_in_progress(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = RuntimeDatabase(tmp_path / "runtime")
    database.initialize()
    with database.connection() as connection:
        for session in ("a" * 64, "b" * 64):
            connection.execute(
                "INSERT INTO admin_sessions(session_hash,csrf_hash,created_at,last_seen_at,"
                "idle_expires_at,absolute_expires_at,session_epoch) VALUES (?,?, 'now','now',"
                "'later','later',0)",
                (session, "c" * 64),
            )
    service = AdminSceneService(
        manager=None,  # type: ignore[arg-type]
        database=database,
        data_directory=tmp_path / "data",
        portfolio=LocalPortfolioStore(tmp_path / "data"),
    )

    def image_content(color: str) -> bytes:
        output = io.BytesIO()
        Image.new("RGBA", (640, 360), color).save(output, "PNG")
        return output.getvalue()

    existing = service.create_background_draft(
        session_hash="a" * 64, content=image_content("black"), filename="old.png"
    )
    written = threading.Event()
    resume = threading.Event()
    persist = service._atomic_content_addressed

    def pause_after_persist(*args: object, **kwargs: object) -> Path:
        result = persist(*args, **kwargs)  # type: ignore[arg-type]
        written.set()
        assert resume.wait(5)
        return result

    monkeypatch.setattr(service, "_atomic_content_addressed", pause_after_persist)
    outcomes: list[dict[str, object]] = []
    errors: list[BaseException] = []

    def upload() -> None:
        try:
            outcomes.append(
                service.create_background_draft(
                    session_hash="b" * 64, content=image_content("white"), filename="new.png"
                )
            )
        except BaseException as exc:
            errors.append(exc)

    def delete() -> None:
        try:
            service.delete_background_draft(
                session_hash="a" * 64, draft_id=str(existing["draft_id"])
            )
        except BaseException as exc:
            errors.append(exc)

    first = threading.Thread(target=upload)
    second = threading.Thread(target=delete)
    first.start()
    try:
        assert written.wait(5)
        second.start()
        second.join(0.25)
    finally:
        resume.set()
        first.join(5)
        if second.ident is not None:
            second.join(5)
    assert not first.is_alive() and not second.is_alive()
    assert not errors and len(outcomes) == 1
    result = service.get_background_draft(
        session_hash="b" * 64, draft_id=str(outcomes[0]["draft_id"])
    )
    assert result.image.width == 640 and result.image.height == 360


def _sheet(first: str = "#000000", remaining: str = "#bcbcbc") -> bytes:
    image = Image.new("RGBA", (256, 448))
    drawing = ImageDraw.Draw(image)
    for row in range(7):
        for column in range(4):
            x, y = column * 64 + 20, row * 64 + 18
            drawing.rectangle(
                (x, y, x + 23, y + 27),
                fill=first if (row, column) == (0, 0) else remaining,
            )
    output = io.BytesIO()
    image.save(output, "PNG")
    return output.getvalue()


def _contrast(first: str, second: str) -> float:
    def luminance(value: str) -> float:
        channels = [int(value[index : index + 2], 16) / 255 for index in (1, 3, 5)]
        linear = [
            channel / 12.92 if channel <= 0.04045 else ((channel + 0.055) / 1.055) ** 2.4
            for channel in channels
        ]
        return sum(
            weight * channel
            for weight, channel in zip((0.2126, 0.7152, 0.0722), linear, strict=True)
        )

    low, high = sorted((luminance(first), luminance(second)))
    return (high + 0.05) / (low + 0.05)


def _registry_source() -> str:
    return (ROOT / "src/reponpc/scene/color_schemes.yml").read_text(encoding="utf-8")


def test_registry_extension_and_alias_need_no_configuration_change() -> None:
    data = yaml.safe_load(_registry_source())
    added = dict(data["schemes"][0])
    added["id"] = "review_future_scheme"
    added["version"] = 7
    data["schemes"].append(added)
    data["aliases"] = {"review_old_name": "review_future_scheme"}
    registry = parse_scene_registry(yaml.safe_dump(data, allow_unicode=True))
    settings = SceneConfig.model_validate(
        {"color_scheme": "review_old_name"}, context={"scene_registry": registry}
    )
    assert settings.color_scheme == "review_future_scheme"
    assert registry.scheme(settings.color_scheme).version == 7
    with pytest.raises(TypeError):
        registry.scheme(settings.color_scheme).light["ink"] = "#ffffff"  # type: ignore[index]


def test_registry_identity_is_cross_platform_and_fallback_honors_explicit_modes() -> None:
    source = _registry_source().replace("\r\n", "\n").replace("\r", "\n")
    unix = parse_scene_registry(source)
    windows = parse_scene_registry(source.replace("\n", "\r\n"))
    assert unix.source_sha256 == windows.source_sha256
    assert fallback_stylesheet(unix) == fallback_stylesheet(windows)
    css = fallback_stylesheet(unix).decode("utf-8")
    assert ':root[data-visitor-mode="light"]' in css
    assert ':root[data-visitor-mode="dark"]' in css
    assert ':root:not([data-visitor-mode="light"]):not([data-visitor-mode="dark"])' in css


def test_nested_duplicate_key_cannot_hide_an_invalid_authored_color() -> None:
    source = _registry_source()
    first_ink = default_scene_registry().scheme("neutral").light["ink"]
    duplicate = source.replace(
        f'ink: "{first_ink}"', f'ink: "#ffffff"\n      ink: "{first_ink}"', 1
    )
    if duplicate == source:
        duplicate = source.replace(
            f"ink: '{first_ink}'", f"ink: '#ffffff'\n      ink: '{first_ink}'", 1
        )
    assert duplicate != source, "fixture must contain the actual authored ink"
    with pytest.raises(SceneRegistryError, match="duplicate"):
        parse_scene_registry(duplicate)


@pytest.mark.parametrize(
    "aliases",
    [
        {"neutral": "ocean"},
        {"cycle_one": "cycle_two", "cycle_two": "cycle_one"},
        {"dangling": "missing_scheme"},
    ],
)
def test_registry_rejects_alias_collisions_cycles_and_missing_successors(
    aliases: dict[str, str],
) -> None:
    data = yaml.safe_load(_registry_source())
    data["aliases"] = aliases
    with pytest.raises(SceneRegistryError):
        parse_scene_registry(yaml.safe_dump(data, allow_unicode=True))


@pytest.mark.parametrize("field", ["template", "source", "glow", "css", "species", "pack"])
def test_scene_settings_reject_retired_or_executable_fields(field: str) -> None:
    with pytest.raises(ValueError):
        SceneConfig.model_validate({field: "review-canary"})


@pytest.mark.parametrize(
    "path",
    [
        "assets/scene/../../private.png",
        "assets/scene/nested/image.png",
        "assets/scene/image.svg",
        "https://example.test/image.png",
        "assets\\scene\\image.png",
    ],
)
def test_scene_background_reference_cannot_escape_the_declared_asset_folder(path: str) -> None:
    with pytest.raises(ValueError):
        SceneConfig.model_validate({"background_path": path})


def test_non_idle_frames_participate_in_the_sheet_edge_average() -> None:
    scene = resolve_scene({}, sprite_content=_sheet(), revision=11).public
    # Equal rectangles have equal edge populations; 27 grey frames and one black.
    average = round(188 * 27 / 28)
    edge = "#" + f"{average:02x}" * 3
    for variant in (scene.themes.light, scene.themes.dark):
        assert _contrast(edge, variant.stage) >= 3.0


@pytest.mark.parametrize("variant,role", [("light", "ink"), ("dark", "accent_ink")])
def test_checksum_matching_public_scene_cannot_contain_failing_contrast(
    variant: str,
    role: str,
) -> None:
    data = resolve_scene({}, sprite_content=_sheet(), revision=11).public.model_dump(mode="json")
    roles = data["themes"][variant]
    roles[role] = roles["surface" if role == "ink" else "accent"]
    with pytest.raises(ValueError):
        PublicScene.model_validate(data)


def test_profile_cannot_claim_another_character_revision_for_its_scene() -> None:
    scene = resolve_scene({}, sprite_content=_sheet(), revision=11).public
    with pytest.raises(ValueError):
        CharacterMetadata(
            mode="builtin",
            asset_url="/api/public/character.png",
            revision=12,
            frame_duration_ms=200,
            movement="none",
            scene=scene,
        )


def test_invalid_packaged_registry_blocks_even_empty_setup_startup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def reject_registry() -> None:
        raise SceneRegistryError("scheme neutral light: contrast ink/surface failed")

    monkeypatch.setattr("reponpc.main.default_scene_registry", reject_registry)
    with pytest.raises(SceneRegistryError, match="contrast"):
        create_app()


@pytest.mark.parametrize("scheme_id", tuple(default_scene_registry().schemes))
def test_character_change_keeps_every_scheme_role_except_stage(scheme_id: str) -> None:
    settings = SceneConfig(color_scheme=scheme_id)
    black = resolve_scene(settings, sprite_content=_sheet("#000000", "#000000"), revision=11)
    white = resolve_scene(settings, sprite_content=_sheet("#ffffff", "#ffffff"), revision=11)
    for variant in ("light", "dark"):
        black_roles = getattr(black.public.themes, variant).model_dump()
        white_roles = getattr(white.public.themes, variant).model_dump()
        assert {role for role in black_roles if black_roles[role] != white_roles[role]} == {"stage"}
        assert _contrast("#000000", black_roles["stage"]) >= 3.0
        assert _contrast("#ffffff", white_roles["stage"]) >= 3.0
        for roles in (black_roles, white_roles):
            for text in ("ink", "muted_ink"):
                for surface in ("background", "surface", "surface_alt"):
                    assert _contrast(roles[text], roles[surface]) >= 4.5
            assert _contrast(roles["accent_ink"], roles["accent"]) >= 4.5
            for foreground in ("accent", "border", "focus"):
                for surface in ("background", "surface", "surface_alt"):
                    assert _contrast(roles[foreground], roles[surface]) >= 3.0


@pytest.mark.parametrize(
    "count,expected",
    [
        (None, None),
        (0, 0),
        (17, 17),
        (2_147_483_647, 2_147_483_647),
        (True, None),
        (-1, None),
        (2_147_483_648, None),
        (1.5, None),
        ("17", None),
    ],
)
def test_repository_snapshot_counts_use_only_the_existing_metadata_request(
    monkeypatch, count, expected
) -> None:
    calls = []
    sha = "a" * 40
    responses = {
        "/repos/owner/repository": {
            "id": "fixture-repository",
            "private": False,
            "archived": False,
            "default_branch": "main",
            "html_url": "https://github.com/owner/repository",
            "language": " Python ",
            "stargazers_count": count,
            "forks_count": True,
        },
        "/repos/owner/repository/commits/main": {"sha": sha},
        f"/repos/owner/repository/git/trees/{sha}?recursive=1": {
            "truncated": False,
            "tree": [],
        },
    }

    def get(_self, path):
        calls.append(path)
        return responses[path]

    monkeypatch.setattr(GitHubSourceResolver, "_get_json", get)
    snapshot = GitHubSourceResolver().resolve(slug="owner/repository", ref=None)
    assert (snapshot.language, snapshot.stars, snapshot.forks) == ("Python", expected, None)
    assert calls == list(responses)
    calls.clear()

    class Transport:
        def request(self, **kwargs):
            path = kwargs["url"].removeprefix("https://api.github.com")
            calls.append(path)
            return GitHubHttpResponse(200, json.dumps(responses[path]).encode(), {})

    resolved = GitHubRESTMetadataResolver(
        transport=Transport(), limiter=GitHubRateLimiter()
    ).resolve_page(selections=[RepositorySelection("owner/repository")])
    assert not resolved.blockers
    archived = resolved.repositories[0]
    assert (archived.language, archived.stars, archived.forks) == (
        snapshot.language,
        snapshot.stars,
        snapshot.forks,
    )
    assert calls == list(responses)[:2]


def test_public_repository_metadata_remains_nullable_and_strict() -> None:
    base = {"slug": "owner/repository", "summary": "Project", "role": "Owner statement", "tags": []}
    legacy = PublicRepository.model_validate(base)
    assert (legacy.language, legacy.stars, legacy.forks) == (None, None, None)
    public = PublicRepository.model_validate({**base, "language": "Python", "stars": 0, "forks": 7})
    assert (public.language, public.stars, public.forks) == ("Python", 0, 7)
    for invalid in (
        {"stars": True},
        {"forks": -1},
        {"stars": 2_147_483_648},
        {"forks": 1.5},
        {"stars": "17"},
        {"language": " "},
        {"language": "x" * 101},
        {"provider": "PRIVATE_METADATA_CANARY"},
    ):
        with pytest.raises(ValueError):
            PublicRepository.model_validate({**base, **invalid})
