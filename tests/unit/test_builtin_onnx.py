"""Inference contract tests with real local tokenization and no model weights."""

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Lock
from time import sleep
from types import SimpleNamespace
from typing import Any

import numpy as np
import pytest
from tokenizers import Tokenizer
from tokenizers.models import WordLevel
from tokenizers.pre_tokenizers import Whitespace
from tokenizers.processors import TemplateProcessing

from reponpc.providers.builtin_artifacts import builtin_embedding_identity
from reponpc.providers.builtin_onnx import BuiltinOnnxEmbeddingProvider
from reponpc.providers.contracts import ProviderError, ProviderFailureCode, RuntimeEmbeddingProvider


def tokenizer() -> Tokenizer:
    result = Tokenizer(
        WordLevel(
            {"<s>": 0, "<pad>": 1, "</s>": 2, "<unk>": 3, "hello": 4, "世界": 5}, unk_token="<unk>"
        )
    )
    result.pre_tokenizer = Whitespace()
    result.post_processor = TemplateProcessing(
        single="<s> $A </s>", special_tokens=[("<s>", 0), ("</s>", 2)]
    )
    # Saved upstream tokenizer settings must not silently truncate or pad.
    result.enable_truncation(4)
    result.enable_padding(length=20, pad_id=1, pad_token="<pad>")
    return result


class Session:
    def __init__(self, output_name: str = "sentence_embedding") -> None:
        self.output_name = output_name
        self.inputs = [
            SimpleNamespace(name=name, type="tensor(int64)", shape=["batch", "length"])
            for name in ("input_ids", "attention_mask")
        ]
        shape = (
            ["batch", 1024] if output_name == "sentence_embedding" else ["batch", "length", 1024]
        )
        self.outputs = [SimpleNamespace(name=output_name, type="tensor(float)", shape=shape)]
        self.providers = ["CPUExecutionProvider"]
        self.calls: list[dict[str, Any]] = []
        self.failure: Exception | None = None
        self.replacement: Any = None

    def get_inputs(self) -> list[Any]:
        return self.inputs

    def get_outputs(self) -> list[Any]:
        return self.outputs

    def get_providers(self) -> list[str]:
        return self.providers

    def run(self, names: list[str], feeds: dict[str, Any]) -> list[Any]:
        assert names == [self.output_name]
        self.calls.append(feeds)
        if self.failure:
            raise self.failure
        if self.replacement is not None:
            return self.replacement
        ids = feeds["input_ids"]
        vectors = np.zeros((len(ids), 1024), dtype=np.float32)
        vectors[:, 0] = 3
        vectors[:, 1] = ids[:, 1]
        if self.output_name != "sentence_embedding":
            tokens = np.full((*ids.shape, 1024), 99, dtype=np.float32)
            tokens[:, 0, :] = vectors
            return [tokens]
        return [vectors]


def provider(tmp_path: Path, session: Session, **kwargs: Any) -> BuiltinOnnxEmbeddingProvider:
    return BuiltinOnnxEmbeddingProvider(
        tmp_path,
        verify_artifacts=lambda root: root,
        tokenizer_factory=lambda _: tokenizer(),
        session_factory=lambda _: session,
        **kwargs,
    )


def assert_safe_failure(error: ProviderError, code: ProviderFailureCode) -> None:
    assert error.code is code
    assert str(error) == "model provider failed"
    assert error.upstream_message is None
    assert error.upstream_status is None
    assert error.__cause__ is None


def test_identity_empty_batches_are_lazy_and_repr_hides_path(tmp_path: Path) -> None:
    def forbidden(_: Path) -> Any:
        pytest.fail("empty batch attempted to load artifacts")

    instance = BuiltinOnnxEmbeddingProvider(tmp_path / "private-secret", verify_artifacts=forbidden)
    assert isinstance(instance, RuntimeEmbeddingProvider)
    assert instance.identity() == builtin_embedding_identity()
    assert "private-secret" not in repr(instance)
    for method in (instance.embed_query, instance.embed_passages):
        output = method([])
        assert output.shape == (0, 1024)
        assert output.dtype == np.float32


