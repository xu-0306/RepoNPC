"""Notice generation is offline, bounded, and pinned to installed build inputs."""

from __future__ import annotations

import hashlib
import json
from importlib import metadata
from os import PathLike
from pathlib import Path

import pytest

from tools import generate_windows_notices as notices


class FixtureDistribution(metadata.Distribution):
    def __init__(
        self,
        root: Path,
        version: str = "1.0",
        requires: tuple[str, ...] = (),
        files: tuple[str, ...] = (),
    ) -> None:
        self.root = root
        self.fixture_version = version
        self.fixture_requires = requires
        self.fixture_files = files

    @property
    def version(self) -> str:
        return self.fixture_version

    @property
    def requires(self) -> list[str]:
        return list(self.fixture_requires)

    @property
    def files(self) -> list[metadata.PackagePath]:
        return [metadata.PackagePath(name) for name in self.fixture_files]

    def locate_file(self, path: str | PathLike[str]) -> Path:
        return self.root / path

    def read_text(self, filename: str) -> str | None:
        path = self.root / filename
        return path.read_text(encoding="utf-8") if path.is_file() else None


def _sources(root: Path, records: list[dict[str, str]] | None = None) -> Path:
    directory = root / "packaging/windows/licenses"
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "sources.json").write_text(json.dumps(records or []), encoding="utf-8")
    return directory


def _record(name: str = "unseen-runtime", version: str = "1.0") -> dict[str, str]:
    return {
        "ecosystem": "python",
        "name": name,
        "version": version,
        "source": "https://example.org/upstream/v1.0/LICENSE",
        "file": "upstream-1.0-LICENSE.txt",
        "sha256": hashlib.sha256(b"authored fixture license\n").hexdigest(),
    }


def _package(directory: Path, name: str, version: str, **extra: object) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "package.json").write_text(
        json.dumps({"name": name, "version": version, **extra}), encoding="utf-8"
    )


