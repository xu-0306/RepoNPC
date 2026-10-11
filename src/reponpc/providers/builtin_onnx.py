"""Local-only, lazy CPU inference for the verified built-in bge-m3 graph.

The pinned graph exposes ``sentence_embedding`` and ``token_embeddings``.
Its pinned 1_Pooling/config.json specifies CLS pooling; a token-only graph must
therefore use token zero, never mean pooling or an unnamed output. Artifact
identity and integrity belong to builtin_artifacts, not this inference leaf.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from threading import Lock
from typing import Any

import numpy as np
from numpy.typing import NDArray

from reponpc.indexing.sources import EmbeddingIdentity
from reponpc.providers.builtin_artifacts import (
    builtin_embedding_identity,
    load_builtin_manifest,
    verify_builtin_artifacts,
)
from reponpc.providers.contracts import (
    ProviderError,
    ProviderFailureCode,
    ProviderHealth,
    RuntimeEmbeddingProvider,
)

_MAX_TOKEN_ID = int(np.iinfo(np.int64).max)


def _load_tokenizer(path: Path) -> Any:
    from tokenizers import Tokenizer

    return Tokenizer.from_file(str(path))


def _load_session(path: Path) -> Any:
    import onnxruntime as ort  # type: ignore[import-untyped]

    ort.disable_telemetry_events()
    options = ort.SessionOptions()
    options.intra_op_num_threads = 4
    options.inter_op_num_threads = 1
    options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
    options.log_severity_level = 4
    session = ort.InferenceSession(
        str(path), sess_options=options, providers=["CPUExecutionProvider"]
    )
    session.disable_fallback()
    return session


class BuiltinOnnxEmbeddingProvider(RuntimeEmbeddingProvider):
    """Synchronous provider; the caller owns scheduling and instance lifecycle.

    One lock serializes loading and inference so concurrent callers cannot
    multiply model or activation memory. Each padded batch is bounded by both
    rows and tokens. Factories are internal test seams, not owner configuration.
    """

    def __init__(
        self,
        model_dir: Path,
        *,
        verify_artifacts: Callable[[Path], Path] = verify_builtin_artifacts,
        tokenizer_factory: Callable[[Path], Any] = _load_tokenizer,
        session_factory: Callable[[Path], Any] = _load_session,
        max_batch_size: int = 8,
    ) -> None:
        try:
            self._identity = builtin_embedding_identity()
            self._context_tokens = load_builtin_manifest().context_tokens
        except Exception:
            raise ProviderError(ProviderFailureCode.UNAVAILABLE) from None
        if type(max_batch_size) is not int or not 1 <= max_batch_size <= 8:
            raise ValueError("invalid built-in inference batch bounds")
        self._model_dir = model_dir
        self._verify_artifacts = verify_artifacts
        self._tokenizer_factory = tokenizer_factory
        self._session_factory = session_factory
        self._max_batch_size = max_batch_size
        self._max_batch_tokens = self._context_tokens
        self._lock = Lock()
        self._tokenizer: Any = None
        self._session: Any = None
        self._closed = False
        self._pad_id = 0
        self._input_names: set[str] = set()
        self._output_name = ""

    def __repr__(self) -> str:
        return f"BuiltinOnnxEmbeddingProvider(identity={self._identity!r})"

    def identity(self) -> EmbeddingIdentity:
        return self._identity

    def close(self) -> None:
        """Release this app-owned session once all users have stopped."""
        with self._lock:
            self._closed = True
            self._session = None
            self._tokenizer = None

    def embed_query(self, texts: list[str]) -> NDArray[np.float32]:
        return self._embed(texts)

    def embed_passages(self, texts: list[str]) -> NDArray[np.float32]:
        return self._embed(texts)

    def health(self) -> ProviderHealth:
        checked_at = datetime.now(UTC).isoformat()
        try:
            self._embed(["RepoNPC embedding health"])
        except ProviderError as error:
            return ProviderHealth(False, checked_at, error.code)
        return ProviderHealth(True, checked_at)

    def _load(self) -> None:
        if self._closed:
            raise ProviderError(ProviderFailureCode.UNAVAILABLE)
        if self._session is not None:
            return
        try:
            root = self._verify_artifacts(self._model_dir)
            tokenizer = self._tokenizer_factory(root / "tokenizer.json")
            tokenizer.no_truncation()
            tokenizer.no_padding()
            pad_id = tokenizer.token_to_id("<pad>")
            session = self._session_factory(root / "model.onnx")
        except Exception:
            raise ProviderError(ProviderFailureCode.UNAVAILABLE) from None
        try:
            inputs = session.get_inputs()
            names = {node.name for node in inputs}
            outputs = session.get_outputs()
            output_names = [node.name for node in outputs]
            if (
                session.get_providers() != ["CPUExecutionProvider"]
                or type(pad_id) is not int
                or not 0 <= pad_id <= _MAX_TOKEN_ID
                or len(names) != len(inputs)
                or not {"input_ids", "attention_mask"} <= names
                or not names <= {"input_ids", "attention_mask", "token_type_ids"}
                or any(node.type != "tensor(int64)" or len(node.shape) != 2 for node in inputs)
                or len(set(output_names)) != len(outputs)
            ):
                raise ValueError
            # The official sentence-transformers export already performs CLS
            # pooling. Request only this output to avoid materializing N*L*D.
            if "sentence_embedding" in output_names:
                output_name = "sentence_embedding"
            else:
                token_names = {"token_embeddings", "last_hidden_state"} & set(output_names)
                if len(token_names) != 1:
                    raise ValueError
                output_name = token_names.pop()
            selected = outputs[output_names.index(output_name)]
            rank = 2 if output_name == "sentence_embedding" else 3
            if (
                selected.type != "tensor(float)"
                or len(selected.shape) != rank
                or selected.shape[-1] != self._identity.dimension
            ):
                raise ValueError
        except Exception:
            raise ProviderError(ProviderFailureCode.INVALID_RESPONSE) from None
        self._tokenizer = tokenizer
        self._pad_id = pad_id
        self._session = session
        self._input_names = names
        self._output_name = output_name

    def _embed(self, texts: list[str]) -> NDArray[np.float32]:
        if not isinstance(texts, list) or any(not isinstance(text, str) for text in texts):
            raise ProviderError(ProviderFailureCode.INVALID_RESPONSE)
        result = np.empty((len(texts), self._identity.dimension), dtype=np.float32)
        if not texts:
            return result
        with self._lock:
            self._load()
            batch: list[list[int]] = []
            batch_length = 0
            offset = 0
            for text in texts:
                try:
                    ids = self._tokenizer.encode(text, add_special_tokens=True).ids
                    if (
                        not isinstance(ids, list)
                        or not ids
                        or any(
                            type(token) is not int or not 0 <= token <= _MAX_TOKEN_ID
                            for token in ids
                        )
                    ):
                        raise ValueError
                except Exception:
                    raise ProviderError(ProviderFailureCode.INVALID_RESPONSE) from None
                if len(ids) > self._context_tokens:
                    raise ProviderError(ProviderFailureCode.CONTEXT_OVERFLOW)
                padded_length = max(batch_length, len(ids))
                if batch and (
                    len(batch) >= self._max_batch_size
                    or padded_length * (len(batch) + 1) > self._max_batch_tokens
                ):
                    result[offset : offset + len(batch)] = self._run(batch)
                    offset += len(batch)
                    batch = []
                    batch_length = 0
                batch.append(ids)
                batch_length = max(batch_length, len(ids))
            result[offset:] = self._run(batch)
        return result

    def _run(self, batch: list[list[int]]) -> NDArray[np.float32]:
        length = max(map(len, batch))
        input_ids = np.full((len(batch), length), self._pad_id, dtype=np.int64)
        attention_mask = np.zeros_like(input_ids)
        for row, ids in enumerate(batch):
            input_ids[row, : len(ids)] = ids
            attention_mask[row, : len(ids)] = 1
        feeds = {"input_ids": input_ids, "attention_mask": attention_mask}
        if "token_type_ids" in self._input_names:
            feeds["token_type_ids"] = np.zeros_like(input_ids)
        try:
            outputs = self._session.run([self._output_name], feeds)
        except Exception:
            raise ProviderError(ProviderFailureCode.UNAVAILABLE) from None
        try:
            if not isinstance(outputs, list) or len(outputs) != 1:
                raise ValueError
            tensor = outputs[0]
            expected: tuple[int, ...] = (len(batch), self._identity.dimension)
            if self._output_name != "sentence_embedding":
                expected = (len(batch), length, self._identity.dimension)
            if (
                not isinstance(tensor, np.ndarray)
                or tensor.dtype != np.float32
                or tensor.shape != expected
                or not np.isfinite(tensor).all()
            ):
                raise ValueError
            dense = tensor if tensor.ndim == 2 else tensor[:, 0, :]
            # Float64 accumulation also handles finite extreme fp32 outputs.
            norms = np.linalg.norm(dense.astype(np.float64), axis=1, keepdims=True)
            if not np.isfinite(norms).all() or np.any(norms <= 0):
                raise ValueError
            normalized = np.asarray(dense / norms, dtype=np.float32)
            if not np.isfinite(normalized).all() or not np.allclose(
                np.linalg.norm(normalized, axis=1), 1.0, atol=1e-5, rtol=1e-4
            ):
                raise ValueError
            return normalized
        except Exception:
            raise ProviderError(ProviderFailureCode.INVALID_RESPONSE) from None