@pytest.mark.parametrize(
    "output_name", ["sentence_embedding", "token_embeddings", "last_hidden_state"]
)
def test_zh_en_order_no_prefix_cls_and_normalization(tmp_path: Path, output_name: str) -> None:
    session = Session(output_name)
    instance = provider(tmp_path, session)
    query = instance.embed_query(["世界", "hello hello"])
    passages = instance.embed_passages(["世界", "hello hello"])
    np.testing.assert_array_equal(query, passages)
    assert query.dtype == np.float32
    np.testing.assert_allclose(np.linalg.norm(query, axis=1), 1, rtol=1e-6)
    np.testing.assert_allclose(query[0, :2], [3 / np.sqrt(34), 5 / np.sqrt(34)])
    np.testing.assert_allclose(query[1, :2], [0.6, 0.8])
    np.testing.assert_array_equal(session.calls[0]["input_ids"], [[0, 5, 2, 1], [0, 4, 4, 2]])
    np.testing.assert_array_equal(session.calls[0]["attention_mask"], [[1, 1, 1, 0], [1, 1, 1, 1]])
    assert set(session.calls[0]) == {"input_ids", "attention_mask"}
    assert session.calls[0]["input_ids"].dtype == np.int64


def test_default_real_tokenizer_factory_verified_before_load(tmp_path: Path) -> None:
    tokenizer().save(str(tmp_path / "tokenizer.json"))
    calls = []
    session = Session()

    def verify(root: Path) -> Path:
        calls.append("verify")
        return root

    def load(path: Path) -> Session:
        assert path == tmp_path / "model.onnx"
        assert calls == ["verify"]
        calls.append("session")
        return session

    instance = BuiltinOnnxEmbeddingProvider(tmp_path, verify_artifacts=verify, session_factory=load)
    instance.embed_query(["hello"])
    instance.embed_passages(["世界"])
    assert calls == ["verify", "session"]


def test_real_token_boundary_includes_special_tokens_and_rejects_overflow(tmp_path: Path) -> None:
    session = Session()
    instance = provider(tmp_path, session)
    instance.embed_query([" ".join(["hello"] * 8190)])
    assert session.calls[0]["input_ids"].shape == (1, 8192)
    with pytest.raises(ProviderError) as caught:
        instance.embed_passages([" ".join(["hello"] * 8191)])
    assert_safe_failure(caught.value, ProviderFailureCode.CONTEXT_OVERFLOW)
    assert len(session.calls) == 1


def test_batch_rows_and_padded_tokens_are_bounded(tmp_path: Path) -> None:
    session = Session()
    instance = provider(tmp_path, session, max_batch_size=2)
    texts = ["hello", "世界", " ".join(["hello"] * 4998), "hello", "世界"]
    result = instance.embed_passages(texts)
    assert [call["input_ids"].shape for call in session.calls] == [(2, 3), (1, 5000), (2, 3)]
    assert all(call["input_ids"].size <= 8192 for call in session.calls)
    np.testing.assert_array_equal(result[0], result[3])
    np.testing.assert_array_equal(result[1], result[4])


@pytest.mark.parametrize("texts", [None, "hello", ("hello",), [1], [None]])
def test_bad_inputs_fail_before_loading(tmp_path: Path, texts: Any) -> None:
    instance = BuiltinOnnxEmbeddingProvider(tmp_path)
    with pytest.raises(ProviderError) as caught:
        instance.embed_query(texts)
    assert_safe_failure(caught.value, ProviderFailureCode.INVALID_RESPONSE)


