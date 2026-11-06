"""CLI trust boundary and pure state-table coverage (synthetic JSON only)."""

from __future__ import annotations

import subprocess
from dataclasses import FrozenInstanceError, replace

import pytest

from reponpc.tailscale.runner import (
    MAX_OUTPUT_BYTES,
    SubprocessRunner,
    TailscaleCommandError,
    funnel_off_command,
    funnel_on_command,
    locate_executable,
    serve_status_command,
    status_command,
)
from reponpc.tailscale.state import (
    choose_state,
    free_ports,
    funnel_ports,
    own_route,
    parse_serve,
    parse_status,
)
from tests.support.fake_tailscale import HOST, VISITOR_PORT, add_route, fixture_state


def test_exact_fixed_arguments():
    assert status_command() == ("tailscale", "status", "--json")
    assert serve_status_command() == ("tailscale", "serve", "status", "--json")
    assert funnel_on_command(8443, 8882) == (
        "tailscale",
        "funnel",
        "--bg",
        "--https=8443",
        "http://127.0.0.1:8882",
    )
    assert funnel_off_command(8443) == ("tailscale", "funnel", "--https=8443", "off")


@pytest.mark.parametrize("bad", [True, False, 0, -1, 65536, "443", "443;echo BAD", 443.0, None])
def test_builders_reject_noninteger_and_out_of_range_ports(bad):
    with pytest.raises(ValueError):
        funnel_on_command(bad, 8882)
    with pytest.raises(ValueError):
        funnel_off_command(bad)


@pytest.mark.parametrize("bad", [True, 1023, 65536, "8882", 8882.0, "8882 && echo BAD"])
def test_visitor_port_range(bad):
    with pytest.raises(ValueError):
        funnel_on_command(443, bad)


@pytest.mark.parametrize("port", [1024, 65535])
def test_visitor_port_boundaries(port):
    assert funnel_on_command(443, port)[-1] == f"http://127.0.0.1:{port}"


def test_unix_lookup_ignores_relative_empty_and_working_directory_entries():
    seen = []

    def is_file(path):
        seen.append(path)
        return path == "/trusted/tailscale"

    assert (
        locate_executable(
            {"PATH": ":.:relative:/work:/work/.:/trusted:/later"}, "linux", is_file, cwd="/work"
        )
        == "/trusted/tailscale"
    )
    assert seen == ["/trusted/tailscale"]


def test_lookup_fallback_order_and_regular_file_check():
    seen = []

    def is_file(path):
        seen.append(path)
        return path == "/usr/local/bin/tailscale"

    assert locate_executable({}, "darwin", is_file) == "/usr/local/bin/tailscale"
    assert seen == [
        "/Applications/Tailscale.app/Contents/MacOS/Tailscale",
        "/usr/bin/tailscale",
        "/usr/local/bin/tailscale",
    ]
    assert locate_executable({}, "linux", lambda _: False) is None


def test_windows_lookup_only_exe_absolute_roots_then_program_files():
    seen = []

    def is_file(path):
        seen.append(path)
        return path == r"C:\Programs\Tailscale\tailscale.exe"

    assert (
        locate_executable(
            {"Path": r".;relative;C:\work;C:\work\.;C:\tools", "ProgramFiles": r"C:\Programs"},
            "win32",
            is_file,
            cwd=r"C:\work",
        )
        == r"C:\Programs\Tailscale\tailscale.exe"
    )
    assert seen == [r"C:\tools\tailscale.exe", r"C:\Programs\Tailscale\tailscale.exe"]
    assert locate_executable({"PATH": r"\rooted;relative"}, "win32", lambda _: True) is None


