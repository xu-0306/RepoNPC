"""Launcher tests never use installed files, owner data, or an actual browser."""

from __future__ import annotations

import hashlib
import json
import logging
import os
import socket
import sys
import threading
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from reponpc import windows_launcher as launcher
from reponpc.admin.auth import (
    AdminSessionService,
    admin_owner_state,
    issue_admin_local_launch_grant,
    set_admin_recovery_password,
)
from reponpc.config import private_files
from reponpc.runtime.database import RuntimeDatabase


class FakeServer:
    def __init__(self) -> None:
        self.should_exit = False
        self.sockets: list[socket.socket] = []

    def run(self, *, sockets: list[socket.socket]) -> None:
        self.sockets = sockets
        while not self.should_exit:
            threading.Event().wait(0.001)


@pytest.fixture
def harness(monkeypatch: pytest.MonkeyPatch) -> SimpleNamespace:
    state = SimpleNamespace(runtime_storage_usable=True, runtime_database=object())
    app = SimpleNamespace(state=state)
    server = FakeServer()
    observed: dict[str, str] = {}
    ports: list[int] = []
    urls: list[str] = []
    grants: list[object] = []

    def load(data_dir: Path) -> Any:
        observed.update(os.environ)
        assert os.environ["REPONPC_DATA_DIR"] == str(data_dir)
        port = int(os.environ["REPONPC_PORT"])
        ports.append(port)
        with socket.socket() as competitor, pytest.raises(OSError):
            competitor.bind(("127.0.0.1", port))
        return app

    def grant(database: object) -> str:
        grants.append(database)
        return f"example-not-secret-grant-{len(grants)}"

    def browser(url: str) -> bool:
        urls.append(url)
        return True

    monkeypatch.setattr(launcher, "_load_application", load)
    monkeypatch.setattr(launcher, "_make_server", lambda application, port: server)
    monkeypatch.setattr(launcher, "_healthy", lambda port, timeout: True)
    monkeypatch.setattr(launcher, "_issue_grant", grant)
    monkeypatch.setattr(launcher.webbrowser, "open", browser)
    monkeypatch.setattr("builtins.input", lambda prompt: "q")
    return SimpleNamespace(
        app=app, server=server, observed=observed, ports=ports, urls=urls, grants=grants
    )


def arguments(tmp_path: Path, *extra: str) -> list[str]:
    return ["--data-dir", str(tmp_path / "data"), *extra]


def test_reserved_socket_fresh_browser_grants_and_shutdown(
    harness: SimpleNamespace, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: Any
) -> None:
    commands = iter(["o", "OPEN", "quit"])
    monkeypatch.setattr("builtins.input", lambda prompt: next(commands))
    assert launcher.main(arguments(tmp_path)) == 0
    port = harness.ports[0]
    assert harness.urls == [
        f"http://localhost:{port}/admin#local-launch=example-not-secret-grant-{index}"
        for index in range(1, 4)
    ]
    assert harness.grants == [harness.app.state.runtime_database] * 3
    assert len(harness.server.sockets) == 1
    assert harness.server.sockets[0].fileno() == -1
    assert launcher._listener_stopped(port)
    assert "grant" not in capsys.readouterr().out


