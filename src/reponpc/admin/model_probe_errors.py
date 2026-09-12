"""Allowlisted diagnostics for persisted, authenticated model test results."""

from reponpc.providers.contracts import ProviderError


def provider_probe_error_code(error: ProviderError) -> str:
    """Keep HTTP evidence when available, without copying provider text or URLs."""

    if error.upstream_status is not None:
        return f"PROVIDER_HTTP_{error.upstream_status}"
    return f"PROVIDER_{error.code.value.upper()}"
