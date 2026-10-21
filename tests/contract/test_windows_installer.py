"""Static recipe boundaries; these do not prove a clean Windows installation."""

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
RECIPE = ROOT / "packaging" / "windows" / "reponpc.iss"
BUILD_SCRIPT = ROOT / "scripts" / "build_windows.ps1"


def _recipe() -> str:
    return RECIPE.read_text(encoding="utf-8-sig")


def _sections() -> dict[str, list[str]]:
    sections: dict[str, list[str]] = {}
    current: list[str] | None = None
    for raw_line in _recipe().splitlines():
        line = raw_line.strip()
        if not line or line.startswith((";", "#")):
            continue
        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1]
            assert section not in sections, f"duplicate section: {section}"
            current = sections.setdefault(section, [])
        else:
            assert current is not None, f"unexpected recipe line: {line}"
            current.append(line)
    return sections


def _setup() -> dict[str, str]:
    settings: dict[str, str] = {}
    for line in _sections()["Setup"]:
        key, value = line.split("=", 1)
        assert key not in settings, f"duplicate setting: {key}"
        settings[key] = value
    return settings


def _entry(line: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    for match in re.finditer(r'(\w+):\s*("[^"]*"|[^;]+)(?:;|$)', line):
        key, value = match.groups()
        assert key not in fields, f"duplicate entry field: {key}"
        fields[key] = value.strip().strip('"')
    assert fields, f"unrecognized entry: {line}"
    return fields


@pytest.mark.parametrize("name", ["AppVersion", "BuildRoot", "OutputRoot"])
def test_build_inputs_fail_closed_when_missing_or_empty(name: str) -> None:
    recipe = _recipe()
    missing = rf"#ifndef {name}\s+#error [^\n]+\s+#endif"
    empty = rf'#if {name} == ""\s+#error [^\n]+\s+#endif'

    assert re.search(missing, recipe)
    assert re.search(empty, recipe)
    assert not re.search(rf"#define\s+{name}\b", recipe)


def test_recipe_requires_a_built_launcher_before_compilation() -> None:
    assert re.search(
        r'#if !FileExists\(BuildRoot \+ "\\RepoNPC\.exe"\)\s+#error [^\n]+\s+#endif',
        _recipe(),
    )


def test_version_and_output_use_only_supplied_build_metadata() -> None:
    setup = _setup()

    assert setup["AppId"] == "{{9B5F80E7-BE26-49B4-9939-9F85D69FF4EC}"
    assert setup["AppName"] == "RepoNPC"
    assert setup["AppVersion"] == "{#AppVersion}"
    assert setup["OutputBaseFilename"] == "RepoNPC-Setup-{#AppVersion}"
    assert setup["OutputDir"] == "{#OutputRoot}"
    assert "LicenseFile" not in setup


def test_install_is_per_user_on_native_x64_windows_11() -> None:
    setup = _setup()

    assert setup["PrivilegesRequired"] == "lowest"
    assert "PrivilegesRequiredOverridesAllowed" not in setup
    assert setup["ArchitecturesAllowed"] == "x64compatible and not arm64"
    assert setup["ArchitecturesInstallIn64BitMode"] == "x64compatible"
    assert setup["MinVersion"] == "10.0.22000"
    assert setup["DefaultDirName"] == r"{localappdata}\Programs\RepoNPC"
    assert setup["DefaultGroupName"] == "RepoNPC"
    assert setup["Uninstallable"] == "yes"


def test_onedir_files_upgrade_only_inside_program_directory() -> None:
    files = [_entry(line) for line in _sections()["Files"]]

    assert len(files) == 1
    assert files[0]["Source"] == r"{#BuildRoot}\*"
    assert files[0]["DestDir"] == "{app}"
    assert set(files[0]["Flags"].split()) == {
        "ignoreversion",
        "recursesubdirs",
        "createallsubdirs",
    }


def test_shortcuts_target_launcher_with_optional_desktop_icon() -> None:
    sections = _sections()
    tasks = [_entry(line) for line in sections["Tasks"]]
    icons = [_entry(line) for line in sections["Icons"]]

    assert len(tasks) == 1
    assert tasks[0]["Name"] == "desktopicon"
    assert set(tasks[0]["Flags"].split()) == {"unchecked"}
    assert {icon["Name"] for icon in icons} == {
        r"{group}\RepoNPC",
        r"{group}\RepoNPC" "\uff08正式模式\uff09",
        r"{autodesktop}\RepoNPC",
    }
    for icon in icons:
        assert icon["Filename"] == r"{app}\RepoNPC.exe"
        assert icon["WorkingDir"] == "{app}"
        if icon["Name"] == r"{group}\RepoNPC" "\uff08正式模式\uff09":
            assert icon["Parameters"] == "--profile production"
        else:
            assert "Parameters" not in icon
        if icon["Name"].startswith("{autodesktop}"):
            assert icon["Tasks"] == "desktopicon"
        else:
            assert "Tasks" not in icon


def test_launch_is_opt_in_and_never_runs_in_silent_install() -> None:
    runs = [_entry(line) for line in _sections()["Run"]]

    assert _setup()["RestartApplications"] == "no"
    assert len(runs) == 1
    assert runs[0]["Filename"] == r"{app}\RepoNPC.exe"
    assert runs[0]["WorkingDir"] == "{app}"
    assert "Parameters" not in runs[0]
    assert set(runs[0]["Flags"].split()) == {
        "postinstall",
        "nowait",
        "skipifsilent",
        "unchecked",
    }


def test_install_and_uninstall_cannot_manage_runtime_data_or_external_operations() -> None:
    sections = _sections()

    # An allowlist rules out custom uninstall deletion, Pascal scripting,
    # registry/service changes, downloads, and extra filesystem destinations.
    assert set(sections) == {"Setup", "Tasks", "Files", "Icons", "Run"}
    assert not {"UninstallDelete", "InstallDelete", "UninstallRun", "Code", "Dirs"} & set(sections)
    active = "\n".join(line for lines in sections.values() for line in lines).casefold()
    for forbidden in (
        r"{localappdata}\reponpc\data",
        "runtime.sqlite",
        "model-secrets",
        "bge-m3",
        "http:",
        "https:",
        "powershell",
        "cmd.exe",
        "gateway",
        "tailscale",
        "deleteafterinstall",
        "uninsneveruninstall",
    ):
        assert forbidden not in active


def test_compiler_preflight_uses_its_own_encoded_version_without_output() -> None:
    script = BUILD_SCRIPT.read_text(encoding="utf-8")
    match = re.search(r"\$compilerProbe\s*=\s*@'\n(.*?)\n'@", script, re.DOTALL)
    assert match is not None, "ISPP stdin preflight is required"
    probe = match.group(1)

    assert "#pragma option -c-" not in probe
    assert re.search(r"#if\s+(?:Ver|PREPROCVER)\s*<\s*EncodeVer\(6,\s*3,\s*0\)", probe)
    assert "#error" in probe
    assert re.search(r"DecodeVer\((?:Ver|PREPROCVER)\)", probe)
    assert "[Setup]" in probe
    assert re.search(r"^Output=no$", probe, re.MULTILINE)
    assert re.search(r"^OutputDir=\{#CompilerPath\}$", probe, re.MULTILINE)
    assert "FileVersionRaw" not in script
    assert "ProductVersionRaw" not in script
    assert re.search(r'\$compilerProbe\s*\|\s*&\s*\$compiler\s+"-"', script)


def test_compiler_rejection_precedes_dependency_installs_and_output_mutation() -> None:
    script = BUILD_SCRIPT.read_text(encoding="utf-8")
    probe_call = re.search(r'\$compilerProbe\s*\|\s*&\s*\$compiler\s+"-"', script)
    assert probe_call is not None
    preflight_end = script.index("$previousPyinstallerConfig")
    preflight_result = script[probe_call.end() : preflight_end]
    assert re.search(r"if\s*\(\$LASTEXITCODE\s+-ne\s+0\)\s*\{\s*throw", preflight_result)
    for operation in (
        'Invoke-BuildCommand "uv" @("sync"',
        'Invoke-BuildCommand "pnpm"',
        "[IO.Directory]::CreateDirectory($outputRoot)",
        "[IO.File]::WriteAllText($marker",
    ):
        assert script.index(operation) > preflight_end
