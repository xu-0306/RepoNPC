"""P2 source resolver tests through its real ref/tree/blob assembly path."""

from __future__ import annotations

import base64
from types import MappingProxyType

import pytest

from reponpc.indexing.exclusions import SourceEntryKind
from reponpc.indexing.github import GitHubSourceResolver, SourceResolutionError

SHA = "b" * 40
BLOB_SHA = "c" * 40


def test_resolver_pins_default_branch_and_preserves_non_regular_tree_entries(monkeypatch) -> None:
    calls: list[str] = []
    responses = {
        "/repos/fixture-owner/demo": {
            "default_branch": "main",
            "html_url": "https://github.com/fixture-owner/demo",
        },
        "/repos/fixture-owner/demo/commits/main": {"sha": SHA},
        f"/repos/fixture-owner/demo/git/trees/{SHA}?recursive=1": {
            "truncated": False,
            "tree": [
                {"path": "src/link", "mode": "120000", "type": "blob", "size": 4},
                {
                    "path": "src/main.py",
                    "mode": "100644",
                    "type": "blob",
                    "size": 12,
                    "sha": BLOB_SHA,
                },
                {"path": "vendor/sub", "mode": "160000", "type": "commit", "size": 0},
            ],
        },
        f"/repos/fixture-owner/demo/git/blobs/{BLOB_SHA}": {
            "encoding": "base64",
            "content": base64.b64encode(b"print('ok')\n").decode("ascii"),
        },
    }

    def fake_get_json(_self, path: str):
        calls.append(path)
        return responses[path]

    monkeypatch.setattr(GitHubSourceResolver, "_get_json", fake_get_json)
    resolver = GitHubSourceResolver()
    resolved = resolver.resolve(slug="fixture-owner/demo", ref=None)

    assert resolved.commit_sha == SHA
    assert resolved.default_branch == "main"
    assert [blob.path for blob in resolved.blobs] == ["src/link", "src/main.py", "vendor/sub"]
    assert [blob.entry_kind for blob in resolved.blobs] == [
        SourceEntryKind.SYMLINK,
        SourceEntryKind.REGULAR_FILE,
        SourceEntryKind.SUBMODULE,
    ]
    assert resolved.blobs[1].content == b"print('ok')\n"
    assert calls[1].endswith("/commits/main")


@pytest.mark.parametrize(
    ("api_base_url", "code"),
    [
        ("http://api.github.com", "value_error"),
        ("https://untrusted.example", "value_error"),
    ],
)
def test_resolver_rejects_non_allowlisted_or_non_https_api_base(
    api_base_url: str, code: str
) -> None:
    assert code == "value_error"
    with pytest.raises(ValueError):
        GitHubSourceResolver(api_base_url=api_base_url)


def test_resolver_rejects_bad_blob_size_without_leaking_blob_content(monkeypatch) -> None:
    def fake_get_json(_self, path: str):
        if path.endswith("/commits/main"):
            return {"sha": SHA}
        if "/git/trees/" in path:
            return {
                "truncated": False,
                "tree": [
                    {
                        "path": "src/main.py",
                        "mode": "100644",
                        "type": "blob",
                        "size": 2,
                        "sha": BLOB_SHA,
                    }
                ],
            }
        if path.endswith(f"/git/blobs/{BLOB_SHA}"):
            return {"encoding": "base64", "content": base64.b64encode(b"wrong").decode("ascii")}
        return {"default_branch": "main", "html_url": "https://github.com/fixture-owner/demo"}

    monkeypatch.setattr(GitHubSourceResolver, "_get_json", fake_get_json)
    with pytest.raises(SourceResolutionError) as error:
        GitHubSourceResolver().resolve(slug="fixture-owner/demo", ref="main")
    assert error.value.code == "github_blob_size_mismatch"
    assert "wrong" not in str(error.value)


def test_resolver_applies_a_hard_response_byte_limit_before_json_parsing(monkeypatch) -> None:
    class Response:
        status = 200
        headers = MappingProxyType({})

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def geturl(self) -> str:
            return "https://api.github.com/oversized"

        def read(self, amount: int) -> bytes:
            assert amount == 17
            return b"x" * amount

    class Opener:
        def open(self, *_args, **_kwargs):
            return Response()

    monkeypatch.setattr("reponpc.indexing.github.build_opener", lambda *_args: Opener())
    resolver = GitHubSourceResolver(max_response_bytes=16)

    with pytest.raises(SourceResolutionError) as error:
        resolver._get_json("/oversized")
    assert error.value.code == "github_response_too_large"
