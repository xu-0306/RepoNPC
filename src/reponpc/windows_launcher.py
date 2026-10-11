"""Owned loopback server and native-browser console for the Windows distribution."""

from __future__ import annotations

import argparse
import json
import os
import secrets
import socket
import stat
import threading
import time
import webbrowser
from collections.abc import Sequence
from http.client import HTTPConnection
from pathlib import Path
from typing import Any

_START_TIMEOUT = 30.0
_STOP_TIMEOUT = 35.0


class _LauncherError(Exception):
    """An internal failure whose details must not reach the console."""


def _port(value: str) -> int:
    try:
        result = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError("port must be an integer from 0 to 65535") from None
    if not 0 <= result <= 65535:
        raise argparse.ArgumentTypeError("port must be an integer from 0 to 65535")
    return result


def _data_directory(value: Path | None) -> Path:
    if value is None:
        local_data = os.environ.get("LOCALAPPDATA", "")
        if not local_data or not Path(local_data).is_absolute():
            raise _LauncherError
        value = Path(local_data) / "RepoNPC" / "data"
    if not value.is_absolute():
        raise _LauncherError
    return value


def _check_directory(path: Path) -> None:
    for candidate in (*reversed(path.parents), path):
        if candidate.is_symlink() or candidate.is_junction():
            raise _LauncherError
        if candidate.exists() and not candidate.is_dir():
            raise _LauncherError


def _identity_key(data_dir: Path) -> Path:
    private = data_dir / "private"
    _check_directory(private)
    private.mkdir(parents=True, exist_ok=True, mode=0o700)
    key_file = private / "ip-hash-key"
    try:
        descriptor = os.open(
            key_file,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
            0o600,
        )
    except FileExistsError:
        pass
    else:
        with os.fdopen(descriptor, "w", encoding="ascii") as stream:
            stream.write(secrets.token_hex(32))
            stream.flush()
            os.fsync(stream.fileno())
    metadata = key_file.lstat()
    if (
        key_file.is_symlink()
        or key_file.is_junction()
        or not stat.S_ISREG(metadata.st_mode)
        or metadata.st_nlink != 1
        or metadata.st_size != 64
        or (os.name != "nt" and metadata.st_mode & 0o077)
    ):
        raise _LauncherError
    try:
        with key_file.open("rb") as stream:
            encoded = stream.read(65)
        if len(encoded) != 64 or len(bytes.fromhex(encoded.decode("ascii"))) != 32:
            raise _LauncherError
    except (UnicodeError, ValueError):
        raise _LauncherError from None
    return key_file


def _reserve_socket(port: int) -> socket.socket:
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            listener.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        listener.bind(("127.0.0.1", port))
        return listener
    except BaseException:
        listener.close()
        raise


def _environment(data_dir: Path, key_file: Path, port: int) -> dict[str, str]:
    origin = f"http://localhost:{port}"
    return {
        "REPONPC_ENV": "production",
        "REPONPC_DEPLOYMENT_PROFILE": "loopback_evaluation",
        "REPONPC_DATA_DIR": str(data_dir),
        "REPONPC_HOST": "127.0.0.1",
        "REPONPC_PORT": str(port),
        "REPONPC_PUBLIC_BASE_URL": origin,
        "REPONPC_ADMIN_ORIGINS": origin,
        "REPONPC_TRUSTED_HOSTS": "localhost,127.0.0.1",
        "REPONPC_ALLOWED_ORIGINS": "",
        "REPONPC_TRUSTED_PROXY_CIDRS": "",
        "REPONPC_VISITOR_TRUSTED_PROXY_CIDRS": "",
        "REPONPC_VISITOR_GATEWAY_PORT": "8002" if port == 8001 else "8001",
        "REPONPC_LOG_LEVEL": "WARNING",
        "REPONPC_CONFIG_REPOSITORY": "",
        "REPONPC_INDEX_MANIFEST_URL": "",
        "REPONPC_GITHUB_TOKEN": "",
        "REPONPC_GITHUB_TOKEN_FILE": "",
        "REPONPC_CHAT_PROVIDER": "",
        "REPONPC_CHAT_MODEL": "",
        "REPONPC_CHAT_BASE_URL": "",
        "REPONPC_CHAT_API_KEY": "",
        "REPONPC_CHAT_API_KEY_FILE": "",
        "REPONPC_EMBEDDING_PROVIDER": "",
        "REPONPC_EMBEDDING_MODEL": "",
        "REPONPC_EMBEDDING_BASE_URL": "",
        "REPONPC_EMBEDDING_API_KEY": "",
        "REPONPC_EMBEDDING_API_KEY_FILE": "",
        "REPONPC_ADMIN_USERNAME": "",
        "REPONPC_ADMIN_PASSWORD_HASH": "",
        "REPONPC_IP_HASH_KEY": "",
        "REPONPC_IP_HASH_KEY_FILE": str(key_file),
    }


