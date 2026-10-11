"""Frozen resource/ownership boundaries; no installer or model is run here."""

from __future__ import annotations

import importlib.util
import shutil
import subprocess
import sys
import types
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
SPEC = ROOT / "packaging" / "windows" / "reponpc.spec"
SCRIPT = ROOT / "scripts" / "build_windows.ps1"
LAUNCH = ROOT / "packaging" / "windows" / "launch.py"


def execute_recipe(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    extra_data: str | None = None,
    missing: str | None = None,
) -> dict[str, Any]:
    """Execute real spec code with small file fixtures and inert build APIs."""
    package = tmp_path / "src" / "reponpc"
    fixture_files = {
        "pyproject.toml": '[project]\nname="reponpc"\nversion="2.7.9"\n',
        "packaging/windows/launch.py": "# fixture entry\n",
        "packaging/windows/THIRD_PARTY_NOTICES.txt": "synthetic reviewed notices\n",
        "apps/web/dist/index.html": "admin fixture",
        "apps/web/dist/visitor.html": "visitor fixture",
        "apps/web/dist/assets/app.js": "public fixture",
        "src/reponpc/scene/color_schemes.yml": "registry: fixture",
        "src/reponpc/providers/builtin_embedding_manifest.yml": "manifest: fixture",
        "src/reponpc/chat/policy/person_reference.en.yml": "registry: fixture",
        "src/reponpc/admin/model_catalog.yml": "catalog: []",
        "src/reponpc/cards/fonts/NotoSansCJKtc-Regular.otf": "synthetic font",
        "src/reponpc/cards/fonts/OFL.txt": "synthetic font notice",
        "reponpc-2.7.9.dist-info/METADATA": "Name: reponpc\nVersion: 2.7.9\n",
        "secrets/private-key": "must not be collected",
        "runtime-data/runtime.sqlite": "must not be collected",
        ".env": "SECRET_CANARY=must_not_be_collected",
        "PixelNPC/private-photo.png": "must not be collected",
        "models/model.onnx_data": "must not be collected",
    }
    for relative, content in fixture_files.items():
        if relative == missing:
            continue
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    calls: dict[str, Any] = {"native": []}

    def collect_data_files(name: str, *, includes: list[str]) -> list[tuple[str, str]]:
        if name != "reponpc":
            return []
        paths = {path for pattern in includes for path in package.glob(pattern) if path.is_file()}
        return [
            (str(path), str(Path("reponpc") / path.relative_to(package).parent))
            for path in sorted(paths)
        ]

    def collect_dynamic_libs(name: str) -> list[tuple[str, str]]:
        calls["native"].append(name)
        return []

    def copy_metadata(name: str) -> list[tuple[str, str]]:
        calls["metadata"] = name
        return [(str(tmp_path / "reponpc-2.7.9.dist-info"), ".")]

    def analysis(_scripts: list[str], **kwargs: Any) -> types.SimpleNamespace:
        calls["analysis"] = kwargs
        collected = [
            (str(Path(destination) / Path(source).name), source, "DATA")
            for source, destination in kwargs["datas"]
        ]
        if extra_data:
            source = tmp_path / "injected-hook-file"
            source.write_text("fixture hook output", encoding="utf-8")
            collected.append((extra_data, str(source), "DATA"))
        return types.SimpleNamespace(pure=[], scripts=[], binaries=[], datas=collected)

    def exe(*_args: object, **kwargs: Any) -> None:
        calls["exe"] = kwargs

    def collect(*_args: object, **kwargs: Any) -> None:
        calls["collect"] = kwargs

    modules: dict[str, dict[str, object]] = {
        "PyInstaller": {},
        "PyInstaller.building": {},
        "PyInstaller.building.api": {"COLLECT": collect, "EXE": exe, "PYZ": lambda _a: None},
        "PyInstaller.building.build_main": {"Analysis": analysis},
        "PyInstaller.utils": {},
        "PyInstaller.utils.hooks": {
            "collect_data_files": collect_data_files,
            "collect_dynamic_libs": collect_dynamic_libs,
            "copy_metadata": copy_metadata,
        },
        "PyInstaller.utils.win32": {},
        "PyInstaller.utils.win32.versioninfo": {
            name: (lambda *_a, **_k: None)
            for name in (
                "FixedFileInfo",
                "StringFileInfo",
                "StringStruct",
                "StringTable",
                "VarFileInfo",
                "VarStruct",
                "VSVersionInfo",
            )
        },
    }
    for name, attributes in modules.items():
        module = types.ModuleType(name)
        module.__dict__.update(attributes)
        monkeypatch.setitem(sys.modules, name, module)
    namespace: dict[str, Any] = {"SPECPATH": str(tmp_path / "packaging" / "windows")}
    exec(compile(SPEC.read_text(encoding="utf-8"), str(SPEC), "exec"), namespace)
    calls["namespace"] = namespace
    return calls


