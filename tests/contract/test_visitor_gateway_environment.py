from __future__ import annotations

from pathlib import Path

import pytest

from reponpc.config.environment import (
    EnvironmentValidationError,
    _canonical_origin,
    load_environment,
)


def values(**overrides: str) -> dict[str, str]:
    result = {
        "REPONPC_PUBLIC_BASE_URL": "https://portfolio.example.com",
        "REPONPC_CONFIG_REPOSITORY": "example/portfolio",
        "REPONPC_INDEX_MANIFEST_URL": "https://example.invalid/manifest.json",
    }
    result.update(overrides)
    return result


@pytest.mark.parametrize(
    "origin, expected",
    [
        ("HTTPS://Admin.Example.com:443", "https://admin.example.com"),
        ("https://admin.example.com:8443", "https://admin.example.com:8443"),
        ("https://admin.example.com/", None),
        ("https://user:password@admin.example.com", None),
        ("https://測試.example", None),
        ("https://xn--g6w251d.example", "https://xn--g6w251d.example"),
        ("https://[2001:0DB8:0000::1]:443", "https://[2001:db8::1]"),
        ("https://[fe80::1%25eth0]", None),
        ("https://admin.example.com.", None),
        ("https://127.000.000.001", None),
        ("https://admin.example.com:0", None),
        ("https://admin.example.com:", None),
        ("http://admin.example.com", None),
        ("http://127.0.0.1:80", "http://127.0.0.1"),
        ("http://[::1]:9000", "http://[::1]:9000"),
        ("ftp://admin.example.com", None),
    ],
)
def test_shared_origin_boundary_uses_strict_rules(origin: str, expected: str | None) -> None:
    assert _canonical_origin(origin) == expected
    assert _canonical_origin(origin, https_only=True) == (
        expected if expected is not None and expected.startswith("https://") else None
    )


def test_gateway_environment_defaults_to_loopback_aggregate_and_base_admin_origin(
    tmp_path: Path,
) -> None:
    settings = load_environment(values(), secret_roots=(tmp_path,))

    assert settings.visitor_gateway_port == 8001
    assert settings.visitor_trusted_proxy_cidrs == ()
    assert settings.admin_origins == ("https://portfolio.example.com",)
    assert not settings.admin_origins_explicit


def test_gateway_environment_normalizes_admin_origins_and_accepts_loopback_trust(
    tmp_path: Path,
) -> None:
    settings = load_environment(
        values(
            REPONPC_ADMIN_ORIGINS="HTTPS://Admin.Example.com:443,http://127.0.0.1:9000",
            REPONPC_VISITOR_TRUSTED_PROXY_CIDRS="127.0.0.0/8,::1/128",
            REPONPC_VISITOR_GATEWAY_PORT="8123",
        ),
        secret_roots=(tmp_path,),
    )

    assert settings.admin_origins == (
        "https://admin.example.com",
        "http://127.0.0.1:9000",
    )
    assert settings.admin_origins_explicit
    assert settings.visitor_trusted_proxy_cidrs == ("127.0.0.0/8", "::1/128")
    assert settings.visitor_gateway_port == 8123


@pytest.mark.parametrize(
    "origin",
    [
        "https://admin.example.com/path",
        "https://user@admin.example.com",
        "https://admin.example.com?query",
        "https://admin.example.com#fragment",
        "https://admin.example.com:bad",
        "https://admin.example.com:",
        "https://admin.example.com\\evil",
        "https://127.000.000.001",
    ],
)
def test_admin_origins_reject_url_components_and_ambiguous_authorities(
    tmp_path: Path, origin: str
) -> None:
    with pytest.raises(EnvironmentValidationError) as raised:
        load_environment(values(REPONPC_ADMIN_ORIGINS=origin), secret_roots=(tmp_path,))
    assert any(issue.name == "REPONPC_ADMIN_ORIGINS" for issue in raised.value.issues)


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("REPONPC_VISITOR_TRUSTED_PROXY_CIDRS", "10.0.0.1/32"),
        ("REPONPC_VISITOR_TRUSTED_PROXY_CIDRS", "127.0.0.1/24"),
        ("REPONPC_VISITOR_TRUSTED_PROXY_CIDRS", "127.0.0.1/32,127.0.0.1/32"),
        ("REPONPC_VISITOR_GATEWAY_PORT", "8000"),
        ("REPONPC_VISITOR_GATEWAY_PORT", "65536"),
    ],
)
def test_visitor_gateway_environment_rejects_invalid_proxy_and_port_settings(
    tmp_path: Path, name: str, value: str
) -> None:
    with pytest.raises(EnvironmentValidationError) as raised:
        load_environment(values(**{name: value}), secret_roots=(tmp_path,))
    assert any(issue.name == name for issue in raised.value.issues)
