"""Bounded, content-addressed cache for validated passage embeddings.

The cache is deliberately a small adapter around the embedding-provider
contract.  It stores one vector per exact passage and embedding identity, so
callers can reuse unchanged passages without making the cache part of the
provider or index lifecycle.  Cache files contain only hashed identity/text
inputs and validated vector bytes; source text and provider connection data do
not cross the persistence boundary.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
import math
import os
import re
import tempfile
import time
from collections.abc import Callable
from contextlib import suppress
from pathlib import Path
from threading import RLock
from typing import Any, Final

import numpy as np
from numpy.typing import NDArray

from reponpc.indexing.sources import EmbeddingProvider

PASSAGE_CACHE_VERSION: Final[str] = "passage-vector-v1"
"""Version for the cache key and on-disk envelope."""

DEFAULT_MAX_BYTES: Final[int] = 256 * 1024 * 1024
DEFAULT_TTL_SECONDS: Final[float] = 30 * 24 * 60 * 60
_ENVELOPE_FORMAT_VERSION: Final[int] = 1
_VECTOR_DTYPE: Final[str] = "float32"
_KEY_RE: Final[re.Pattern[str]] = re.compile(r"^[0-9a-f]{64}\.json$")
_HASH_RE: Final[re.Pattern[str]] = re.compile(r"^[0-9a-f]{64}$")
_ENVELOPE_KEYS: Final[frozenset[str]] = frozenset(
    {
        "format_version",
        "key",
        "identity_sha256",
        "dimension",
        "normalized",
        "dtype",
        "shape",
        "created_at",
        "expires_at",
        "vector_base64",
        "vector_sha256",
        "payload_sha256",
    }
)
_UNIT_NORM_RTOL: Final[float] = 1e-5
_UNIT_NORM_ATOL: Final[float] = 1e-6

_LOCK_REGISTRY_GUARD = RLock()
_ROOT_LOCKS: dict[Path, RLock] = {}

NDArrayFloat32 = NDArray[np.float32]


class PassageVectorCache:
    """Reuse validated passage vectors within bounded disposable storage."""

    def __init__(
        self,
        root: Path,
        *,
        max_bytes: int = DEFAULT_MAX_BYTES,
        ttl_seconds: float = DEFAULT_TTL_SECONDS,
        clock: Callable[[], float] = time.time,
    ) -> None:
        if isinstance(max_bytes, bool) or not isinstance(max_bytes, int) or max_bytes <= 0:
            raise ValueError("cache max_bytes must be a positive integer")
        if isinstance(ttl_seconds, bool) or not isinstance(ttl_seconds, (int, float)):
            raise ValueError("cache ttl_seconds must be a positive finite number")
        if not math.isfinite(float(ttl_seconds)) or float(ttl_seconds) <= 0:
            raise ValueError("cache ttl_seconds must be a positive finite number")
        if not callable(clock):
            raise TypeError("cache clock must be callable")

        self._root = Path(root)
        self._max_bytes = max_bytes
        self._ttl_seconds = float(ttl_seconds)
        self._clock = clock
        self._lock = _lock_for_root(self._root)

    def embed_passages(self, provider: EmbeddingProvider, texts: list[str]) -> NDArrayFloat32:
        """Return vectors in input order, delegating only cache misses once.

        The provider is the only source of new vectors.  A provider exception
        or malformed response is propagated to the caller; persistence errors
        are isolated and never turn a valid provider response into a failure.
        """

        if not isinstance(texts, list):
            raise TypeError("passage texts must be a list of strings")
        if any(not isinstance(text, str) for text in texts):
            raise TypeError("passage texts must be a list of strings")

        with self._lock:
            identity = _identity_payload(provider.identity())
            identity_bytes = _canonical_json(identity).encode("utf-8")
            identity_sha256 = hashlib.sha256(identity_bytes).hexdigest()
            dimension = identity["dimension"]
            assert isinstance(dimension, int)
            now = self._now()

            if not texts:
                return np.empty((0, dimension), dtype=np.float32)

            keys = [_passage_key(identity, text) for text in texts]
            output = np.empty((len(texts), dimension), dtype=np.float32)
            missing_texts: list[str] = []
            missing_keys: list[str] = []
            key_to_missing_index: dict[str, int] = {}

            for row, key in enumerate(keys):
                vector = self._read_entry(
                    key,
                    identity_sha256=identity_sha256,
                    dimension=dimension,
                    now=now,
                )
                if vector is not None:
                    output[row] = vector
                    continue

                pending_index = key_to_missing_index.get(key)
                if pending_index is None:
                    pending_index = len(missing_texts)
                    key_to_missing_index[key] = pending_index
                    missing_texts.append(texts[row])
                    missing_keys.append(key)

            if missing_texts:
                provided = provider.embed_passages(missing_texts)
                vectors = _validate_provider_output(
                    provided,
                    count=len(missing_texts),
                    dimension=dimension,
                )
                for key, vector in zip(missing_keys, vectors, strict=True):
                    self._store_entry(
                        key,
                        identity_sha256=identity_sha256,
                        dimension=dimension,
                        vector=vector,
                        created_at=now,
                    )

                for row, key in enumerate(keys):
                    pending_index = key_to_missing_index.get(key)
                    if pending_index is not None:
                        output[row] = vectors[pending_index]

                self._evict(now=now)

            return output

    def _now(self) -> float:
        try:
            now = float(self._clock())
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError("cache clock must return a finite number") from exc
        if not math.isfinite(now):
            raise ValueError("cache clock must return a finite number")
        return now

    def _path_for_key(self, key: str) -> Path:
        return self._root / f"{key}.json"

    def _read_entry(
        self,
        key: str,
        *,
        identity_sha256: str,
        dimension: int,
        now: float,
    ) -> NDArrayFloat32 | None:
        path = self._path_for_key(key)
        decoded = _decode_entry(path, max_bytes=self._max_bytes)
        if decoded is None:
            if _path_is_present(path):
                _discard(path)
            return None

        payload, vector = decoded
        if (
            payload["key"] != key
            or payload["identity_sha256"] != identity_sha256
            or payload["dimension"] != dimension
            or payload["expires_at"] <= now
        ):
            if payload["expires_at"] <= now:
                _discard(path)
            return None
        return vector

    def _store_entry(
        self,
        key: str,
        *,
        identity_sha256: str,
        dimension: int,
        vector: NDArrayFloat32,
        created_at: float,
    ) -> None:
        vector_le = np.asarray(vector, dtype=np.dtype("<f4"))
        vector_bytes = vector_le.tobytes(order="C")
        payload: dict[str, object] = {
            "format_version": _ENVELOPE_FORMAT_VERSION,
            "key": key,
            "identity_sha256": identity_sha256,
            "dimension": dimension,
            "normalized": True,
            "dtype": _VECTOR_DTYPE,
            "shape": [dimension],
            "created_at": created_at,
            "expires_at": created_at + self._ttl_seconds,
            "vector_base64": base64.b64encode(vector_bytes).decode("ascii"),
            "vector_sha256": hashlib.sha256(vector_bytes).hexdigest(),
        }
        payload["payload_sha256"] = hashlib.sha256(
            _canonical_json(payload).encode("utf-8")
        ).hexdigest()
        try:
            data = _canonical_json(payload).encode("utf-8")
        except (TypeError, ValueError, OverflowError):
            return
        if len(data) > self._max_bytes:
            return
        if not _ensure_directory(self._root):
            return

        temporary_path: Path | None = None
        try:
            descriptor, temporary_name = tempfile.mkstemp(
                prefix=f".{key}.", suffix=".tmp", dir=self._root
            )
            temporary_path = Path(temporary_name)
            with os.fdopen(descriptor, "wb") as temporary_file:
                os.chmod(temporary_path, 0o600)
                temporary_file.write(data)
                temporary_file.flush()
                os.fsync(temporary_file.fileno())
            os.replace(temporary_path, self._path_for_key(key))
            temporary_path = None
        except OSError:
            if temporary_path is not None:
                _discard(temporary_path)

    def _evict(self, *, now: float) -> None:
        try:
            if not self._root.is_dir():
                return
            entries: list[tuple[float, int, Path]] = []
            for path in self._root.iterdir():
                if not _KEY_RE.fullmatch(path.name) or path.is_symlink():
                    continue
                decoded = _decode_entry(path, max_bytes=self._max_bytes)
                if decoded is None:
                    _discard(path)
                    continue
                payload, _vector = decoded
                if payload["expires_at"] <= now:
                    _discard(path)
                    continue
                try:
                    size = path.stat().st_size
                except OSError:
                    continue
                entries.append((payload["created_at"], size, path))
        except OSError:
            return

        total = sum(size for _created_at, size, _path in entries)
        if total <= self._max_bytes:
            return
        for _created_at, size, path in sorted(entries, key=lambda item: (item[0], item[2].name)):
            if total <= self._max_bytes:
                break
            _discard(path)
            total -= size


def _lock_for_root(root: Path) -> RLock:
    try:
        key = root.resolve(strict=False)
    except OSError:
        key = root.absolute()
    with _LOCK_REGISTRY_GUARD:
        lock = _ROOT_LOCKS.get(key)
        if lock is None:
            lock = RLock()
            _ROOT_LOCKS[key] = lock
        return lock


def _identity_payload(identity: object) -> dict[str, object]:
    """Extract only the provider identity fields needed for cache semantics."""

    try:
        adapter = identity.adapter  # type: ignore[attr-defined]
        model_id = identity.model_id  # type: ignore[attr-defined]
        dimension = identity.dimension  # type: ignore[attr-defined]
        normalized = identity.normalized  # type: ignore[attr-defined]
        query_prefix = identity.query_prefix  # type: ignore[attr-defined]
        passage_prefix = identity.passage_prefix  # type: ignore[attr-defined]
    except AttributeError as exc:
        raise TypeError("provider identity must expose the embedding contract") from exc

    if not isinstance(adapter, str) or not adapter:
        raise ValueError("embedding adapter must be a non-empty string")
    if not isinstance(model_id, str) or not model_id:
        raise ValueError("embedding model_id must be a non-empty string")
    if isinstance(dimension, bool) or not isinstance(dimension, int) or dimension <= 0:
        raise ValueError("embedding dimension must be a positive integer")
    if normalized is not True:
        raise ValueError("cache requires normalized embeddings")
    if not isinstance(query_prefix, str) or not isinstance(passage_prefix, str):
        raise ValueError("embedding prefixes must be strings")
    return {
        "adapter": adapter,
        "model_id": model_id,
        "dimension": dimension,
        "normalized": normalized,
        "query_prefix": query_prefix,
        "passage_prefix": passage_prefix,
    }


def _passage_key(identity: dict[str, object], text: str) -> str:
    material = _canonical_json(
        {"cache_version": PASSAGE_CACHE_VERSION, "identity": identity, "text": text}
    ).encode("utf-8")
    return hashlib.sha256(material).hexdigest()


def _canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _validate_provider_output(value: object, *, count: int, dimension: int) -> NDArrayFloat32:
    if not isinstance(value, np.ndarray) or value.dtype != np.dtype(np.float32):
        raise ValueError("embedding provider returned invalid vectors")
    if value.shape != (count, dimension):
        raise ValueError("embedding provider returned invalid vectors")
    vectors = value.astype(np.float32, copy=True)
    if not np.isfinite(vectors).all():
        raise ValueError("embedding provider returned invalid vectors")
    norms = np.linalg.vector_norm(vectors, axis=1)
    if not np.allclose(norms, 1.0, rtol=_UNIT_NORM_RTOL, atol=_UNIT_NORM_ATOL):
        raise ValueError("embedding provider returned invalid vectors")
    return vectors


def _decode_entry(path: Path, *, max_bytes: int) -> tuple[dict[str, Any], NDArrayFloat32] | None:
    try:
        if path.is_symlink() or not path.is_file() or path.stat().st_size > max_bytes:
            return None
        data = path.read_bytes()
        if len(data) > max_bytes:
            return None
        payload = json.loads(data.decode("utf-8"), parse_constant=_reject_json_constant)
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError, TypeError):
        return None
    if not isinstance(payload, dict) or frozenset(payload) != _ENVELOPE_KEYS:
        return None

    try:
        if (
            isinstance(payload["format_version"], bool)
            or not isinstance(payload["format_version"], int)
            or payload["format_version"] != _ENVELOPE_FORMAT_VERSION
        ):
            return None
        key = payload["key"]
        identity_sha256 = payload["identity_sha256"]
        if not isinstance(key, str) or not _HASH_RE.fullmatch(key):
            return None
        if path.name != f"{key}.json":
            return None
        if not isinstance(identity_sha256, str) or not _HASH_RE.fullmatch(identity_sha256):
            return None
        if not isinstance(payload["dimension"], int) or isinstance(payload["dimension"], bool):
            return None
        dimension = payload["dimension"]
        if dimension <= 0 or payload["normalized"] is not True:
            return None
        shape = payload["shape"]
        if (
            payload["dtype"] != _VECTOR_DTYPE
            or not isinstance(shape, list)
            or len(shape) != 1
            or isinstance(shape[0], bool)
            or not isinstance(shape[0], int)
            or shape[0] != dimension
        ):
            return None
        created_at = _finite_number(payload["created_at"])
        expires_at = _finite_number(payload["expires_at"])
        if expires_at <= created_at:
            return None
        vector_base64 = payload["vector_base64"]
        vector_sha256 = payload["vector_sha256"]
        payload_sha256 = payload["payload_sha256"]
        if not isinstance(vector_base64, str):
            return None
        if not isinstance(vector_sha256, str) or not _HASH_RE.fullmatch(vector_sha256):
            return None
        if not isinstance(payload_sha256, str) or not _HASH_RE.fullmatch(payload_sha256):
            return None
        without_checksum = dict(payload)
        del without_checksum["payload_sha256"]
        expected_payload_hash = hashlib.sha256(
            _canonical_json(without_checksum).encode("utf-8")
        ).hexdigest()
        if payload_sha256 != expected_payload_hash:
            return None
        vector_bytes = base64.b64decode(vector_base64, validate=True)
        if len(vector_bytes) != dimension * np.dtype(np.float32).itemsize:
            return None
        if hashlib.sha256(vector_bytes).hexdigest() != vector_sha256:
            return None
        vector = np.frombuffer(vector_bytes, dtype=np.dtype("<f4")).copy()
        _validate_provider_output(vector.reshape(1, dimension), count=1, dimension=dimension)
    except (binascii.Error, UnicodeError, TypeError, ValueError, OverflowError):
        return None
    return payload, vector


def _finite_number(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("cache timestamp is invalid")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError("cache timestamp is invalid")
    return number


def _reject_json_constant(value: str) -> None:
    raise ValueError(f"invalid JSON number: {value}")


def _ensure_directory(root: Path) -> bool:
    try:
        root.mkdir(parents=True, exist_ok=True)
        return root.is_dir()
    except OSError:
        return False


def _path_is_present(path: Path) -> bool:
    try:
        return path.exists() or path.is_symlink()
    except OSError:
        return False


def _discard(path: Path) -> None:
    with suppress(OSError):
        path.unlink(missing_ok=True)