@pytest.mark.parametrize("platform", ["win32", "linux"])
@pytest.mark.parametrize(
    "command,timeout",
    [
        (status_command(), 10),
        (serve_status_command(), 10),
        (funnel_on_command(443, 8882), 30),
        (funnel_off_command(443), 30),
    ],
)
def test_subprocess_exact_invocation_and_sanitized_environment(
    monkeypatch, platform, command, timeout
):
    calls = []

    def run(args, **kwargs):
        calls.append((args, kwargs))
        return subprocess.CompletedProcess(args, 0, b"{}", b"")

    monkeypatch.setattr(subprocess, "run", run)
    runner = SubprocessRunner(
        "/trusted/tailscale.exe",
        platform=platform,
        environment={
            "SystemRoot": "C:/Windows",
            "HOME": "/fixture",
            "TOKEN": "CANARY",
            "HTTP_PROXY": "CANARY",
            "TS_SOCKET": "CANARY",
            "PATH": ".",
        },
    )
    assert runner.run(command) == b"{}"
    assert calls == [
        (
            ["/trusted/tailscale.exe", *command[1:]],
            {
                "shell": False,
                "capture_output": True,
                "timeout": timeout,
                "env": {"SystemRoot": "C:/Windows", "HOME": "/fixture"},
                "stdin": subprocess.DEVNULL,
                "creationflags": subprocess.CREATE_NO_WINDOW if platform == "win32" else 0,
            },
        )
    ]


@pytest.mark.parametrize("kind", ["stdout", "stderr", "exit", "timeout", "oserror"])
def test_subprocess_failures_are_fixed_and_bounded(monkeypatch, kind):
    def run(args, **kwargs):
        if kind == "timeout":
            raise subprocess.TimeoutExpired(args, 10, output=b"CANARY")
        if kind == "oserror":
            raise OSError("CANARY")
        return subprocess.CompletedProcess(
            args,
            1 if kind == "exit" else 0,
            b"x" * (MAX_OUTPUT_BYTES + 1) if kind == "stdout" else b"CANARY",
            b"x" * (MAX_OUTPUT_BYTES + 1) if kind == "stderr" else b"",
        )

    monkeypatch.setattr(subprocess, "run", run)
    with pytest.raises(TailscaleCommandError) as raised:
        SubprocessRunner("/trusted/tailscale.exe").run(status_command())
    assert str(raised.value) == "The Tailscale command could not be completed."


@pytest.mark.parametrize(
    "command",
    [
        ("tailscale", "funnel", "reset"),
        ("tailscale", "up"),
        ("tailscale", "login"),
        ("tailscale", "set"),
        ("tailscale", "serve", "--bg", "8882"),
        ("tailscale", "funnel", "--bg", "--https=0443", "http://127.0.0.1:8882"),
    ],
)
def test_runner_never_starts_unlisted_commands(monkeypatch, command):
    def forbidden(*args, **kwargs):
        pytest.fail("An unlisted command reached subprocess.run")

    monkeypatch.setattr(subprocess, "run", forbidden)
    with pytest.raises(TailscaleCommandError):
        SubprocessRunner("/trusted/tailscale.exe").run(command)


def _choose(data, **kwargs):
    return choose_state(
        profile=kwargs.pop("profile", "loopback_evaluation"),
        installed=kwargs.pop("installed", True),
        status=parse_status(data["status"]),
        serve=parse_serve(data["serve"]),
        visitor_port=VISITOR_PORT,
        **kwargs,
    )


@pytest.mark.parametrize(
    "expected",
    [
        "unavailable_profile",
        "not_installed",
        "error",
        "unsupported_version",
        "needs_login",
        "stopped",
        "offline",
        "https_disabled",
        "funnel_not_allowed",
        "live",
        "no_free_port",
        "ready",
    ],
)
def test_every_state_table_row(expected):
    data = fixture_state()
    status = data["status"]
    kwargs = {}
    if expected == "unavailable_profile":
        kwargs["profile"] = "production"
    elif expected == "not_installed":
        kwargs["installed"] = False
    elif expected == "error":
        kwargs["error"] = True
    elif expected == "unsupported_version":
        status["Version"] = "1.51.9"
    elif expected == "needs_login":
        status["BackendState"] = "NeedsLogin"
    elif expected == "stopped":
        status["BackendState"] = "Stopped"
    elif expected == "offline":
        status["Self"]["Online"] = False
    elif expected == "https_disabled":
        status["CertDomains"] = []
    elif expected == "funnel_not_allowed":
        status["Self"]["Capabilities"].remove("funnel")
    elif expected == "live":
        add_route(data["serve"], 8443)
    elif expected == "no_free_port":
        for port in (443, 8443, 10000):
            add_route(data["serve"], port, visitor_port=8883)
    result = _choose(data, **kwargs)
    assert result.state == expected
    assert result.version == (
        None
        if expected in {"unavailable_profile", "not_installed"}
        else "1.51.9"
        if expected == "unsupported_version"
        else "1.104.4"
    )
    assert (result.port is not None) == (expected in {"ready", "live"})
    assert (result.funnel_url is not None) == (expected in {"ready", "live"})


