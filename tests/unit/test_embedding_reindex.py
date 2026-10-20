"""Closed source classification and unchanged safe reindex failure mappings."""

from __future__ import annotations

import pytest

from reponpc.admin.batch_resolver import BatchResolverError
from reponpc.admin.embedding_profiles import EmbeddingProfileError
from reponpc.admin.embedding_reindex import (
    ReindexCancelled,
    ReindexTimedOut,
    SourceFailureCode,
    _safe_reindex_error,
)
from reponpc.bundles.archive import BundleError
from reponpc.bundles.manager import BundleActivationError
from reponpc.indexing.github import SourceResolutionError
from reponpc.indexing.pipeline import IndexPipelineError
from reponpc.providers.contracts import ProviderError, ProviderFailureCode


@pytest.mark.parametrize("error_type", [BatchResolverError, SourceResolutionError])
@pytest.mark.parametrize(
    "code",
    [
        "GITHUB_RATE_LIMITED",
        "GITHUB_ERROR",
        "GITHUB_TIMEOUT",
        "NOT_FOUND",
        "ARCHIVED_NOT_ALLOWED",
        "ARCHIVE_TOO_LARGE",
        "ARCHIVE_INVALID",
        "ARCHIVE_UNSAFE",
    ],
)
def test_safe_reindex_error_preserves_every_closed_source_code(error_type, code):
    error = error_type(code)
    error.args = ("private-source-body-canary",)
    assert _safe_reindex_error(error) == code
    assert code in SourceFailureCode


@pytest.mark.parametrize(
    ("code", "expected"),
    [
        ("github_rate_limited", "GITHUB_RATE_LIMITED"),
        ("github_request_failed", "GITHUB_ERROR"),
        ("github_timeout", "GITHUB_TIMEOUT"),
        ("github_not_found", "NOT_FOUND"),
    ],
)
def test_safe_reindex_error_maps_source_resolver_aliases(code, expected):
    assert _safe_reindex_error(SourceResolutionError(code)) == expected
    # The aliases belong only to SourceResolutionError, not arbitrary exceptions.
    assert _safe_reindex_error(BatchResolverError(code)) == "EMBEDDING_REINDEX_FAILED"
    assert _safe_reindex_error(RuntimeError(code)) == "EMBEDDING_REINDEX_FAILED"


@pytest.mark.parametrize(
    "error",
    [
        BatchResolverError("CONFIRMATION_REQUIRED"),
        SourceResolutionError("github_cancelled"),
        SourceResolutionError("github_response_invalid"),
        SourceResolutionError("github_host_not_allowed"),
        RuntimeError("GITHUB_RATE_LIMITED"),
        IndexPipelineError("embedding_output_invalid"),
    ],
)
def test_safe_reindex_error_keeps_out_of_set_failures_generic(error):
    assert _safe_reindex_error(error) == "EMBEDDING_REINDEX_FAILED"


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (ReindexCancelled(), "EMBEDDING_REINDEX_CANCELLED"),
        (ReindexTimedOut(), "EMBEDDING_REINDEX_TIMEOUT"),
        (EmbeddingProfileError("EMBEDDING_REINDEX_STALE"), "EMBEDDING_REINDEX_STALE"),
        (BundleError("bundle_embedding_incompatible"), "EMBEDDING_ACTIVATION_FAILED"),
        (BundleActivationError("bundle_activation_failed"), "EMBEDDING_ACTIVATION_FAILED"),
    ],
)
def test_safe_reindex_error_keeps_existing_mappings(error, expected):
    assert _safe_reindex_error(error) == expected


@pytest.mark.parametrize("code", list(ProviderFailureCode))
def test_safe_reindex_error_keeps_provider_mappings(code):
    expected = (
        "EMBEDDING_REINDEX_TIMEOUT"
        if code == ProviderFailureCode.TIMEOUT
        else "EMBEDDING_REINDEX_FAILED"
    )
    assert _safe_reindex_error(ProviderError(code)) == expected


@pytest.mark.parametrize(
    ("cause", "expected"),
    [
        (ReindexCancelled(), "EMBEDDING_REINDEX_CANCELLED"),
        (ReindexTimedOut(), "EMBEDDING_REINDEX_TIMEOUT"),
    ],
)
def test_safe_reindex_error_keeps_activation_stop_causes(cause, expected):
    error = BundleActivationError("bundle_activation_failed")
    error.__cause__ = cause
    assert _safe_reindex_error(error) == expected