def test_recipe_preserves_approved_resources_native_runtime_and_metadata_without_owner_data(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = execute_recipe(tmp_path, monkeypatch)
    namespace = calls["namespace"]
    assert namespace["VERSION"] == "2.7.9"
    assert namespace["file_version"] == (2, 7, 9, 0)
    assert calls["metadata"] == "reponpc"
    inputs = [(Path(source), destination) for source, destination in calls["analysis"]["datas"]]
    assert any(
        source.name == "app.js" and destination == str(Path("web_dist/assets"))
        for source, destination in inputs
    )
    for expected in [
        "color_schemes.yml",
        "builtin_embedding_manifest.yml",
        "person_reference.en.yml",
        "model_catalog.yml",
        "NotoSansCJKtc-Regular.otf",
        "OFL.txt",
        "THIRD_PARTY_NOTICES.txt",
    ]:
        assert any(source.name == expected for source, _destination in inputs)
    assert any(source.name == "reponpc-2.7.9.dist-info" for source, _destination in inputs)
    forbidden = {".env", "private-key", "runtime.sqlite", "private-photo.png", "model.onnx_data"}
    assert not forbidden.intersection(source.name for source, _destination in inputs)
    assert calls["analysis"]["excludes"] == ["torch", "transformers", "sentence_transformers"]
    assert set(calls["native"]) >= {
        "numpy",
        "onnxruntime",
        "tokenizers",
        "cryptography",
        "tree_sitter",
        "tree_sitter_go",
        "tree_sitter_javascript",
        "tree_sitter_python",
        "tree_sitter_rust",
        "tree_sitter_typescript",
    }
    assert "onnxruntime.capi.onnxruntime_pybind11_state" in calls["analysis"]["hiddenimports"]
    assert calls["exe"]["exclude_binaries"] is True
    assert calls["exe"]["console"] is True
    assert calls["collect"]["name"] == "RepoNPC"
    assert not any(source.name == "LICENSE" for source, _destination in inputs)


def test_recipe_includes_an_existing_root_license_without_generating_one(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    license_path = tmp_path / "LICENSE"
    license_path.write_text("Synthetic test license; not a repository license", encoding="utf-8")
    calls = execute_recipe(tmp_path, monkeypatch)
    assert (str(license_path), ".") in calls["analysis"]["datas"]
    assert license_path.read_text(encoding="utf-8") == (
        "Synthetic test license; not a repository license"
    )


@pytest.mark.parametrize(
    "destination",
    [
        "model.onnx",
        "models/model.onnx_data",
        "tokenizer.json",
        "weights.safetensors",
        ".env",
        ".env.production",
        "runtime-data/runtime.sqlite",
        "secrets/master.key",
        "PixelNPC/photo.png",
        "release-evidence/owner-export.zip",
    ],
)
def test_final_hook_output_cannot_inject_models_secrets_or_owner_artifacts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, destination: str
) -> None:
    with pytest.raises(ValueError, match="Forbidden"):
        execute_recipe(tmp_path, monkeypatch, extra_data=destination)


@pytest.mark.parametrize(
    "missing",
    [
        "apps/web/dist/index.html",
        "apps/web/dist/visitor.html",
        "packaging/windows/THIRD_PARTY_NOTICES.txt",
    ],
)
def test_recipe_requires_complete_web_and_explicit_notices(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, missing: str
) -> None:
    with pytest.raises((ValueError, FileNotFoundError)):
        execute_recipe(tmp_path, monkeypatch, missing=missing)


def test_recipe_rejects_symlink_input_without_traversal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    link = tmp_path / "src/reponpc/linked-private-folder"
    link.parent.mkdir(parents=True)
    try:
        link.symlink_to(outside, target_is_directory=True)
    except OSError as exc:
        code = getattr(exc, "winerror", exc.errno)
        pytest.skip(f"Host cannot create a test symlink: {code}")
    with pytest.raises(ValueError, match="symlinks or reparse points"):
        execute_recipe(tmp_path, monkeypatch)


def test_launch_import_is_lazy_and_only_main_calls_the_existing_windows_launcher(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    name = "reponpc.windows_launcher"
    calls: list[str] = []
    module = types.ModuleType(name)

    def launch() -> int:
        calls.append("launch")
        return 17

    module.__dict__["main"] = launch
    monkeypatch.setitem(sys.modules, name, module)
    spec = importlib.util.spec_from_file_location("packaging_launch_fixture", LAUNCH)
    assert spec is not None and spec.loader is not None
    entry = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(entry)
    assert calls == []
    assert entry.main() == 17
    assert calls == ["launch"]


def test_build_script_locks_tools_checks_compiler_and_hashes_only_named_outputs() -> None:
    script = SCRIPT.read_text(encoding="utf-8")
    assert '"sync", "--locked", "--group", "windows-build"' in script
    assert '"install", "--frozen-lockfile"' in script
    assert '"run", "web:build"' in script
    assert '"pyinstaller", "--noconfirm", "--clean"' in script
    assert "tools/generate_windows_notices.py" in script
    assert script.index(
        "tools/generate_windows_notices.py", script.index("Push-Location")
    ) < script.index('"pyinstaller", "--noconfirm"')
    assert "[switch]$SkipInstaller" in script and '[string]$IsccPath = ""' in script
    assert "Inno Setup compiler is required" in script
    assert "#if Ver < EncodeVer(6,3,0)" in script
    assert "DecodeVer(Ver)" in script
    assert "Output=no" in script and "OutputDir={#CompilerPath}" in script
    assert "$compilerProbe | & $compiler" in script
    assert "FileMajorPart" not in script
    assert (
        '"/DAppVersion=$appVersion", "/DBuildRoot=$buildRoot", "/DOutputRoot=$outputRoot"' in script
    )
    assert '"RepoNPC-Setup-$appVersion.exe"' in script
    assert 'Join-Path $repoRoot "dist/windows"' in script
    assert "Refusing to overwrite an unrecognized" in script
    assert "ReparsePoint" in script and "OrdinalIgnoreCase" in script
    assert "Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256" in script
    assert 'Join-Path $outputRoot "SHA256SUMS"' in script
    assert "root LICENSE is missing" in script and "AC-069" in script
    assert "cmd /c" not in script and "Remove-Item -Recurse" not in script
    assert "REPONPC_DATA_DIR" not in script


def test_build_script_parses_with_available_powershell() -> None:
    shell = shutil.which("pwsh") or shutil.which("powershell")
    if shell is None:
        pytest.skip("PowerShell is unavailable on this host")
    command = (
        "$tokens=$null; $errors=$null; "
        "[Management.Automation.Language.Parser]::ParseFile("
        f"'{str(SCRIPT).replace(chr(39), chr(39) * 2)}', [ref]$tokens, [ref]$errors) | Out-Null; "
        "if ($errors.Count) { $errors | ForEach-Object { $_.Message }; exit 1 }"
    )
    result = subprocess.run(
        [shell, "-NoProfile", "-NonInteractive", "-Command", command],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize("existing_output", [False, True])
def test_build_preflight_fails_before_tools_or_mutation_for_missing_compiler_or_unknown_output(
    tmp_path: Path, existing_output: bool
) -> None:
    if sys.platform != "win32":
        pytest.skip("Windows script preflight requires Windows")
    shell = shutil.which("pwsh") or shutil.which("powershell")
    if shell is None:
        pytest.skip("PowerShell is unavailable on this host")
    script = tmp_path / "scripts/build_windows.ps1"
    script.parent.mkdir()
    script.write_text(SCRIPT.read_text(encoding="utf-8"), encoding="utf-8")
    (tmp_path / "src/reponpc").mkdir(parents=True)
    (tmp_path / "apps/web/src").mkdir(parents=True)
    output = tmp_path / "dist/windows"
    sentinel = output / "unrelated-owner-file.txt"
    if existing_output:
        output.mkdir(parents=True)
        sentinel.write_text("preserve", encoding="utf-8")
    escaped_script = str(script).replace("'", "''")
    # Clearing PATH makes compiler/tool availability deterministic. No build
    # command may run and no output may be written after these preflight errors.
    result = subprocess.run(
        [shell, "-NoProfile", "-NonInteractive", "-Command", f"$env:PATH=''; & '{escaped_script}'"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        timeout=30,
    )
    assert result.returncode != 0
    message = result.stdout + result.stderr
    expected = (
        "Refusing to overwrite an unrecognized"
        if existing_output
        else "Inno Setup compiler is required"
    )
    assert expected in message
    if existing_output:
        assert sentinel.read_text(encoding="utf-8") == "preserve"
        assert list(output.iterdir()) == [sentinel]
    else:
        assert not output.exists()
