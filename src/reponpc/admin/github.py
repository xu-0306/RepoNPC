"""Least-privilege GitHub contents and workflow mutation boundary."""

from __future__ import annotations

import base64
import json
import re
from dataclasses import dataclass
from http.client import HTTPMessage
from typing import IO, Final, Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

MAX_RESPONSE_BYTES: Final = 2 * 1024 * 1024


class GitHubAdminError(RuntimeError):
    def __init__(self, code: str, *, current_blob_sha: str | None = None) -> None:
        self.code = code
        self.current_blob_sha = current_blob_sha
        super().__init__("GitHub operation failed")


@dataclass(frozen=True, slots=True)
class GitHubResponse:
    status: int
    body: bytes


class GitHubTransport(Protocol):
    def request(
        self, *, method: str, url: str, headers: dict[str, str], body: bytes | None
    ) -> GitHubResponse: ...


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(
        self,
        req: Request,
        fp: IO[bytes],
        code: int,
        msg: str,
        headers: HTTPMessage,
        newurl: str,
    ) -> Request | None:
        del req, fp, code, msg, headers, newurl
        return None


class UrllibGitHubAdminTransport:
    """Bounded production transport that rejects redirects and non-GitHub targets."""

    def __init__(self, *, timeout_seconds: float = 20.0) -> None:
        if timeout_seconds <= 0:
            raise ValueError("GitHub admin timeout must be positive")
        self._timeout_seconds = timeout_seconds

    def request(
        self, *, method: str, url: str, headers: dict[str, str], body: bytes | None
    ) -> GitHubResponse:
        _validate_api_url(url)
        request = Request(url, data=body, headers=headers, method=method)
        try:
            with build_opener(_NoRedirect()).open(
                request, timeout=self._timeout_seconds
            ) as response:
                _validate_api_url(response.geturl())
                payload = response.read(MAX_RESPONSE_BYTES + 1)
                if len(payload) > MAX_RESPONSE_BYTES:
                    raise GitHubAdminError("GITHUB_ERROR")
                return GitHubResponse(int(response.status), payload)
        except GitHubAdminError:
            raise
        except HTTPError as exc:
            payload = exc.read(MAX_RESPONSE_BYTES + 1)
            if len(payload) > MAX_RESPONSE_BYTES:
                payload = b""
            return GitHubResponse(int(exc.code), payload)
        except (URLError, OSError, TimeoutError) as exc:
            raise GitHubAdminError("GITHUB_ERROR") from exc


@dataclass(frozen=True, slots=True)
class GitFile:
    content: bytes
    blob_sha: str
    commit_sha: str
    updated_at: str | None


@dataclass(frozen=True, slots=True)
class GitCommit:
    path: str
    commit_sha: str
    blob_sha: str