@pytest.mark.parametrize(
    "output",
    [
        [],
        ["private prompt"],
        [np.ones((1, 1023), dtype=np.float32)],
        [np.ones((2, 1024), dtype=np.float32)],
        [np.ones((1, 1024), dtype=np.float64)],
        [np.zeros((1, 1024), dtype=np.float32)],
        [np.full((1, 1024), np.nan, dtype=np.float32)],
        [np.full((1, 1024), np.inf, dtype=np.float32)],
        [np.ones((1, 3, 1024), dtype=np.float32)],
    ],
)
def test_wrong_dense_tensors_fail_closed(tmp_path: Path, output: Any) -> None:
    session = Session()
    session.replacement = output
    with pytest.raises(ProviderError) as caught:
        provider(tmp_path, session).embed_query(["hello"])
    assert_safe_failure(caught.value, ProviderFailureCode.INVALID_RESPONSE)


def test_wrong_token_shape_and_non_cls_nonfinite_fail_closed(tmp_path: Path) -> None:
    session = Session("token_embeddings")
    for output in (
        np.ones((1, 2, 1024), dtype=np.float32),
        np.ones((1, 3, 1024), dtype=np.float32),
    ):
        if output.shape[1] == 3:
            output[0, 1, 0] = np.nan
        session.replacement = [output]
        with pytest.raises(ProviderError) as caught:
            provider(tmp_path, session).embed_query(["hello"])
        assert_safe_failure(caught.value, ProviderFailureCode.INVALID_RESPONSE)


@pytest.mark.parametrize(
    "problem",
    [
        "gpu",
        "input_name",
        "input_type",
        "output_name",
        "output_type",
        "output_rank",
        "dimension",
        "duplicate",
    ],
)
def test_graph_metadata_fails_closed(tmp_path: Path, problem: str) -> None:
    session = Session()
    if problem == "gpu":
        session.providers = ["CUDAExecutionProvider", "CPUExecutionProvider"]
    elif problem == "input_name":
        session.inputs[0].name = "arbitrary"
    elif problem == "input_type":
        session.inputs[0].type = "tensor(int32)"
    elif problem == "output_name":
        session.outputs[0].name = "unnamed_pooler"
    elif problem == "output_type":
        session.outputs[0].type = "tensor(float16)"
    elif problem == "output_rank":
        session.outputs[0].shape = ["batch", "length", 1024]
    elif problem == "dimension":
        session.outputs[0].shape[-1] = 384
    else:
        session.outputs.append(session.outputs[0])
    with pytest.raises(ProviderError) as caught:
        provider(tmp_path, session).embed_query(["hello"])
    assert_safe_failure(caught.value, ProviderFailureCode.INVALID_RESPONSE)
    assert not session.calls


def test_optional_token_types_and_auxiliary_output(tmp_path: Path) -> None:
    session = Session()
    session.inputs.append(
        SimpleNamespace(name="token_type_ids", type="tensor(int64)", shape=["b", "l"])
    )
    session.outputs.insert(
        0, SimpleNamespace(name="token_embeddings", type="tensor(float)", shape=["b", "l", 1024])
    )
    provider(tmp_path, session).embed_query(["hello"])
    np.testing.assert_array_equal(session.calls[0]["token_type_ids"], [[0, 0, 0]])


def test_loading_and_runtime_failures_health_are_safe(tmp_path: Path) -> None:
    def fail(_: Path) -> Any:
        raise OSError("private/path key=secret user prompt")

    instance = BuiltinOnnxEmbeddingProvider(tmp_path, verify_artifacts=fail)
    health = instance.health()
    assert not health.ready and health.failure_code is ProviderFailureCode.UNAVAILABLE
    with pytest.raises(ProviderError) as caught:
        instance.embed_query(["private user prompt"])
    assert_safe_failure(caught.value, ProviderFailureCode.UNAVAILABLE)
    session = Session()
    session.failure = RuntimeError("private/path key=secret user prompt")
    assert provider(tmp_path, session).health().failure_code is ProviderFailureCode.UNAVAILABLE
    session.failure = None
    session.replacement = [np.zeros((1, 1024), dtype=np.float32)]
    assert provider(tmp_path, session).health().failure_code is ProviderFailureCode.INVALID_RESPONSE
    assert provider(tmp_path, Session()).health().ready


