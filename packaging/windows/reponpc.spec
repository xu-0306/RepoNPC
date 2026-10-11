# Build only with the locked windows-build group; this is an onedir console app.
import stat
import tomllib
from pathlib import Path

from packaging.version import Version
from PyInstaller.building.api import COLLECT, EXE, PYZ
from PyInstaller.building.build_main import Analysis
from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs, copy_metadata
from PyInstaller.utils.win32.versioninfo import (
    FixedFileInfo,
    StringFileInfo,
    StringStruct,
    StringTable,
    VarFileInfo,
    VarStruct,
    VSVersionInfo,
)

ROOT = Path(SPECPATH).absolute().parents[1]  # noqa: F821 - supplied by PyInstaller
WEB = ROOT / "apps" / "web" / "dist"
NOTICES = ROOT / "packaging" / "windows" / "THIRD_PARTY_NOTICES.txt"
PACKAGE = ROOT / "src" / "reponpc"
EXCLUDED = ["torch", "transformers", "sentence_transformers"]


def safe_path(path):
    """Reject links/junctions before resolving or traversing a build input."""
    for item in (path, *path.parents):
        attributes = item.lstat()
        if item.is_symlink() or (
            getattr(attributes, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT
        ):
            raise ValueError("Packaging inputs must not contain symlinks or reparse points")


def safe_files(directory):
    safe_path(directory)
    pending = [directory]
    files = []
    while pending:
        for item in sorted(pending.pop().iterdir()):
            safe_path(item)
            if item.is_dir():
                pending.append(item)
            elif item.is_file():
                files.append(item)
            else:
                raise ValueError("Packaging input must be a regular file or directory")
    return files


safe_path(ROOT / "pyproject.toml")
VERSION = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]
safe_path(ROOT / "packaging" / "windows" / "launch.py")
safe_files(PACKAGE)
safe_path(NOTICES)
if not (WEB / "index.html").is_file() or not (WEB / "visitor.html").is_file():
    raise ValueError("Build the complete Web distribution before freezing")
datas = [
    (str(item), str(Path("web_dist") / item.relative_to(WEB).parent)) for item in safe_files(WEB)
]
# Resource classes, rather than a duplicate registry of every YAML filename.
datas += collect_data_files(
    "reponpc", includes=["**/*.yml", "**/*.yaml", "cards/fonts/*.otf", "cards/fonts/OFL.txt"]
)
datas += copy_metadata("reponpc")
datas.append((str(NOTICES), "."))
if (ROOT / "LICENSE").is_file():
    safe_path(ROOT / "LICENSE")
    datas.append((str(ROOT / "LICENSE"), "."))

native_packages = [
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
]
binaries = []
for package in native_packages:
    binaries += collect_dynamic_libs(package)
    if package.startswith("tree_sitter_"):
        datas += collect_data_files(package, includes=["queries/*.scm"])

a = Analysis(
    [str(ROOT / "packaging" / "windows" / "launch.py")],
    pathex=[str(ROOT / "src")],
    binaries=binaries,
    datas=datas,
    hiddenimports=[
        "reponpc.windows_launcher",
        "onnxruntime.capi.onnxruntime_pybind11_state",
        "tokenizers.tokenizers",
        "cryptography.hazmat.bindings._rust",
        "uvicorn.logging",
        "uvicorn.loops.auto",
        "uvicorn.loops.asyncio",
        "uvicorn.protocols.http.auto",
        "uvicorn.protocols.http.h11_impl",
        "uvicorn.protocols.http.httptools_impl",
        "uvicorn.protocols.websockets.auto",
        "uvicorn.protocols.websockets.websockets_impl",
        "uvicorn.lifespan.on",
        *native_packages,
    ],
    excludes=EXCLUDED,
    noarchive=False,
)

# Inspect final hook output too: a transitive hook must not add owner files or
# bundled model weights. Never collect an entire checkout or dependency extras.
for destination, source, _kind in [*a.datas, *a.binaries]:
    safe_path(Path(source))
    name = Path(destination.replace("\\", "/"))
    if (
        name.suffix.lower()
        in {".onnx", ".onnx_data", ".safetensors", ".gguf", ".pt", ".pth", ".sqlite", ".db"}
        or name.name in {".env", "model.onnx_data", "Constant_7_attr__value", "tokenizer.json"}
        or name.name.startswith(".env.")
        or any(
            part in {"runtime-data", "secrets", "PixelNPC", "release-evidence"}
            for part in name.parts
        )
    ):
        raise ValueError("Forbidden model, runtime, secret, or owner artifact in frozen bundle")

release = Version(VERSION).release
file_version = tuple((*release, 0, 0, 0, 0)[:4])
version_info = VSVersionInfo(
    ffi=FixedFileInfo(
        filevers=file_version,
        prodvers=file_version,
        mask=0x3F,
        flags=0,
        OS=0x40004,
        fileType=1,
        subtype=0,
        date=(0, 0),
    ),
    kids=[
        StringFileInfo(
            [
                StringTable(
                    "040904B0",
                    [
                        StringStruct("FileDescription", "RepoNPC"),
                        StringStruct("FileVersion", VERSION),
                        StringStruct("ProductName", "RepoNPC"),
                        StringStruct("ProductVersion", VERSION),
                        StringStruct("OriginalFilename", "RepoNPC.exe"),
                    ],
                )
            ]
        ),
        VarFileInfo([VarStruct("Translation", [1033, 1200])]),
    ],
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="RepoNPC",
    console=True,
    debug=False,
    strip=False,
    upx=False,
    version=version_info,
)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="RepoNPC")