class GitHubAdminClient:
    """Target one configured repository/branch/workflow and no browser-selected scope."""

    def __init__(
        self,
        *,
        repository: str,
        branch: str,
        workflow: str,
        token: str,
        transport: GitHubTransport,
        api_url: str = "https://api.github.com",
    ) -> None:
        if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository):
            raise ValueError("GitHub repository is invalid")
        if not branch or "/" in workflow or not workflow.endswith((".yml", ".yaml")):
            raise ValueError("GitHub fixed target is invalid")
        if api_url != "https://api.github.com" or not token:
            raise ValueError("GitHub admin endpoint configuration is invalid")
        self._repository = repository
        self._branch = branch
        self._workflow = workflow
        self._token = token
        self._transport = transport
        self._api_url = api_url

    def read_config(self) -> GitFile:
        return self.read("reponpc.yml")

    def read(self, path: str) -> GitFile:
        path = _allowed_path(path)
        commit_sha, updated_at = self._branch_commit()
        response = self._request("GET", self._contents_url(path, ref=commit_sha), None)
        if response.status == 404:
            raise GitHubAdminError("NOT_FOUND")
        payload = _json(response, expected=(200,))
        try:
            content = base64.b64decode(str(payload["content"]), validate=True)
            return GitFile(
                content=content,
                blob_sha=str(payload["sha"]),
                commit_sha=commit_sha,
                updated_at=updated_at,
            )
        except (KeyError, ValueError, TypeError) as exc:
            raise GitHubAdminError("GITHUB_ERROR") from exc

    def write(
        self,
        *,
        path: str,
        content: bytes,
        expected_blob_sha: str | None,
        commit_message: str,
    ) -> GitCommit:
        path = _allowed_path(path)
        message = " ".join(commit_message.split())[:120] or "Update RepoNPC configuration"
        current: GitFile | None
        try:
            current = self.read(path)
        except GitHubAdminError as exc:
            if exc.code != "NOT_FOUND":
                raise
            current = None
        if current is None and expected_blob_sha is not None:
            raise GitHubAdminError("CONFIG_CONFLICT")
        if current is not None and (
            expected_blob_sha is None or expected_blob_sha != current.blob_sha
        ):
            raise GitHubAdminError("CONFIG_CONFLICT", current_blob_sha=current.blob_sha)
        request: dict[str, object] = {
            "message": message,
            "content": base64.b64encode(content).decode("ascii"),
            "branch": self._branch,
        }
        if current is not None:
            request["sha"] = current.blob_sha
        response = self._request(
            "PUT",
            self._contents_url(path),
            json.dumps(request, separators=(",", ":")).encode(),
        )
        if response.status == 409:
            raise GitHubAdminError("CONFIG_CONFLICT")
        payload = _json(response, expected=(200, 201))
        try:
            commit_payload = payload["commit"]
            content_payload = payload["content"]
            if not isinstance(commit_payload, dict) or not isinstance(content_payload, dict):
                raise TypeError
            return GitCommit(
                path=path,
                commit_sha=str(commit_payload["sha"]),
                blob_sha=str(content_payload["sha"]),
            )
        except (KeyError, TypeError) as exc:
            raise GitHubAdminError("GITHUB_ERROR") from exc

    def dispatch_index(self) -> None:
        url = (
            f"{self._api_url}/repos/{self._repository}/actions/workflows/"
            f"{quote(self._workflow, safe='')}/dispatches"
        )
        body = json.dumps({"ref": self._branch}, separators=(",", ":")).encode()
        response = self._request("POST", url, body)
        if response.status != 204:
            raise GitHubAdminError("GITHUB_ERROR")

    def _branch_commit(self) -> tuple[str, str | None]:
        response = self._request(
            "GET",
            f"{self._api_url}/repos/{self._repository}/commits/{quote(self._branch, safe='')}",
            None,
        )
        payload = _json(response, expected=(200,))
        commit_sha = str(payload.get("sha", ""))
        if not re.fullmatch(r"[0-9a-f]{40}", commit_sha):
            raise GitHubAdminError("GITHUB_ERROR")
        updated_at: str | None = None
        commit = payload.get("commit")
        if isinstance(commit, dict):
            committer = commit.get("committer")
            if isinstance(committer, dict) and isinstance(committer.get("date"), str):
                updated_at = str(committer["date"])
        return commit_sha, updated_at

    def _contents_url(self, path: str, *, ref: str | None = None) -> str:
        resolved_ref = self._branch if ref is None else ref
        return (
            f"{self._api_url}/repos/{self._repository}/contents/{quote(path, safe='/')}"
            f"?ref={quote(resolved_ref, safe='')}"
        )

    def _request(self, method: str, url: str, body: bytes | None) -> GitHubResponse:
        try:
            return self._transport.request(
                method=method,
                url=url,
                headers={
                    "Accept": "application/vnd.github+json",
                    "Authorization": f"Bearer {self._token}",
                    "X-GitHub-Api-Version": "2022-11-28",
                },
                body=body,
            )
        except GitHubAdminError:
            raise
        except Exception as exc:
            raise GitHubAdminError("GITHUB_ERROR") from exc


def _allowed_path(path: str) -> str:
    if path == "reponpc.yml":
        return path
    if re.fullmatch(r"assets/character/[a-z][a-z0-9_-]{0,63}\.png", path):
        return path
    raise GitHubAdminError("WRITE_NOT_ALLOWED")


def _json(response: GitHubResponse, *, expected: tuple[int, ...]) -> dict[str, object]:
    if response.status not in expected:
        raise GitHubAdminError("GITHUB_ERROR")
    try:
        payload = json.loads(response.body)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise GitHubAdminError("GITHUB_ERROR") from exc
    if not isinstance(payload, dict):
        raise GitHubAdminError("GITHUB_ERROR")
    return payload


def _validate_api_url(url: str) -> None:
    parsed = urlsplit(url)
    if (
        parsed.scheme != "https"
        or parsed.hostname != "api.github.com"
        or parsed.port not in {None, 443}
        or parsed.username
        or parsed.password
    ):
        raise GitHubAdminError("GITHUB_ERROR")