def _load_application(data_dir: Path) -> Any:
    # Import only after the owned socket and isolated deployment environment exist.
    from reponpc.config.environment import load_environment
    from reponpc.main import prepare_application

    settings = load_environment(secret_roots=(data_dir / "private",))
    return prepare_application(settings)


def _make_server(application: Any, port: int) -> Any:
    import uvicorn

    return uvicorn.Server(
        uvicorn.Config(
            getattr(getattr(application, "state", None), "maintenance_host", application),
            host="127.0.0.1",
            port=port,
            proxy_headers=False,
            forwarded_allow_ips="",
            access_log=False,
            log_level="warning",
            timeout_graceful_shutdown=30,
        )
    )


def _healthy(port: int, timeout: float) -> bool:
    connection = HTTPConnection("127.0.0.1", port, timeout=timeout)
    try:
        connection.request("GET", "/healthz")
        response = connection.getresponse()
        if response.status != 200:
            return False
        body = response.read(4097)
        return len(body) <= 4096 and json.loads(body) == {"status": "alive"}
    except (OSError, ValueError):
        return False
    finally:
        connection.close()


def _wait_for_health(port: int, thread: threading.Thread, failed: threading.Event) -> None:
    deadline = time.monotonic() + _START_TIMEOUT
    while thread.is_alive() and not failed.is_set():
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        if _healthy(port, min(1.0, remaining)):
            return
        time.sleep(min(0.1, remaining))
    raise _LauncherError


def _issue_grant(database: Any) -> str:
    from reponpc.admin.auth import issue_admin_local_launch_grant

    return issue_admin_local_launch_grant(database, deployment_profile="loopback_evaluation")


def _open_admin(application: Any, port: int) -> None:
    try:
        grant = _issue_grant(application.state.runtime_database)
        opened = webbrowser.open(f"http://localhost:{port}/admin#local-launch={grant}")
        if not opened:
            print("無法開啟瀏覽器; 輸入 open 重試。 Browser unavailable; enter open to retry.")
    except Exception:
        print("無法開啟管理頁; 輸入 open 重試。 Admin unavailable; enter open to retry.")


def _listener_stopped(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.settimeout(0.5)
        return probe.connect_ex(("127.0.0.1", port)) != 0


def main(argv: Sequence[str] | None = None) -> int:
    """Run the console; smoke-check is a bounded health-only build verification."""

    parser = argparse.ArgumentParser(description="RepoNPC local Windows launcher")
    parser.add_argument("--port", type=_port, default=0)
    parser.add_argument("--data-dir", type=Path)
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--smoke-check", action="store_true", help="check health and exit")
    try:
        options = parser.parse_args(argv)
    except SystemExit as exc:
        return int(exc.code or 0)
    listener = None
    server = None
    thread = None
    saved_environment: dict[str, str] | None = None
    port = 0
    result = 0
    try:
        listener = _reserve_socket(options.port)
        port = listener.getsockname()[1]
        data_dir = _data_directory(options.data_dir)
        key_file = _identity_key(data_dir)
        saved_environment = {
            key: value
            for key, value in os.environ.items()
            if key.startswith("REPONPC_") or key == "BROWSER"
        }
        for key in saved_environment:
            del os.environ[key]
        os.environ.update(_environment(data_dir, key_file, port))
        application = _load_application(data_dir)
        if (
            getattr(application.state, "runtime_storage_usable", False) is not True
            or getattr(application.state, "runtime_database", None) is None
        ):
            raise _LauncherError
        server = _make_server(application, port)
        failed = threading.Event()

        def serve() -> None:
            try:
                server.run(sockets=[listener])
            except BaseException:
                failed.set()

        thread = threading.Thread(target=serve, name="reponpc-loopback", daemon=True)
        thread.start()
        _wait_for_health(port, thread, failed)
        if not options.smoke_check:
            if not options.no_browser:
                _open_admin(application, port)
            while thread.is_alive() and not failed.is_set():
                command = input("o/open 開啟管理頁/Open admin; q/quit 結束/Quit: ").strip().lower()
                if command in {"q", "quit"}:
                    break
                if command in {"o", "open"} and not options.no_browser:
                    _open_admin(application, port)
            if failed.is_set() or not thread.is_alive():
                raise _LauncherError
    except (EOFError, KeyboardInterrupt):
        pass
    except Exception:
        print("RepoNPC 無法啟動。 RepoNPC could not start.")
        result = 2
    finally:
        if server is not None:
            server.should_exit = True
        try:
            if thread is not None:
                thread.join(_STOP_TIMEOUT)
        except KeyboardInterrupt:
            result = 2
        finally:
            if listener is not None:
                listener.close()
        if thread is not None and (thread.is_alive() or not _listener_stopped(port)):
            print("RepoNPC 尚未完成停止。 RepoNPC has not finished stopping.")
            result = 2
        if saved_environment is not None:
            for key in tuple(os.environ):
                if key.startswith("REPONPC_") or key == "BROWSER":
                    del os.environ[key]
            os.environ.update(saved_environment)
    return result


if __name__ == "__main__":
    raise SystemExit(main())
