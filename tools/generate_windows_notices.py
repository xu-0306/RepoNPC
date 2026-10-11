"""Reproduce Windows third-party notices from the locked installed build inputs."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata as metadata
import json
import re
import sys
from pathlib import Path

from packaging.requirements import Requirement

ROOT = Path(__file__).resolve().parents[1]
LICENSE_NAME = re.compile(
    r"^(licen[sc]e|copying|notice|third[-_ ]?party[-_ ]?notices)", re.IGNORECASE
)
MAX_TEXT_BYTES = 8 * 1024 * 1024


def _bytes(path: Path) -> bytes:
    try:
        if not path.is_file():
            raise ValueError("notice input is missing")
        with path.open("rb") as stream:
            content = stream.read(MAX_TEXT_BYTES + 1)
    except OSError:
        raise ValueError("notice input is unreadable") from None
    if len(content) > MAX_TEXT_BYTES:
        raise ValueError("notice input is too large")
    return content


def _decode(content: bytes) -> str:
    try:
        text = content.decode("utf-8", errors="strict").replace("\r\n", "\n").strip()
    except UnicodeDecodeError:
        raise ValueError("notice input must be UTF-8 text") from None
    if not text or "\x00" in text or "\ufeff" in text:
        raise ValueError("notice input must be nonempty regular UTF-8 text")
    return text


def _text(path: Path) -> str:
    return _decode(_bytes(path))


def _supplements(ecosystem: str, name: str, version: str, root: Path) -> list[tuple[str, str]]:
    """Use authored exact-version local supplements; never fetch a missing license."""
    directory = root / "packaging/windows/licenses"
    records = json.loads(_text(directory / "sources.json"))
    if not isinstance(records, list) or len(records) > 64:
        raise ValueError("invalid notice source manifest")
    result: list[tuple[str, str]] = []
    for record in records:
        if (
            not isinstance(record, dict)
            or set(record) != {"ecosystem", "name", "version", "source", "file", "sha256"}
            or not all(isinstance(value, str) and value for value in record.values())
            or record["ecosystem"] not in {"python", "web"}
            or not record["source"].startswith("https://")
            or not re.fullmatch(r"[a-f0-9]{64}", record["sha256"])
            or record["file"] in {".", ".."}
            or any(character in record["file"] for character in "/\\:")
        ):
            raise ValueError("invalid notice source record")
        if (record["ecosystem"], record["name"], record["version"]) != (ecosystem, name, version):
            continue
        content = _bytes(directory / record["file"])
        if hashlib.sha256(content).hexdigest() != record["sha256"]:
            raise ValueError(f"license supplement checksum mismatch for {name} {version}")
        result.append(
            (
                f"{name} {version} / {record['file']}\n"
                f"Source: {record['source']}\nSource SHA-256: {record['sha256']}",
                _decode(content),
            )
        )
    return result


def _python_distributions() -> dict[str, metadata.Distribution]:
    """Follow runtime requirements and active extras, excluding development tools."""
    pending: list[tuple[str, frozenset[str]]] = [
        ("reponpc", frozenset()),
        ("pyinstaller", frozenset()),
    ]
    visited: set[tuple[str, frozenset[str]]] = set()
    distributions: dict[str, metadata.Distribution] = {}
    while pending:
        name, extras = pending.pop()
        normalized = re.sub(r"[-_.]+", "-", name).lower()
        key = normalized, extras
        if key in visited:
            continue
        visited.add(key)
        distribution = metadata.distribution(name)
        distributions[normalized] = distribution
        for raw in distribution.requires or ():
            requirement = Requirement(raw)
            if requirement.marker is not None and not any(
                requirement.marker.evaluate({"extra": extra}) for extra in {"", *extras}
            ):
                continue
            pending.append((requirement.name, frozenset(requirement.extras)))
    return distributions


def python_notices(root: Path = ROOT) -> list[tuple[str, str]]:
    result = [
        (f"Python runtime {sys.version.split()[0]}", _text(Path(sys.base_prefix) / "LICENSE.txt"))
    ]
    for name, distribution in sorted(_python_distributions().items()):
        if name == "reponpc":
            continue  # A missing owner project license is a separate release gate.
        licenses = sorted(
            (item for item in distribution.files or () if LICENSE_NAME.match(Path(item).name)),
            key=str,
        )
        supplements = _supplements("python", name, distribution.version, root)
        if not licenses and not supplements:
            raise ValueError(f"no installed license text for {name}")
        for item in licenses:
            path = distribution.locate_file(item)
            if not isinstance(path, Path):
                raise ValueError(f"license must be an installed regular file for {name}")
            result.append((f"{name} {distribution.version} / {item}", _text(path)))
        result.extend(supplements)
    return result


def web_notices(root: Path = ROOT) -> list[tuple[str, str]]:
    web = root / "apps" / "web"
    manifest = json.loads(_text(web / "package.json"))
    pending = [(name, web) for name in manifest["dependencies"]]
    visited: set[Path] = set()
    result: list[tuple[str, str]] = []
    while pending:
        name, importer = pending.pop()
        directory = next(
            (
                parent / "node_modules" / name
                for parent in (importer, *importer.parents)
                if (parent / "node_modules" / name / "package.json").is_file()
            ),
            None,
        )
        if directory is None:
            raise ValueError(f"Web runtime dependency is missing: {name}")
        directory = directory.resolve()
        if directory in visited:
            continue
        visited.add(directory)
        package = json.loads(_text(directory / "package.json"))
        if package["name"] != name:
            raise ValueError(f"Web runtime package identity mismatch: {name}")
        licenses = sorted(
            (
                item
                for item in directory.iterdir()
                if item.is_file() and LICENSE_NAME.match(item.name)
            ),
            key=lambda item: item.name,
        )
        supplements = _supplements("web", name, package["version"], root)
        if not licenses and not supplements:
            raise ValueError(f"no Web runtime license text for {name}")
        result.extend(
            (f"{name} {package['version']} / {item.name}", _text(item)) for item in licenses
        )
        result.extend(supplements)
        pending.extend((child, directory) for child in package.get("dependencies", {}))
    return sorted(result)


def render_notices(parts: list[tuple[str, str]]) -> str:
    heading = (
        "RepoNPC Windows local-build third-party notices\n"
        "Generated by tools/generate_windows_notices.py from installed locked inputs.\n"
        "This file does not grant a license for owner artwork or model weights.\n"
        "RepoNPC root LICENSE and final release review remain separate gates.\n"
    )
    chunks = [heading]
    total = len(heading.encode("utf-8"))
    for name, text in sorted(parts):
        chunk = (
            f"\n{'=' * 72}\n{name}\n"
            f"Normalized text SHA-256: {hashlib.sha256(text.encode('utf-8')).hexdigest()}\n"
            f"{'=' * 72}\n{text}\n"
        )
        total += len(chunk.encode("utf-8"))
        if total > MAX_TEXT_BYTES:
            raise ValueError("combined notices are too large")
        chunks.append(chunk)
    return "".join(chunks)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    options = parser.parse_args()
    parts = python_notices() + web_notices()
    # A source locator is required alongside the full MPL text for the frozen
    # unmodified tqdm files. Keep it pinned to the actual installed input.
    if metadata.version("tqdm") != "4.70.0":
        raise ValueError("review source availability for the locked tqdm version")
    parts.append(
        (
            "Locked source availability",
            _text(ROOT / "packaging/windows/licenses/SOURCE_AVAILABILITY.txt"),
        )
    )
    parts.append(
        ("NotoSansCJKtc-Regular.otf / SIL OFL", _text(ROOT / "src/reponpc/cards/fonts/OFL.txt"))
    )
    options.output.parent.mkdir(parents=True, exist_ok=True)
    options.output.write_text(render_notices(parts), encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