def test_concurrent_calls_load_once_and_preserve_results(tmp_path: Path) -> None:
    calls = []
    session = Session()
    run = session.run
    guard = Lock()
    active = 0
    peak_active = 0

    def serialized_run(names: list[str], feeds: dict[str, Any]) -> list[Any]:
        nonlocal active, peak_active
        with guard:
            active += 1
            peak_active = max(peak_active, active)
        sleep(0.002)
        try:
            return run(names, feeds)
        finally:
            with guard:
                active -= 1

    session.run = serialized_run  # type: ignore[method-assign]

    def verify(root: Path) -> Path:
        calls.append(root)
        return root

    instance = BuiltinOnnxEmbeddingProvider(
        tmp_path,
        verify_artifacts=verify,
        tokenizer_factory=lambda _: tokenizer(),
        session_factory=lambda _: session,
    )
    with ThreadPoolExecutor(max_workers=4) as executor:
        outputs = list(executor.map(instance.embed_query, [["hello"]] * 16))
    assert len(calls) == 1
    assert len(session.calls) == 16
    assert peak_active == 1
    for output in outputs:
        np.testing.assert_array_equal(output, outputs[0])


def test_default_session_is_cpu_only_and_disables_fallback(
    tmp_path: Path, monkeypatch: Any
) -> None:
    import onnxruntime as ort  # type: ignore[import-untyped]

    options = SimpleNamespace()
    session = Session()
    calls = []
    monkeypatch.setattr(ort, "SessionOptions", lambda: options)

    def load(path: str, *, sess_options: Any, providers: list[str]) -> Session:
        assert path == str(tmp_path / "model.onnx")
        assert sess_options is options
        assert providers == ["CPUExecutionProvider"]
        return session

    monkeypatch.setattr(ort, "InferenceSession", load)
    monkeypatch.setattr(session, "disable_fallback", lambda: calls.append("disable"), raising=False)
    instance = BuiltinOnnxEmbeddingProvider(
        tmp_path, verify_artifacts=lambda root: root, tokenizer_factory=lambda _: tokenizer()
    )
    instance.embed_query(["hello"])
    assert calls == ["disable"]
    assert options.intra_op_num_threads == 4
    assert options.inter_op_num_threads == 1
    assert options.log_severity_level == 4


@pytest.mark.parametrize("seam", ["tokenizer", "session"])
def test_factory_failures_are_safe_and_do_not_activate(tmp_path: Path, seam: str) -> None:
    def fail(_: Path) -> Any:
        raise RuntimeError("private/path key=secret prompt")

    instance = BuiltinOnnxEmbeddingProvider(
        tmp_path,
        verify_artifacts=lambda root: root,
        tokenizer_factory=fail if seam == "tokenizer" else lambda _: tokenizer(),
        session_factory=fail,
    )
    with pytest.raises(ProviderError) as caught:
        instance.embed_passages(["hello"])
    assert_safe_failure(caught.value, ProviderFailureCode.UNAVAILABLE)
    assert instance._session is None


@pytest.mark.parametrize("ids", [None, [], [True], [-1], [1 << 64], ["private prompt"]])
def test_malformed_token_ids_fail_closed(tmp_path: Path, ids: Any) -> None:
    class BrokenTokenizer:
        def no_truncation(self) -> None:
            pass

        def no_padding(self) -> None:
            pass

        def token_to_id(self, _: str) -> int:
            return 1

        def encode(self, _: str, *, add_special_tokens: bool) -> Any:
            return SimpleNamespace(ids=ids)

    session = Session()
    instance = BuiltinOnnxEmbeddingProvider(
        tmp_path,
        verify_artifacts=lambda root: root,
        tokenizer_factory=lambda _: BrokenTokenizer(),
        session_factory=lambda _: session,
    )
    with pytest.raises(ProviderError) as caught:
        instance.embed_query(["hello"])
    assert_safe_failure(caught.value, ProviderFailureCode.INVALID_RESPONSE)
    assert not session.calls