def test_runtime_graph_follows_markers_and_extras_without_indexer_or_dev(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    graph = {
        "reponpc": FixtureDistribution(
            tmp_path,
            requires=(
                "server[standard]>=1",
                'weight-loader; extra == "indexer"',
                'pytest; extra == "dev"',
                'foreign-platform; sys_platform == "never-platform"',
            ),
        ),
        "server": FixtureDistribution(
            tmp_path,
            requires=("httpx", 'transport; extra == "standard"', 'docs; extra == "docs"'),
        ),
        "transport": FixtureDistribution(tmp_path, requires=("server",)),
        "httpx": FixtureDistribution(tmp_path),
        "pyinstaller": FixtureDistribution(tmp_path, requires=("hook-library",)),
        "hook-library": FixtureDistribution(tmp_path),
    }
    requested: list[str] = []

    def distribution(name: str) -> metadata.Distribution:
        requested.append(name)
        return graph[name]

    monkeypatch.setattr(notices.metadata, "distribution", distribution)

    assert set(notices._python_distributions()) == set(graph)
    assert not {"weight-loader", "pytest", "foreign-platform", "docs"} & set(requested)
    assert "httpx" in requested  # A runtime transitively required package stays included.


def test_python_preserves_nested_vendored_notices_and_licence_spelling(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _sources(tmp_path)
    (tmp_path / "LICENSE.txt").write_text("Python runtime license", encoding="utf-8")
    files = ("pkg/LICENSE", "pkg/ThirdPartyNotices.txt", "pkg/vendor/LICENCE")
    for name in files:
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"realistic fixture for {name}", encoding="utf-8")
    dist = FixtureDistribution(tmp_path, "7.3", files=files)
    monkeypatch.setattr(notices.sys, "base_prefix", str(tmp_path))
    monkeypatch.setattr(notices, "_python_distributions", lambda: {"synthetic-runtime": dist})

    parts = notices.python_notices(tmp_path)

    assert len(parts) == 4
    assert {text for _, text in parts[1:]} == {f"realistic fixture for {name}" for name in files}
    assert all(str(tmp_path) not in label for label, _ in parts)


def test_missing_python_license_fails_before_output_is_written(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _sources(tmp_path)
    (tmp_path / "LICENSE.txt").write_text("Python runtime license", encoding="utf-8")
    monkeypatch.setattr(notices.sys, "base_prefix", str(tmp_path))
    monkeypatch.setattr(
        notices, "_python_distributions", lambda: {"unseen-runtime": FixtureDistribution(tmp_path)}
    )

    with pytest.raises(ValueError, match="no installed license text for unseen-runtime"):
        notices.python_notices(tmp_path)


def test_local_supplement_requires_exact_package_version_and_checksum(tmp_path: Path) -> None:
    record = _record()
    directory = _sources(tmp_path, [record])
    license_file = directory / record["file"]
    license_file.write_bytes(b"authored fixture license\n")

    assert notices._supplements("python", "unseen-runtime", "2.0", tmp_path) == []
    assert notices._supplements("web", "unseen-runtime", "1.0", tmp_path) == []
    parts = notices._supplements("python", "unseen-runtime", "1.0", tmp_path)
    assert len(parts) == 1
    assert parts[0][1] == "authored fixture license"
    assert record["source"] in parts[0][0]
    assert record["sha256"] in parts[0][0]
    license_file.write_text("tampered fixture", encoding="utf-8")
    with pytest.raises(ValueError, match="checksum mismatch"):
        notices._supplements("python", "unseen-runtime", "1.0", tmp_path)


@pytest.mark.parametrize("filename", ["../LICENSE", "..\\LICENSE", "C:LICENSE", ".", ".."])
def test_supplement_manifest_cannot_read_other_paths(tmp_path: Path, filename: str) -> None:
    record = _record()
    record["file"] = filename
    _sources(tmp_path, [record])

    with pytest.raises(ValueError, match="invalid notice source record"):
        notices._supplements("python", "unseen-runtime", "1.0", tmp_path)


def test_shipped_supplements_are_pinned_and_match_recorded_source_bytes() -> None:
    directory = notices.ROOT / "packaging/windows/licenses"
    records = json.loads((directory / "sources.json").read_text(encoding="utf-8"))

    assert records
    for record in records:
        content = (directory / record["file"]).read_bytes()
        assert hashlib.sha256(content).hexdigest() == record["sha256"]
        assert len(content) <= notices.MAX_TEXT_BYTES
        assert len(content.decode("utf-8")) > 500  # Full text, not an SPDX identifier.
        assert notices._supplements(
            record["ecosystem"], record["name"], record["version"], notices.ROOT
        )


def test_web_uses_installed_production_dependencies_and_pinned_supplement(tmp_path: Path) -> None:
    record = _record("@fixture/icons", "4.2")
    record["ecosystem"] = "web"
    directory = _sources(tmp_path, [record])
    (directory / record["file"]).write_bytes(b"authored fixture license\n")
    web = tmp_path / "apps/web"
    _package(
        web,
        "fixture-web",
        "1.0",
        dependencies={"@fixture/icons": "4.2", "widget": "1.5"},
        devDependencies={"typescript": "9.0"},
    )
    _package(web / "node_modules/@fixture/icons", "@fixture/icons", "4.2")
    widget = web / "node_modules/widget"
    _package(widget, "widget", "1.5", dependencies={"child": "1.0"})
    (widget / "LICENSE").write_text("widget license", encoding="utf-8")
    child = widget / "node_modules/child"
    _package(child, "child", "1.0")
    (child / "COPYING").write_text("child license", encoding="utf-8")

    parts = notices.web_notices(tmp_path)

    assert len(parts) == 3
    assert {text for _, text in parts} == {
        "authored fixture license",
        "widget license",
        "child license",
    }
    assert "typescript" not in notices.render_notices(parts)
    _package(web / "node_modules/@fixture/icons", "@fixture/icons", "4.3")
    with pytest.raises(ValueError, match="no Web runtime license text"):
        notices.web_notices(tmp_path)


@pytest.mark.parametrize("problem", ["missing", "identity", "license"])
def test_web_dependency_errors_fail_closed(tmp_path: Path, problem: str) -> None:
    _sources(tmp_path)
    web = tmp_path / "apps/web"
    _package(web, "fixture-web", "1.0", dependencies={"widget": "1.0"})
    if problem != "missing":
        _package(web / "node_modules/widget", "other" if problem == "identity" else "widget", "1.0")

    with pytest.raises(ValueError):
        notices.web_notices(tmp_path)


@pytest.mark.parametrize("content", [b"", b"\xff", b"binary\x00text", b"\xef\xbb\xbfMIT"])
def test_text_rejects_empty_binary_or_non_regular_utf8(tmp_path: Path, content: bytes) -> None:
    path = tmp_path / "LICENSE"
    path.write_bytes(content)

    with pytest.raises(ValueError, match="UTF-8"):
        notices._text(path)


def test_text_read_is_bounded_and_normalizes_newlines(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    assert notices.MAX_TEXT_BYTES == 8 * 1024 * 1024
    monkeypatch.setattr(notices, "MAX_TEXT_BYTES", 32)
    path = tmp_path / "LICENSE"
    path.write_bytes(b"x" * 33)
    with pytest.raises(ValueError, match="too large"):
        notices._text(path)
    path.write_bytes(b"x" * 32)
    assert notices._text(path) == "x" * 32
    path.write_bytes("  中文\r\nlicense\r\n".encode())
    assert notices._text(path) == "中文\nlicense"
    with pytest.raises(ValueError, match="missing"):
        notices._text(tmp_path / "missing")


def test_render_is_deterministic_with_hashes_and_no_timestamp_or_host_path() -> None:
    parts = [("package-z 2.0", "license z"), ("package-a 1.0", "license a")]

    rendered = notices.render_notices(parts)

    assert rendered == notices.render_notices(list(reversed(parts)))
    assert hashlib.sha256(b"license a").hexdigest() in rendered
    assert "owner artwork or model weights" in rendered
    assert str(notices.ROOT) not in rendered
    assert "Generated at" not in rendered


def test_render_rejects_oversized_combined_output(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(notices, "MAX_TEXT_BYTES", 1024)

    with pytest.raises(ValueError, match="combined notices are too large"):
        notices.render_notices([("package 1.0", "x" * 1024)])


def test_failed_collection_preserves_existing_output(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    output = tmp_path / "THIRD_PARTY_NOTICES.txt"
    output.write_bytes(b"last complete notices\n")

    def fail() -> list[tuple[str, str]]:
        raise ValueError("no installed license text for unseen-runtime")

    monkeypatch.setattr(notices, "python_notices", fail)
    monkeypatch.setattr(
        notices.sys, "argv", ["generate_windows_notices.py", "--output", str(output)]
    )
    with pytest.raises(ValueError, match="no installed license text"):
        notices.main()
    assert output.read_bytes() == b"last complete notices\n"


@pytest.mark.parametrize("version", ["4.70.0", "9.0.0"])
def test_source_locator_is_shipped_and_version_change_requires_review(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, version: str
) -> None:
    monkeypatch.setattr(notices, "ROOT", tmp_path)
    monkeypatch.setattr(notices, "python_notices", lambda: [])
    monkeypatch.setattr(notices, "web_notices", lambda: [])
    monkeypatch.setattr(notices.metadata, "version", lambda _name: version)
    directory = _sources(tmp_path)
    (directory / "SOURCE_AVAILABILITY.txt").write_text(
        "fixture MPL covered source https://example.org/v4.70.0/source\n", encoding="utf-8"
    )
    font = tmp_path / "src/reponpc/cards/fonts"
    font.mkdir(parents=True)
    (font / "OFL.txt").write_text("fixture font license\n", encoding="utf-8")
    output = tmp_path / "notices.txt"
    output.write_bytes(b"previous complete notices\n")
    monkeypatch.setattr(notices.sys, "argv", ["notices", "--output", str(output)])
    if version == "4.70.0":
        notices.main()
        assert "fixture MPL covered source" in output.read_text(encoding="utf-8")
    else:
        with pytest.raises(ValueError, match="review source availability"):
            notices.main()
        assert output.read_bytes() == b"previous complete notices\n"
