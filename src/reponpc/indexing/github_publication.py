"""Concrete, allowlisted GitHub Release publication adapter.

The publication coordinator owns ordering.  This module owns only the narrow
GitHub REST mutations needed to create an immutable release asset and advance
the fixed stable-manifest pointer after that asset is reachable.
"""

from __future__ import annotations

import base64
import hashlib
import json
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from http.client import HTTPMessage
from typing import IO, Final, Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlsplit, urlunsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from reponpc.indexing.publication import PublicationError

_REPOSITORY_RE: Final = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
_GIT_BLOB_SHA_RE: Final = re.compile(r"^[0-9a-f]{40}$")


@dataclass(frozen=True, slots=True)
class GitHubHttpResponse:
    """A bounded HTTP response with no request URL/body echoing."""

    status: int
    headers: Mapping[str, str]
    body: bytes


class GitHubReleaseTransport(Protocol):
    """Small injectable HTTP boundary used by the concrete publisher."""

    def request(
        self,
        method: str,
        url: str,
        *,
        headers: Mapping[str, str],
        body: bytes | None,
    ) -> GitHubHttpResponse:
        """Issue one bounded request without accepting unchecked redirects."""


class _NoRedirect(HTTPRedirectHandler):
    """Follow only redirects whose targets satisfy the GitHub host policy."""

    def __init__(self, allowed_hosts: set[str]) -> None:
        super().__init__()
        self._allowed_hosts = allowed_hosts

    def redirect_request(
        self, req: Request, fp: IO[bytes], code: int, msg: str, headers: HTTPMessage, newurl: str
    ) -> Request | None:
        _validate_allowed_https_url(newurl, self._allowed_hosts)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class UrllibGitHubReleaseTransport:
    """Production stdlib transport with a fixed HTTPS GitHub host allowlist."""

    def __init__(self, *, allowed_hosts: frozenset[str], timeout_seconds: float = 20.0) -> None:
        if timeout_seconds <= 0:
            raise ValueError("GitHub release timeout must be positive")
        self._allowed_hosts = {host.casefold() for host in allowed_hosts}
        if not self._allowed_hosts:
            raise ValueError("GitHub release host allowlist must not be empty")
        self._timeout_seconds = timeout_seconds

    def request(
        self,
        method: str,
        url: str,
        *,
        headers: Mapping[str, str],
        body: bytes | None,
    ) -> GitHubHttpResponse:
        _validate_allowed_https_url(url, self._allowed_hosts)
        request = Request(url, data=body, headers=dict(headers), method=method)
        try:
            with build_opener(_NoRedirect(self._allowed_hosts)).open(
                request, timeout=self._timeout_seconds
            ) as response:
                _validate_allowed_https_url(response.geturl(), self._allowed_hosts)
                return GitHubHttpResponse(
                    status=int(response.status),
                    headers=dict(response.headers.items()),
                    body=response.read(),
                )
        except PublicationError:
            raise
        except HTTPError as exc:
            return GitHubHttpResponse(
                status=exc.code,
                headers=dict(exc.headers.items()),
                body=exc.read(),
            )
        except (URLError, OSError) as exc:
            raise PublicationError("github_release_request_failed") from exc