def test_extreme_finite_fp32_outputs_normalize_without_overflow(tmp_path: Path) -> None:
    session = Session()
    session.replacement = [np.full((1, 1024), np.finfo(np.float32).max, dtype=np.float32)]
    output = provider(tmp_path, session).embed_query(["hello"])
    np.testing.assert_allclose(output, np.full((1, 1024), 1 / 32, dtype=np.float32))


def test_local_tokenizer_and_inference_never_connect_network(
    tmp_path: Path, monkeypatch: Any
) -> None:
    import socket

    def forbidden(*args: Any, **kwargs: Any) -> Any:
        pytest.fail("built-in local inference attempted a network connection")

    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    tokenizer().save(str(tmp_path / "tokenizer.json"))
    session = Session()
    instance = BuiltinOnnxEmbeddingProvider(
        tmp_path, verify_artifacts=lambda root: root, session_factory=lambda _: session
    )
    instance.embed_passages(["世界", "hello"])
    assert len(session.calls) == 1


@pytest.mark.parametrize("max_batch_size", [0, 9, True, 1.5])
def test_invalid_batch_bounds_are_rejected(tmp_path: Path, max_batch_size: Any) -> None:
    with pytest.raises(ValueError, match="invalid built-in inference batch bounds"):
        BuiltinOnnxEmbeddingProvider(tmp_path, max_batch_size=max_batch_size)


def test_close_before_loading_is_idempotent_and_never_reloads(tmp_path: Path) -> None:
    def forbidden(_: Path) -> Any:
        pytest.fail("closed provider attempted to load artifacts")

    instance = BuiltinOnnxEmbeddingProvider(tmp_path, verify_artifacts=forbidden)
    identity = instance.identity()
    instance.close()
    instance.close()
    assert instance.identity() == identity
    for method in (instance.embed_query, instance.embed_passages):
        empty = method([])
        assert empty.dtype == np.float32 and empty.shape == (0, 1024)
        with pytest.raises(ProviderError) as error:
            method(["hello"])
        assert_safe_failure(error.value, ProviderFailureCode.UNAVAILABLE)
    assert instance.health().failure_code is ProviderFailureCode.UNAVAILABLE


def test_close_releases_loaded_session_and_tokenizer_and_blocks_reload(tmp_path: Path) -> None:
    import gc
    import weakref

    sessions: list[weakref.ReferenceType[Session]] = []

    def load(_: Path) -> Session:
        session = Session()
        sessions.append(weakref.ref(session))
        return session

    instance = BuiltinOnnxEmbeddingProvider(
        tmp_path,
        verify_artifacts=lambda root: root,
        tokenizer_factory=lambda _: tokenizer(),
        session_factory=load,
    )
    instance.embed_query(["hello"])
    assert sessions[0]() is not None
    instance.close()
    instance.close()
    gc.collect()
    assert sessions[0]() is None
    assert instance._session is None and instance._tokenizer is None
    with pytest.raises(ProviderError) as error:
        instance.embed_passages(["世界"])
    assert_safe_failure(error.value, ProviderFailureCode.UNAVAILABLE)
    assert len(sessions) == 1


def test_default_session_disables_telemetry_before_session_creation(
    tmp_path: Path, monkeypatch: Any
) -> None:
    import onnxruntime as ort  # type: ignore[import-untyped]

    calls: list[str] = []
    session = Session()
    monkeypatch.setattr(ort, "disable_telemetry_events", lambda: calls.append("telemetry"))

    def options() -> Any:
        calls.append("options")
        return SimpleNamespace()

    def load(*args: Any, **kwargs: Any) -> Session:
        assert calls == ["telemetry", "options"]
        calls.append("session")
        return session

    monkeypatch.setattr(ort, "SessionOptions", options)
    monkeypatch.setattr(ort, "InferenceSession", load)
    monkeypatch.setattr(
        session, "disable_fallback", lambda: calls.append("fallback"), raising=False
    )
    instance = BuiltinOnnxEmbeddingProvider(
        tmp_path, verify_artifacts=lambda root: root, tokenizer_factory=lambda _: tokenizer()
    )
    instance.embed_query(["hello"])
    assert calls == ["telemetry", "options", "session", "fallback"]