def test_state_precedence_and_version_boundary():
    data = fixture_state()
    status = parse_status(data["status"])
    serve = parse_serve(data["serve"])
    later = replace(
        status,
        version="1.51.9",
        version_numbers=(1, 51, 9),
        backend_state="NeedsLogin",
        auth_url="https://login.invalid",
        online=False,
        cert_domains=(),
        capabilities=(),
    )
    states = [
        (later, "unsupported_version"),
        (replace(later, version_numbers=(1, 52, 0)), "needs_login"),
        (
            replace(later, version_numbers=(1, 52, 0), backend_state="Stopped", auth_url=""),
            "stopped",
        ),
        (replace(status, online=False, cert_domains=(), capabilities=()), "offline"),
        (replace(status, cert_domains=(), capabilities=()), "https_disabled"),
    ]
    for candidate, expected in states:
        assert (
            choose_state(
                profile="loopback_evaluation",
                installed=True,
                status=candidate,
                serve=serve,
                visitor_port=VISITOR_PORT,
            ).state
            == expected
        )
    assert (
        choose_state(
            profile="production", installed=False, error=True, visitor_port=VISITOR_PORT
        ).state
        == "unavailable_profile"
    )
    assert (
        choose_state(
            profile="loopback_evaluation", installed=False, error=True, visitor_port=VISITOR_PORT
        ).state
        == "not_installed"
    )
    assert (
        choose_state(
            profile="loopback_evaluation",
            installed=True,
            status=later,
            serve=serve,
            error=True,
            visitor_port=VISITOR_PORT,
        ).state
        == "error"
    )
    assert _choose(data).version == "1.104.4"
    assert _choose(data).funnel_url == f"https://{HOST}"
    with pytest.raises(FrozenInstanceError):
        status.online = False


@pytest.mark.parametrize("backend", ["NeedsLogin", "NeedsMachineAuth", "NoState", "Starting"])
def test_backend_state_and_auth_url(backend):
    data = fixture_state()
    data["status"]["BackendState"] = backend
    assert _choose(data).state == ("offline" if backend == "Starting" else "needs_login")
    data["status"]["AuthURL"] = "https://login.invalid/fixture"
    assert _choose(data).state == "needs_login"


@pytest.mark.parametrize("source", ["Capabilities", "CapMap"])
def test_capability_ports_are_ordered_and_not_copied_from_examples(source):
    data = fixture_state()
    own = data["status"]["Self"]
    capability = "https://tailscale.com/cap/funnel-ports?ports=4443,10000,443,8443,7443"
    own["Capabilities"] = ["https", "funnel"]
    if source == "Capabilities":
        own[source].append(capability)
    else:
        own[source][capability] = []
    assert funnel_ports(parse_status(data["status"])) == (443, 8443, 10000, 4443, 7443)
    for port in (443, 8443, 10000, 4443):
        assert _choose(data).port == port
        add_route(data["serve"], port, visitor_port=8883)
    assert _choose(data).port == 7443
    assert _choose(data).funnel_url == f"https://{HOST}:7443"


def test_capability_map_accepts_null_and_list_values_as_the_real_cli_reports_them():
    # Found by a read-only run against the real CLI: most CapMap values are null.
    data = fixture_state()
    cap_map = data["status"]["Self"]["CapMap"]
    assert cap_map["fixture-null"] is None and isinstance(cap_map["fixture-list"], list)
    assert _choose(data).state == "ready"
    cap_map["unrelated"] = None
    assert _choose(data).state == "ready"
    cap_map["unrelated"] = "text"
    with pytest.raises(ValueError):
        parse_status(data["status"])


