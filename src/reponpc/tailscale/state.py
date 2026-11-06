"""Pure parsing and route ownership decisions over untrusted CLI JSON."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any
from urllib.parse import parse_qs, urlsplit

from reponpc.tailscale.runner import _port

DEFAULT_FUNNEL_PORTS = (443, 8443, 10000)
_PORT_CAPABILITY = "https://tailscale.com/cap/funnel-ports"


@dataclass(frozen=True, slots=True)
class Status:
    version: str
    version_numbers: tuple[int, int, int]
    backend_state: str
    auth_url: str
    cert_domains: tuple[str, ...]
    dns_name: str
    online: bool
    capabilities: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class WebRoute:
    host: str
    port: int
    proxy: str | None


@dataclass(frozen=True, slots=True)
class Serve:
    tcp_ports: frozenset[int]
    https_ports: frozenset[int]
    web: tuple[WebRoute, ...]
    allowed: frozenset[tuple[str, int]]


@dataclass(frozen=True, slots=True)
class FunnelStatus:
    state: str
    funnel_url: str | None = None
    port: int | None = None
    version: str | None = None

    def payload(self) -> dict[str, Any]:
        return asdict(self)


def _object(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or any(not isinstance(key, str) for key in value):
        raise ValueError("Invalid Tailscale object.")
    return value


def _strings(value: Any) -> tuple[str, ...]:
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise ValueError("Invalid Tailscale string list.")
    return tuple(value)


def parse_status(value: Any) -> Status:
    data = _object(value)
    version = data.get("Version")
    match = (
        re.fullmatch(r"(\d+)\.(\d+)\.(\d+)(?:-[A-Za-z0-9.-]+)?", version or "")
        if isinstance(version, str)
        else None
    )
    if match is None:
        raise ValueError("Invalid Tailscale version.")
    backend, auth = data.get("BackendState"), data.get("AuthURL")
    own = _object(data.get("Self"))
    dns, online = own.get("DNSName"), own.get("Online")
    if (
        not isinstance(backend, str)
        or not isinstance(auth, str)
        or not isinstance(dns, str)
        or type(online) is not bool
    ):
        raise ValueError("Invalid Tailscale status fields.")
    caps = _strings(own.get("Capabilities"))
    cap_map = _object(own.get("CapMap"))
    # The real CLI reports most capabilities with a null value and a few with a list.
    if any(item is not None and not isinstance(item, list) for item in cap_map.values()):
        raise ValueError("Invalid Tailscale capabilities.")
    return Status(
        ".".join(match.groups()),
        (int(match[1]), int(match[2]), int(match[3])),
        backend,
        auth,
        _strings(data.get("CertDomains")),
        dns,
        online,
        tuple(dict.fromkeys((*caps, *cap_map))),
    )


def _number(value: str) -> int:
    if not re.fullmatch(r"[1-9][0-9]{0,4}", value):
        raise ValueError("Invalid Tailscale route port.")
    return _port(int(value))


def _authority(value: str) -> tuple[str, int]:
    host, separator, port = value.rpartition(":")
    if not separator or not host or any(char.isspace() or char in "/\\@?#:" for char in host):
        raise ValueError("Invalid Tailscale route authority.")
    return host, _number(port)


def parse_serve(value: Any) -> Serve:
    data = _object(value)
    tcp, web, allow = (_object(data.get(key)) for key in ("TCP", "Web", "AllowFunnel"))
    tcp_ports: set[int] = set()
    https_ports: set[int] = set()
    routes: list[WebRoute] = []
    for key, config in tcp.items():
        port, fields = _number(key), _object(config)
        if not fields:
            raise ValueError("Invalid Tailscale TCP route.")
        for flag in ("HTTPS", "HTTP"):
            if flag in fields and type(fields[flag]) is not bool:
                raise ValueError("Invalid Tailscale TCP flag.")
        if "TCPForward" in fields and not isinstance(fields["TCPForward"], str):
            raise ValueError("Invalid Tailscale TCP target.")
        tcp_ports.add(port)
        if fields == {"HTTPS": True}:
            https_ports.add(port)
    for authority, config in web.items():
        host, port = _authority(authority)
        fields = _object(config)
        handlers = _object(fields.get("Handlers"))
        if not handlers:
            raise ValueError("Invalid Tailscale Web route.")
        for handler in handlers.values():
            values = _object(handler)
            if not values or ("Proxy" in values and not isinstance(values["Proxy"], str)):
                raise ValueError("Invalid Tailscale Web handler.")
        root = handlers.get("/")
        proxy = (
            root.get("Proxy")
            if isinstance(root, dict)
            and set(root) == {"Proxy"}
            and set(handlers) == {"/"}
            and set(fields) == {"Handlers"}
            else None
        )
        routes.append(WebRoute(host, port, proxy))
    allowed = set()
    for authority, enabled in allow.items():
        host_port = _authority(authority)
        if type(enabled) is not bool:
            raise ValueError("Invalid Tailscale Funnel permission.")
        if enabled:
            allowed.add(host_port)
    return Serve(frozenset(tcp_ports), frozenset(https_ports), tuple(routes), frozenset(allowed))


def funnel_ports(status: Status) -> tuple[int, ...]:
    ports: list[int] = []
    listed = False
    for capability in status.capabilities:
        if not capability.startswith(_PORT_CAPABILITY):
            continue
        listed = True
        parsed = urlsplit(capability)
        values = parse_qs(parsed.query, keep_blank_values=True)
        if (
            parsed.scheme + "://" + parsed.netloc + parsed.path != _PORT_CAPABILITY
            or parsed.fragment
            or set(values) != {"ports"}
            or len(values["ports"]) != 1
        ):
            raise ValueError("Invalid Tailscale Funnel ports.")
        ports.extend(_number(value) for value in values["ports"][0].split(","))
    if not listed:
        return DEFAULT_FUNNEL_PORTS if "funnel" in status.capabilities else ()
    return tuple(port for port in DEFAULT_FUNNEL_PORTS if port in ports) + tuple(
        port for port in dict.fromkeys(ports) if port not in DEFAULT_FUNNEL_PORTS
    )


def own_route(serve: Serve, host: str, port: int, visitor_port: int) -> bool:
    _port(port)
    _port(visitor_port, 1024)
    routes = tuple(route for route in serve.web if route.port == port)
    return (
        port in serve.https_ports
        and (host, port) in serve.allowed
        and len(routes) == 1
        and routes[0] == WebRoute(host, port, f"http://127.0.0.1:{visitor_port}")
    )


def free_ports(serve: Serve, ports: tuple[int, ...]) -> tuple[int, ...]:
    occupied = serve.tcp_ports | {route.port for route in serve.web}
    return tuple(port for port in ports if port not in occupied)


def choose_state(
    *,
    profile: str,
    installed: bool,
    status: Status | None = None,
    serve: Serve | None = None,
    visitor_port: int,
    error: bool = False,
) -> FunnelStatus:
    version = status.version if status is not None else None
    if profile != "loopback_evaluation":
        return FunnelStatus("unavailable_profile")
    if not installed:
        return FunnelStatus("not_installed")
    if error or status is None or serve is None:
        return FunnelStatus("error", version=version)
    try:
        _port(visitor_port, 1024)
        ports = funnel_ports(status)
    except ValueError:
        return FunnelStatus("error", version=version)
    state = None
    if status.version_numbers < (1, 52, 0):
        state = "unsupported_version"
    elif status.backend_state in {"NeedsLogin", "NeedsMachineAuth", "NoState"} or status.auth_url:
        state = "needs_login"
    elif status.backend_state == "Stopped":
        state = "stopped"
    elif status.backend_state != "Running" or not status.online:
        state = "offline"
    elif not status.cert_domains or "https" not in status.capabilities:
        state = "https_disabled"
    elif "funnel" not in status.capabilities:
        state = "funnel_not_allowed"
    if state is not None:
        return FunnelStatus(state, version=version)
    host = status.dns_name.removesuffix(".")
    if not re.fullmatch(r"[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?\.ts\.net", host) or any(
        not label or len(label) > 63 or label.startswith("-") or label.endswith("-")
        for label in host.split(".")
    ):
        return FunnelStatus("error", version=version)
    live = next((port for port in ports if own_route(serve, host, port, visitor_port)), None)
    free = free_ports(serve, ports)
    port = live if live is not None else next(iter(free), None)
    if port is None:
        return FunnelStatus("no_free_port", version=version)
    return FunnelStatus(
        "live" if live is not None else "ready",
        f"https://{host}" + (f":{port}" if port != 443 else ""),
        port,
        version,
    )