def test_isolated_environment_and_restore(
    harness: SimpleNamespace, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    inherited = {
        "REPONPC_CHAT_API_KEY": "example-secret-not-real",
        "REPONPC_EMBEDDING_BASE_URL": "https://example.invalid/private",
        "REPONPC_CHAT_API_KEY_FILE": "example-private-path",
        "REPONPC_ADMIN_PASSWORD_HASH": "example-not-real",
        "REPONPC_VISITOR_TRUSTED_PROXY_CIDRS": "10.0.0.0/8",
        "REPONPC_UNKNOWN_SETTING": "ignored-inherited-value",
        "BROWSER": "echo %s",
    }
    for key, value in inherited.items():
        monkeypatch.setenv(key, value)
    assert launcher.main(arguments(tmp_path, "--no-browser")) == 0
    assert all(harness.observed.get(key) != value for key, value in inherited.items())
    assert all(os.environ[key] == value for key, value in inherited.items())
    assert harness.observed["REPONPC_DEPLOYMENT_PROFILE"] == "loopback_evaluation"
    assert harness.observed["REPONPC_ENV"] == "production"
    assert harness.observed["REPONPC_LOG_LEVEL"] == "INFO"
    assert harness.observed["REPONPC_TRUSTED_PROXY_CIDRS"] == ""
    assert harness.observed["REPONPC_ADMIN_ORIGINS"] == harness.observed["REPONPC_PUBLIC_BASE_URL"]
    assert harness.observed["REPONPC_VISITOR_GATEWAY_PORT"] != harness.observed["REPONPC_PORT"]
    assert not harness.grants and not harness.urls


@pytest.mark.parametrize("extra", ["--no-browser", "--smoke-check"])
def test_no_browser_and_health_only_mint_no_grant(
    harness: SimpleNamespace, tmp_path: Path, extra: str
) -> None:
    assert launcher.main(arguments(tmp_path, extra)) == 0
    assert not harness.urls and not harness.grants


@pytest.mark.parametrize("exception", [EOFError, KeyboardInterrupt])
def test_console_interrupt_is_graceful(
    harness: SimpleNamespace,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    exception: type[BaseException],
) -> None:
    def stop(prompt: str) -> str:
        raise exception

    monkeypatch.setattr("builtins.input", stop)
    assert launcher.main(arguments(tmp_path, "--no-browser")) == 0
    assert harness.server.should_exit
    assert launcher._listener_stopped(harness.ports[0])


def test_persistent_key_is_32_bytes_and_not_printed(
    harness: SimpleNamespace, tmp_path: Path, capsys: Any
) -> None:
    assert launcher.main(arguments(tmp_path, "--smoke-check")) == 0
    key = tmp_path / "data" / "private" / "ip-hash-key"
    contents = key.read_text(encoding="ascii")
    assert len(contents) == 64 and len(bytes.fromhex(contents)) == 32
    assert (
        launcher.prepare_data_directory(tmp_path / "data", production=False).read_text() == contents
    )
    assert contents not in capsys.readouterr().out


@pytest.mark.parametrize("bad", [b"x" * 64, b"01" * 31, b"\xff" * 64])
def test_invalid_existing_key_preserved(
    harness: SimpleNamespace, tmp_path: Path, bad: bytes
) -> None:
    private = tmp_path / "data" / "private"
    private.mkdir(parents=True)
    key = private / "ip-hash-key"
    key.write_bytes(bad)
    assert launcher.main(arguments(tmp_path)) == 2
    assert key.read_bytes() == bad
    assert not harness.ports and not harness.urls


def test_hardlinked_key_refused(harness: SimpleNamespace, tmp_path: Path) -> None:
    private = tmp_path / "data" / "private"
    private.mkdir(parents=True)
    source = tmp_path / "other-key"
    source.write_text("ab" * 32)
    os.link(source, private / "ip-hash-key")
    assert launcher.main(arguments(tmp_path)) == 2
    assert source.read_text() == "ab" * 32
    assert not harness.ports


def test_symlink_directory_refused(harness: SimpleNamespace, tmp_path: Path) -> None:
    real = tmp_path / "real"
    real.mkdir()
    try:
        (tmp_path / "data").symlink_to(real, target_is_directory=True)
    except OSError:
        pytest.skip("Windows account cannot create symlinks")
    assert launcher.main(arguments(tmp_path)) == 2
    assert not tuple(real.iterdir()) and not harness.ports


def test_occupied_port_never_reuses_other_listener(
    harness: SimpleNamespace, tmp_path: Path
) -> None:
    with socket.socket() as other:
        other.bind(("127.0.0.1", 0))
        other.listen()
        port = other.getsockname()[1]
        assert launcher.main(arguments(tmp_path, "--port", str(port))) == 2
        assert not launcher._listener_stopped(port)
    assert not (tmp_path / "data").exists() and not harness.ports


@pytest.mark.parametrize("port", ["-1", "65536", "abc"])
def test_invalid_port_has_no_startup_side_effects(
    harness: SimpleNamespace, tmp_path: Path, port: str
) -> None:
    assert launcher.main(arguments(tmp_path, "--port", port)) == 2
    assert not (tmp_path / "data").exists() and not harness.ports


def test_relative_data_path_refused(harness: SimpleNamespace) -> None:
    assert launcher.main(["--data-dir", "relative-example-data"]) == 2
    assert not harness.ports


def test_default_data_uses_local_appdata(
    harness: SimpleNamespace, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    assert launcher.main(["--smoke-check"]) == 0
    assert harness.observed["REPONPC_DATA_DIR"] == str(tmp_path / "RepoNPC" / "data")


def test_launcher_environment_passes_real_configuration_validation(
    harness: SimpleNamespace, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from reponpc.config.environment import load_environment

    def load(data_dir: Path) -> Any:
        settings = load_environment(secret_roots=(data_dir / "private",))
        assert settings.host == "127.0.0.1"
        assert settings.deployment_profile == "loopback_evaluation"
        assert settings.secrets["ip_hash_key"].reveal()
        assert not settings.chat_provider and not settings.embedding_provider
        return harness.app

    monkeypatch.setattr(launcher, "_load_application", load)
    assert launcher.main(arguments(tmp_path, "--smoke-check")) == 0


def test_failed_shutdown_is_bounded_and_reports_failure(
    harness: SimpleNamespace, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: Any
) -> None:
    release = threading.Event()
    monkeypatch.setattr(harness.server, "run", lambda **kwargs: release.wait(1))
    monkeypatch.setattr(launcher, "_STOP_TIMEOUT", 0.01)
    try:
        assert launcher.main(arguments(tmp_path, "--smoke-check")) == 2
        assert "has not finished stopping" in capsys.readouterr().out
    finally:
        release.set()


@pytest.mark.parametrize("usable,database", [(False, object()), (None, object()), (True, None)])
def test_unusable_runtime_fails_closed(
    harness: SimpleNamespace, tmp_path: Path, usable: bool | None, database: object | None
) -> None:
    harness.app.state.runtime_storage_usable = usable
    harness.app.state.runtime_database = database
    assert launcher.main(arguments(tmp_path)) == 2
    assert not harness.grants and not harness.server.sockets
    assert launcher._listener_stopped(harness.ports[0])


def test_health_timeout_is_bounded_and_closes_socket(
    harness: SimpleNamespace, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(launcher, "_START_TIMEOUT", 0.01)
    monkeypatch.setattr(launcher, "_healthy", lambda port, timeout: False)
    assert launcher.main(arguments(tmp_path)) == 2
    assert harness.server.should_exit and not harness.grants
    assert launcher._listener_stopped(harness.ports[0])


def test_browser_exception_does_not_reveal_grant(
    harness: SimpleNamespace, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: Any
) -> None:
    def browser(url: str) -> bool:
        raise RuntimeError(url)

    monkeypatch.setattr(launcher.webbrowser, "open", browser)
    assert launcher.main(arguments(tmp_path)) == 0
    assert "local-launch" not in capsys.readouterr().out


def test_server_exception_is_safe(
    harness: SimpleNamespace, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: Any
) -> None:
    def run(*, sockets: list[socket.socket]) -> None:
        raise RuntimeError("example-private-error")

    monkeypatch.setattr(harness.server, "run", run)
    assert launcher.main(arguments(tmp_path)) == 2
    captured = capsys.readouterr()
    assert "example-private-error" not in captured.out + captured.err
    assert not harness.grants and launcher._listener_stopped(harness.ports[0])


def test_server_uses_application_object_without_proxy_or_access_logging(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings: dict[str, Any] = {}
    app = object()

    def config(application: object, **kwargs: Any) -> object:
        assert application is app
        settings.update(kwargs)
        return application

    monkeypatch.setitem(sys.modules, "uvicorn", SimpleNamespace(Config=config, Server=lambda x: x))
    assert launcher._make_server(app, 54321) is app
    assert settings["host"] == "127.0.0.1" and settings["port"] == 54321
    assert settings["proxy_headers"] is False and settings["forwarded_allow_ips"] == ""
    assert settings["access_log"] is False
    assert settings["log_level"] == "warning"


def test_load_application_passes_installer_log_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import reponpc.main as runtime_main
    from reponpc.config import environment

    settings, application = object(), object()
    observed: list[tuple[object, Path]] = []

    def load_environment(*, secret_roots: tuple[Path, ...]) -> object:
        assert secret_roots == (tmp_path / "private",)
        return settings

    def prepare(actual: object, *, log_file_path: Path) -> object:
        observed.append((actual, log_file_path))
        return application

    monkeypatch.setattr(environment, "load_environment", load_environment)
    monkeypatch.setattr(runtime_main, "prepare_application", prepare)
    assert launcher._load_application(tmp_path) is application
    assert observed == [(settings, tmp_path / "logs" / "reponpc.log")]


def test_installer_log_file_survives_maintenance_application_rebuild(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, reponpc_logger: logging.Logger
) -> None:
    import reponpc.main as runtime_main
    from reponpc.observability.logging import get_safe_logger

    for key in tuple(os.environ):
        if key.startswith("REPONPC_"):
            monkeypatch.delenv(key)
    for key, value in launcher._environment(
        tmp_path,
        launcher.prepare_data_directory(tmp_path, production=False),
        18240,
        "loopback_evaluation",
    ).items():
        monkeypatch.setenv(key, value)
    monkeypatch.setattr(runtime_main, "app", runtime_main.create_app())
    application = launcher._load_application(tmp_path)
    logger = get_safe_logger("reponpc.test.installer")
    logger.emit(logging.INFO, "test.installer.before")
    rebuilt = application.state.maintenance_service._factory()
    logger.emit(logging.INFO, "test.installer.after")

    payloads = [
        json.loads(line)
        for line in (tmp_path / "logs" / "reponpc.log").read_text(encoding="utf-8").splitlines()
    ]
    assert [p["event"] for p in payloads] == ["test.installer.before", "test.installer.after"]
    assert all(p["severity"] == "INFO" for p in payloads)
    assert reponpc_logger.level == logging.INFO
    for app in (application, rebuilt):
        app.state.maintenance_service.close()
        app.state.bundle_manager.close()


@pytest.mark.parametrize(
    "status,body,expected",
    [
        (200, b'{"status":"alive"}', True),
        (503, b'{"status":"alive"}', False),
        (200, b'{"status":"ready"}', False),
        (200, b"invalid-json", False),
        (200, b" " * 4097, False),
    ],
)
def test_health_is_bounded_liveness_only(
    monkeypatch: pytest.MonkeyPatch, status: int, body: bytes, expected: bool
) -> None:
    closed: list[bool] = []

    class Connection:
        def __init__(self, host: str, port: int, *, timeout: float) -> None:
            assert (host, port, timeout) == ("127.0.0.1", 54321, 0.5)

        def request(self, method: str, path: str) -> None:
            assert (method, path) == ("GET", "/healthz")

        def getresponse(self) -> Any:
            def read(size: int) -> bytes:
                assert size == 4097 and status == 200
                return body

            return SimpleNamespace(status=status, read=read)

        def close(self) -> None:
            closed.append(True)

    monkeypatch.setattr(launcher, "HTTPConnection", Connection)
    assert launcher._healthy(54321, 0.5) is expected
    assert closed == [True]


def test_real_uvicorn_disposable_health_smoke(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    requests: list[str] = []
    ports: list[int] = []

    class HealthApplication:
        state = SimpleNamespace(runtime_storage_usable=True, runtime_database=object())

        async def __call__(self, scope: Any, receive: Any, send: Any) -> None:
            if scope["type"] == "lifespan":
                while True:
                    message = await receive()
                    if message["type"] == "lifespan.startup":
                        await send({"type": "lifespan.startup.complete"})
                    else:
                        await send({"type": "lifespan.shutdown.complete"})
                        return
            else:
                requests.append(scope["path"])
                await send({"type": "http.response.start", "status": 200, "headers": []})
                await send({"type": "http.response.body", "body": b'{"status":"alive"}'})

    def load(data_dir: Path) -> HealthApplication:
        ports.append(int(os.environ["REPONPC_PORT"]))
        return HealthApplication()

    def forbidden(*args: Any, **kwargs: Any) -> Any:
        pytest.fail("health smoke must not mint grants or launch a browser")

    monkeypatch.setattr(launcher, "_load_application", load)
    monkeypatch.setattr(launcher, "_issue_grant", forbidden)
    monkeypatch.setattr(launcher.webbrowser, "open", forbidden)
    assert launcher.main(arguments(tmp_path, "--smoke-check")) == 0
    assert requests == ["/healthz"]
    assert launcher._listener_stopped(ports[0])


def _passwordless_owner(data_dir: Path) -> RuntimeDatabase:
    database = RuntimeDatabase(data_dir)
    database.initialize()
    service = AdminSessionService(
        database=database,
        identity_hmac_key=b"k" * 32,
        deployment_profile="loopback_evaluation",
    )
    grant = issue_admin_local_launch_grant(database, deployment_profile="loopback_evaluation")
    service.consume_local_launch(grant=grant)
    return database


def test_admin_owner_state_three_states(tmp_path: Path) -> None:
    database = RuntimeDatabase(tmp_path)
    database.initialize()
    assert admin_owner_state(database) == "setup_required"
    _passwordless_owner(tmp_path)
    assert admin_owner_state(database) == "password_required"
    set_admin_recovery_password(database, username=None, password="example password 12345")
    assert admin_owner_state(database) == "ready"


def test_owner_console_setup_code_is_displayed_once_and_only_hash_stored(
    tmp_path: Path, caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    from reponpc.admin import auth

    issue = auth.issue_admin_setup_code
    issued: list[str] = []
    output: list[str] = []

    def issue_once(database: RuntimeDatabase) -> str:
        code = issue(database)
        issued.append(code)
        return code

    monkeypatch.setattr(auth, "issue_admin_setup_code", issue_once)
    caplog.set_level(logging.DEBUG)
    assert launcher.run_owner_console(tmp_path, environ={}, write=output.append)
    assert len(output) == 1
    code = output[0].splitlines()[-1]
    assert issued == [code]
    assert len(code) == 43
    assert "15 minutes" in output[0] and "15 分鐘" in output[0]
    assert "shown only here" in output[0] and "只在此顯示" in output[0]
    database = RuntimeDatabase(tmp_path)
    with database.connection() as connection:
        rows = connection.execute("SELECT * FROM admin_setup").fetchall()
        assert len(rows) == 1
        assert rows[0]["code_hash"] == hashlib.sha256(code.encode()).hexdigest()
        assert datetime.fromisoformat(rows[0]["expires_at"]) - datetime.fromisoformat(
            rows[0]["created_at"]
        ) == timedelta(minutes=15)
        assert code not in repr([tuple(row) for row in rows])
        assert connection.execute("SELECT COUNT(*) FROM admin_owner").fetchone()[0] == 0
    assert code not in caplog.text


@pytest.mark.parametrize(
    "attempts",
    [
        ["example password 12345"] * 2,
        ["short", "short", "example password 12345", "example password 12345"],
        ["mismatch canary", "other canary", "example password 12345", "example password 12345"],
    ],
)
def test_owner_console_sets_password_and_retries_safely(
    tmp_path: Path, attempts: list[str], caplog: pytest.LogCaptureFixture
) -> None:
    database = _passwordless_owner(tmp_path)
    output: list[str] = []
    prompts: list[str] = []
    replies = iter(attempts)

    def read_password(prompt: str) -> str:
        prompts.append(prompt)
        return next(replies)

    caplog.set_level(logging.DEBUG)
    assert launcher.run_owner_console(
        tmp_path, environ={}, read_password=read_password, write=output.append
    )
    assert len(prompts) == len(attempts)
    assert admin_owner_state(database) == "ready"
    service = AdminSessionService(database=database, identity_hmac_key=b"k" * 32)
    assert service.auth_methods().password_available
    service.login(username="local-owner", password=attempts[-1], remote_identity="console-test")
    assert "Password set successfully" in output[-1]
    for password in attempts:
        assert password not in "\n".join(output + prompts) + caplog.text


@pytest.mark.parametrize("mismatch", [False, True])
def test_owner_console_stops_after_three_failures_without_password_method(
    tmp_path: Path, mismatch: bool, caplog: pytest.LogCaptureFixture
) -> None:
    database = _passwordless_owner(tmp_path)
    output: list[str] = []
    reads: list[str] = []

    def read_password(prompt: str) -> str:
        reads.append(prompt)
        return "different canary" if mismatch and len(reads) % 2 == 0 else "short canary"

    assert not launcher.run_owner_console(
        tmp_path, environ={}, read_password=read_password, write=output.append
    )
    assert len(reads) == 6
    assert admin_owner_state(database) == "password_required"
    with database.connection() as connection:
        assert connection.execute("SELECT COUNT(*) FROM admin_auth_methods").fetchone()[0] == 0
    assert "short canary" not in "\n".join(output) + caplog.text
    assert "different canary" not in "\n".join(output) + caplog.text


@pytest.mark.parametrize("exception", [EOFError, KeyboardInterrupt])
@pytest.mark.parametrize("interrupt_at", [1, 2])
def test_owner_console_interrupt_never_sets_password(
    tmp_path: Path, exception: type[BaseException], interrupt_at: int
) -> None:
    database = _passwordless_owner(tmp_path)
    reads: list[str] = []

    def read_password(prompt: str) -> str:
        reads.append(prompt)
        if len(reads) == interrupt_at:
            raise exception
        return "example password 12345"

    assert not launcher.run_owner_console(
        tmp_path, environ={}, read_password=read_password, write=lambda message: None
    )
    assert admin_owner_state(database) == "password_required"


@pytest.mark.parametrize("existing_owner", [False, True])
def test_owner_console_environment_credentials_are_silent(
    tmp_path: Path, existing_owner: bool
) -> None:
    if existing_owner:
        _passwordless_owner(tmp_path)
    output: list[str] = []

    def forbidden(prompt: str) -> str:
        pytest.fail("environment credentials must not prompt")

    assert launcher.run_owner_console(
        tmp_path,
        environ={"REPONPC_ADMIN_USERNAME": "example", "REPONPC_ADMIN_PASSWORD_HASH": "example"},
        read_password=forbidden,
        write=output.append,
    )
    assert output == []
    with RuntimeDatabase(tmp_path).connection() as connection:
        assert connection.execute("SELECT COUNT(*) FROM admin_setup").fetchone()[0] == 0


@pytest.mark.parametrize("name", ["REPONPC_ADMIN_USERNAME", "REPONPC_ADMIN_PASSWORD_HASH"])
def test_owner_console_partial_environment_credentials_do_not_bypass_setup(
    tmp_path: Path, name: str
) -> None:
    output: list[str] = []
    assert launcher.run_owner_console(tmp_path, environ={name: "example"}, write=output.append)
    assert len(output) == 1 and "First-owner setup code" in output[0]


def test_owner_console_ready_owner_is_silent(tmp_path: Path) -> None:
    database = _passwordless_owner(tmp_path)
    set_admin_recovery_password(database, username=None, password="example password 12345")

    def forbidden(*args: Any) -> Any:
        pytest.fail("ready owner must not prompt or print")

    assert launcher.run_owner_console(
        tmp_path, environ={}, read_password=forbidden, write=forbidden
    )


def test_invalid_profile_has_no_startup_side_effects(
    harness: SimpleNamespace, tmp_path: Path
) -> None:
    assert launcher.main(arguments(tmp_path, "--profile", "invalid")) == 2
    assert not (tmp_path / "data").exists() and not harness.ports


@pytest.mark.parametrize("profile", ["loopback_evaluation", "production"])
def test_explicit_profile_and_production_browser_never_issues_grants(
    harness: SimpleNamespace, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, profile: str
) -> None:
    consoles: list[tuple[Path, str]] = []
    commands = iter(["open", "q"])
    monkeypatch.setattr("builtins.input", lambda prompt: next(commands))

    def console(data_dir: Path, *, environ: Any) -> bool:
        assert not harness.server.sockets
        consoles.append((data_dir, environ["REPONPC_DEPLOYMENT_PROFILE"]))
        return True

    def forbidden(database: Any) -> str:
        pytest.fail("production must never issue a local-launch grant")

    monkeypatch.setattr(launcher, "run_owner_console", console)
    if profile == "production":
        monkeypatch.setattr(launcher, "_issue_grant", forbidden)
    assert launcher.main(arguments(tmp_path, "--profile", profile)) == 0
    assert harness.observed["REPONPC_DEPLOYMENT_PROFILE"] == profile
    assert harness.observed["REPONPC_ADMIN_ORIGINS"] == f"http://localhost:{harness.ports[0]}"
    if profile == "production":
        assert consoles == [(tmp_path / "data", "production")]
        assert harness.urls == [f"http://localhost:{harness.ports[0]}/admin"] * 2
        assert not harness.grants
    else:
        assert not consoles
        assert len(harness.grants) == 2


def test_production_console_failure_prevents_server_construction(
    harness: SimpleNamespace, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def forbidden(*args: Any) -> Any:
        pytest.fail("cancelled owner setup must not construct a server")

    monkeypatch.setattr(launcher, "run_owner_console", lambda *args, **kwargs: False)
    monkeypatch.setattr(launcher, "_make_server", forbidden)
    assert launcher.main(arguments(tmp_path, "--profile", "production")) == 2
    assert not harness.urls and not harness.grants and not harness.server.sockets
    assert launcher._listener_stopped(harness.ports[0])


def test_production_smoke_skips_owner_console_and_grants(
    harness: SimpleNamespace, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def forbidden(*args: Any, **kwargs: Any) -> Any:
        pytest.fail("production smoke must not prompt, issue grants or open a browser")

    monkeypatch.setattr(launcher, "run_owner_console", forbidden)
    monkeypatch.setattr(launcher, "_issue_grant", forbidden)
    monkeypatch.setattr(launcher.webbrowser, "open", forbidden)
    assert launcher.main(arguments(tmp_path, "--profile", "production", "--smoke-check")) == 0
    assert harness.server.sockets and launcher._listener_stopped(harness.ports[0])


@pytest.mark.parametrize(
    ("relative", "root", "expected"),
    [
        (
            "existing data",
            True,
            'icacls "{path}" /inheritance:r /grant:r '
            '"*S-1-5-21-123-456-789-1001:(OI)(CI)F" '
            '"*S-1-5-18:(OI)(CI)F" "*S-1-5-32-544:(OI)(CI)F" /remove:g "*S-1-5-32-545"',
        ),
        ("existing data/private", False, 'icacls "{path}" /reset /T'),
    ],
)
def test_unsafe_production_path_reports_exact_repair_and_does_not_load_app(
    harness: SimpleNamespace,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: Any,
    relative: str,
    root: bool,
    expected: str,
) -> None:
    unsafe_path = tmp_path / relative
    monkeypatch.setattr(private_files, "_current_user_sid", lambda: "S-1-5-21-123-456-789-1001")
    monkeypatch.setattr(
        private_files,
        "_read_windows_acl",
        lambda path: (
            "S-1-5-21-123-456-789-1001",
            [(0, 0, "S-1-5-32-545"), (0, 0x10, "S-1-5-11")],
            True,
        ),
    )

    def prepare(data_dir: Path, *, production: bool) -> Path:
        assert production
        raise launcher.UnsafeDataDirectory(unsafe_path, root=root)

    monkeypatch.setattr(launcher, "prepare_data_directory", prepare)
    assert launcher.main(arguments(tmp_path, "--profile", "production")) == 2
    output = capsys.readouterr().out.splitlines()
    assert len(output) == 2
    assert str(unsafe_path) in output[0]
    assert output[1] == expected.format(path=unsafe_path)
    assert not harness.ports and not harness.server.sockets and not harness.urls