def test_default_ports_and_foreign_routes():
    data = fixture_state()
    data["status"]["Self"]["Capabilities"] = ["funnel", "https"]
    assert funnel_ports(parse_status(data["status"])) == (443, 8443, 10000)
    for port in (443, 8443, 10000):
        add_route(data["serve"], port, visitor_port=8883)
    serve = parse_serve(data["serve"])
    assert free_ports(serve, (443, 8443, 10000)) == ()
    assert all(not own_route(serve, HOST, port, VISITOR_PORT) for port in (443, 8443, 10000))
    add_route(data["serve"], 8443)
    assert _choose(data).state == "live"
    assert _choose(data).port == 8443


@pytest.mark.parametrize("mutation", ["host", "path", "proxy", "permission", "tcp", "sibling"])
def test_ownership_requires_the_whole_scoped_route(mutation):
    data = fixture_state()
    serve = data["serve"]
    add_route(serve, 443)
    if mutation == "host":
        serve["Web"]["other.tailnet-fixture.ts.net:443"] = serve["Web"].pop(f"{HOST}:443")
    elif mutation == "path":
        serve["Web"][f"{HOST}:443"]["Handlers"]["/foreign"] = {"Proxy": "http://127.0.0.1:8883"}
    elif mutation == "proxy":
        serve["Web"][f"{HOST}:443"]["Handlers"]["/"]["Proxy"] += "/"
    elif mutation == "permission":
        serve["AllowFunnel"][f"{HOST}:443"] = False
    elif mutation == "tcp":
        serve["TCP"]["443"] = {"TCPForward": "127.0.0.1:8883"}
    elif mutation == "sibling":
        add_route(serve, 443, host="other.tailnet-fixture.ts.net")
    assert not own_route(parse_serve(serve), HOST, 443, VISITOR_PORT)


def test_web_or_tcp_alone_occupies_a_port():
    data = fixture_state()
    add_route(data["serve"], 443, visitor_port=8883)
    del data["serve"]["TCP"]["443"]
    data["serve"]["TCP"]["8443"] = {"TCPForward": "127.0.0.1:8883"}
    data["serve"]["TCP"]["11434"] = {"TCPForward": "127.0.0.1:11434"}
    assert free_ports(parse_serve(data["serve"]), (443, 8443, 10000)) == (10000,)


@pytest.mark.parametrize(
    "path,value",
    [
        (("Version",), None),
        (("Version",), "CANARY"),
        (("BackendState",), 1),
        (("AuthURL",), False),
        (("CertDomains",), {}),
        (("Self",), None),
        (("Self", "Online"), 1),
        (("Self", "DNSName"), None),
        (("Self", "Capabilities"), {}),
        (("Self", "Capabilities"), [True]),
        (("Self", "CapMap"), []),
        (("Self", "CapMap"), {"funnel": True}),
    ],
)
def test_status_malformed_fields_fail_closed(path, value):
    status = fixture_state()["status"]
    target = status
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    with pytest.raises(ValueError):
        parse_status(status)
    del target[path[-1]]
    with pytest.raises(ValueError):
        parse_status(status)


@pytest.mark.parametrize(
    "value",
    [
        None,
        [],
        {},
        {"TCP": {}, "Web": {}, "AllowFunnel": []},
        {"TCP": {"0443": {"HTTPS": True}}, "Web": {}, "AllowFunnel": {}},
        {"TCP": {"443": {"HTTPS": 1}}, "Web": {}, "AllowFunnel": {}},
        {"TCP": {}, "Web": {f"{HOST}:443": {}}, "AllowFunnel": {}},
        {"TCP": {}, "Web": {}, "AllowFunnel": {f"{HOST}:443": "true"}},
    ],
)
def test_serve_malformed_fields_fail_closed(value):
    with pytest.raises(ValueError):
        parse_serve(value)


@pytest.mark.parametrize("ports", ["", "0", "65536", "443,", "true", "443&ports=8443", "-1"])
def test_malformed_capability_port_lists_are_error(ports):
    data = fixture_state()
    data["status"]["Self"]["Capabilities"] = [
        "funnel",
        "https",
        f"https://tailscale.com/cap/funnel-ports?ports={ports}",
    ]
    assert _choose(data).state == "error"
