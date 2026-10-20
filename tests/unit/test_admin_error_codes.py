"""Keep the two owner error mappers aligned with their backend envelopes."""

from __future__ import annotations

import ast
import json
import re
from pathlib import Path

import pytest

from reponpc.admin.embedding_reindex import SourceFailureCode
from reponpc.admin.model_probe_errors import provider_probe_error_code
from reponpc.providers.contracts import ProviderError, ProviderFailureCode

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "src" / "reponpc"
FIXTURE = ROOT / "apps/web/src/features/admin/__fixtures__/adminErrorCodes.json"
CODE = re.compile(r"[A-Z][A-Z0-9_]+")
# The fixture lists the provider HTTP family once; the frontend test expands it.
HTTP_CODE = re.compile(r"PROVIDER_HTTP_[1-5][0-9]{2}")
HTTP_TEMPLATE = "PROVIDER_HTTP_{status}"


def _literal_codes(tree: ast.AST) -> set[str]:
    return {
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and CODE.fullmatch(node.value)
    }


@pytest.mark.parametrize(
    ("family", "constructor", "api_mapper"),
    [
        ("embedding_profile", "EmbeddingProfileError", "_embedding_profile_error"),
        ("guided_onboarding", "GuidedOnboardingError", "_onboarding_error"),
    ],
)
def test_admin_error_code_fixture_covers_backend(
    family: str, constructor: str, api_mapper: str
) -> None:
    # Reviewed non-literal calls: queue can forward stored probe/reindex errors;
    # all three onboarding catches surround acquire_generation (capacity only).
    forwarded = {provider_probe_error_code(ProviderError(code)) for code in ProviderFailureCode} | {
        provider_probe_error_code(
            ProviderError(ProviderFailureCode.UNAVAILABLE, upstream_status=status)
        )
        for status in range(100, 600)
    }
    reindex_tree = ast.parse((SOURCE / "admin/embedding_reindex.py").read_text(encoding="utf-8"))
    safe_reindex = next(
        node
        for node in reindex_tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "_safe_reindex_error"
    )
    forwarded |= _literal_codes(safe_reindex) | {code.value for code in SourceFailureCode}
    # Probe's catch-all and persisted restart/bundle recovery markers.
    forwarded |= {
        "EMBEDDING_PROBE_FAILED",
        "EMBEDDING_REINDEX_INTERRUPTED",
        "EMBEDDING_BUNDLE_UNAVAILABLE",
    }
    # (file, argument source) -> (number of calls, codes they can carry)
    dynamic = (
        {("admin/embedding_reindex.py", "profile.last_error_code"): (1, forwarded)}
        if family == "embedding_profile"
        else {("admin/onboarding.py", "exc.code"): (3, {"CONCURRENCY_LIMIT"})}
    )
    emitted: set[str] = set()
    seen_dynamic: dict[tuple[str, str], int] = {}
    for path in sorted(SOURCE.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8-sig"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            name = (
                node.func.id
                if isinstance(node.func, ast.Name)
                else node.func.attr
                if isinstance(node.func, ast.Attribute)
                else None
            )
            if name != constructor:
                continue
            argument = (
                node.args[0]
                if node.args
                else next((item.value for item in node.keywords if item.arg == "code"), None)
            )
            if isinstance(argument, ast.Constant) and isinstance(argument.value, str):
                emitted.add(argument.value)
                continue
            relative = path.relative_to(SOURCE).as_posix()
            key = (relative, ast.unparse(argument) if argument is not None else "")
            assert key in dynamic, (
                f"Unreviewed non-literal {constructor} at {relative}:{node.lineno}"
            )
            seen_dynamic[key] = seen_dynamic.get(key, 0) + 1
            emitted |= dynamic[key][1]
    assert seen_dynamic == {key: count for key, (count, _) in dynamic.items()}
    api_tree = ast.parse((SOURCE / "api/admin.py").read_text(encoding="utf-8"))
    mapper = next(
        node
        for node in api_tree.body
        if isinstance(node, ast.FunctionDef) and node.name == api_mapper
    )
    emitted |= _literal_codes(mapper)
    emitted = {HTTP_TEMPLATE if HTTP_CODE.fullmatch(code) else code for code in emitted}
    classification = json.loads(FIXTURE.read_text(encoding="utf-8"))[family]
    mapped = classification["mapped"]
    generic = classification["generic"]
    assert len(mapped) == len(set(mapped))
    assert not set(mapped) & set(generic)
    assert all(isinstance(reason, str) and reason.strip() for reason in generic.values())
    assert set(mapped) | set(generic) == emitted