@dataclass(slots=True)
class GitHubReleasePublisher:
    """ReleasePublisher implementation with a fixed branch/path mutation scope."""

    repository_slug: str
    token: str = field(repr=False)
    transport: GitHubReleaseTransport
    api_base_url: str = "https://api.github.com"
    stable_branch: str = "reponpc-index"
    stable_manifest_path: str = "stable-manifest.json"
    allowed_hosts: frozenset[str] = frozenset(
        {"api.github.com", "uploads.github.com", "github.com"}
    )
    _release_upload_urls: dict[int, str] = field(default_factory=dict, init=False, repr=False)

    def __post_init__(self) -> None:
        if not _REPOSITORY_RE.fullmatch(self.repository_slug):
            raise ValueError("GitHub publication repository must be owner/name")
        if not self.token:
            raise ValueError("GitHub publication token must be non-empty")
        if self.stable_branch != "reponpc-index":
            raise ValueError("stable manifest branch is fixed by the bundle contract")
        if self.stable_manifest_path != "stable-manifest.json":
            raise ValueError("stable manifest path is fixed by the bundle contract")
        _validate_allowed_https_url(
            self.api_base_url, {host.casefold() for host in self.allowed_hosts}
        )

    def create_immutable_release(self, *, tag: str, name: str) -> int:
        """Create a fresh Release and retain only its validated upload endpoint."""

        response = self._json_request(
            "POST",
            "/releases",
            {"tag_name": tag, "name": name, "draft": False, "prerelease": False},
        )
        payload = _json_object(
            response, expected_statuses={201}, code="github_release_create_failed"
        )
        release_id = payload.get("id")
        upload_url = payload.get("upload_url")
        if isinstance(release_id, bool) or not isinstance(release_id, int):
            raise PublicationError("github_release_create_invalid")
        if not isinstance(upload_url, str):
            raise PublicationError("github_release_create_invalid")
        upload_base = upload_url.split("{", maxsplit=1)[0]
        _validate_allowed_https_url(upload_base, {host.casefold() for host in self.allowed_hosts})
        self._release_upload_urls[release_id] = upload_base
        return release_id

    def upload_immutable_asset(self, *, release_id: int, name: str, content: bytes) -> str:
        """Upload one new asset by the release-provided upload URL only."""

        if not name.startswith("reponpc-index-") or not name.endswith(".tar.zst") or not content:
            raise PublicationError("github_release_asset_invalid")
        upload_base = self._release_upload_urls.get(release_id)
        if upload_base is None:
            raise PublicationError("github_release_unknown")
        parsed = urlsplit(upload_base)
        upload_url = urlunsplit(
            (parsed.scheme, parsed.netloc, parsed.path, f"name={quote(name, safe='')}", "")
        )
        response = self.transport.request(
            "POST",
            upload_url,
            headers=self._headers({"Content-Type": "application/octet-stream"}),
            body=content,
        )
        payload = _json_object(
            response, expected_statuses={201}, code="github_release_upload_failed"
        )
        asset_url = payload.get("browser_download_url")
        asset_name = payload.get("name")
        asset_size = payload.get("size")
        if (
            not isinstance(asset_url, str)
            or asset_name != name
            or isinstance(asset_size, bool)
            or asset_size != len(content)
        ):
            raise PublicationError("github_release_upload_invalid")
        _validate_allowed_https_url(asset_url, {host.casefold() for host in self.allowed_hosts})
        return asset_url

    def verify_asset(self, *, asset_url: str, size: int, sha256: str) -> None:
        """Fetch exact immutable bytes and verify the published asset before pointer write."""

        _validate_allowed_https_url(asset_url, {host.casefold() for host in self.allowed_hosts})
        response = self.transport.request("GET", asset_url, headers=self._headers(), body=None)
        if response.status != 200 or len(response.body) != size:
            raise PublicationError("github_release_verify_failed")
        if hashlib.sha256(response.body).hexdigest() != sha256:
            raise PublicationError("github_release_verify_failed")

    def update_stable_manifest_last(self, *, content: bytes) -> None:
        """Use GitHub Contents API for precisely one fixed stable-pointer mutation."""

        existing = self._contents_request("GET", None)
        current_sha: str | None = None
        if existing.status == 200:
            existing_payload = _json_object(
                existing,
                expected_statuses={200},
                code="github_stable_manifest_read_failed",
            )
            candidate = existing_payload.get("sha")
            if not isinstance(candidate, str) or not _GIT_BLOB_SHA_RE.fullmatch(candidate):
                raise PublicationError("github_stable_manifest_read_invalid")
            current_sha = candidate
        elif existing.status != 404:
            raise PublicationError("github_stable_manifest_read_failed")

        payload: dict[str, str] = {
            "branch": self.stable_branch,
            "content": base64.b64encode(content).decode("ascii"),
            "message": "Publish immutable RepoNPC index manifest",
        }
        if current_sha is not None:
            payload["sha"] = current_sha
        response = self._contents_request("PUT", _canonical_json(payload))
        _json_object(
            response,
            expected_statuses={200, 201},
            code="github_stable_manifest_write_failed",
        )

    def _json_request(
        self, method: str, api_path: str, payload: dict[str, object]
    ) -> GitHubHttpResponse:
        return self.transport.request(
            method,
            self._api_url(self._repository_api_path(api_path)),
            headers=self._headers({"Content-Type": "application/json"}),
            body=_canonical_json(payload),
        )

    def _contents_request(self, method: str, body: bytes | None) -> GitHubHttpResponse:
        path = quote(self.stable_manifest_path, safe="/")
        url = self._api_url(self._repository_api_path(f"/contents/{path}"))
        if method == "GET":
            url += f"?ref={quote(self.stable_branch, safe='')}"
        headers = self._headers({"Content-Type": "application/json"} if body is not None else None)
        return self.transport.request(method, url, headers=headers, body=body)

    def _api_url(self, path: str) -> str:
        url = self.api_base_url.rstrip("/") + path
        _validate_allowed_https_url(url, {host.casefold() for host in self.allowed_hosts})
        return url

    def _repository_api_path(self, suffix: str) -> str:
        owner, repository = self.repository_slug.split("/", maxsplit=1)
        return f"/repos/{quote(owner, safe='')}/{quote(repository, safe='')}{suffix}"

    def _headers(self, additional: Mapping[str, str] | None = None) -> dict[str, str]:
        headers = {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {self.token}",
            "User-Agent": "RepoNPC-index-publisher",
        }
        if additional:
            headers.update(additional)
        return headers


def _json_object(
    response: GitHubHttpResponse,
    *,
    expected_statuses: set[int],
    code: str,
) -> dict[str, object]:
    if response.status not in expected_statuses:
        raise PublicationError(code)
    try:
        payload = json.loads(response.body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PublicationError(code) from exc
    if not isinstance(payload, dict):
        raise PublicationError(code)
    return payload


def _canonical_json(payload: Mapping[str, object]) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _validate_allowed_https_url(value: str, allowed_hosts: set[str]) -> None:
    parsed = urlsplit(value)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.hostname.casefold() not in allowed_hosts
        or parsed.username
        or parsed.password
    ):
        raise PublicationError("github_release_host_not_allowed")
