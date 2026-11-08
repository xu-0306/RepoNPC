"""Child process that proves a staged GPU runtime can run a CUDA session (ADR-084).

    python -I -m reponpc.providers.gpu_runtime_check <runtime folder>

It runs in its own process so the server never imports a half-proven build.
Exit codes: 0 proven; 2 import failed; 3 ONNX Runtime came from elsewhere; 4 the
CUDA session could not be created; 5 CUDA was not the first provider; 6 the run
failed; 7 the answer was wrong. Nothing is printed.
"""

from __future__ import annotations

import struct
import sys
from pathlib import Path

_CUDA = "CUDAExecutionProvider"


def _varint(value: int) -> bytes:
    out = bytearray()
    while value > 0x7F:
        out.append(value & 0x7F | 0x80)
        value >>= 7
    out.append(value)
    return bytes(out)


def _int(number: int, value: int) -> bytes:
    return _varint(number << 3) + _varint(value)


def _msg(number: int, body: bytes) -> bytes:
    return _varint(number << 3 | 2) + _varint(len(body)) + body


def _text(number: int, value: str) -> bytes:
    return _msg(number, value.encode())


def _tensor_info(name: str) -> bytes:
    shape = _msg(1, _int(1, 1)) + _msg(1, _int(1, 1))  # float[1, 1]
    return _text(1, name) + _msg(2, _msg(1, _int(1, 1) + _msg(2, shape)))


def check_model() -> bytes:
    """A hand-encoded ONNX graph `y = x @ [[1.0]]`; it needs no `onnx` package.

    MatMul runs on cuBLAS, so a pass also shows the cuBLAS libraries load.
    """

    weight = _int(1, 1) + _int(1, 1) + _int(2, 1) + _msg(4, struct.pack("<f", 1.0)) + _text(8, "w")
    node = _text(1, "x") + _text(1, "w") + _text(2, "y") + _text(4, "MatMul")
    graph = (
        _msg(1, node)
        + _text(2, "check")
        + _msg(5, weight)
        + _msg(11, _tensor_info("x"))
        + _msg(12, _tensor_info("y"))
    )
    return _int(1, 8) + _msg(8, _text(1, "") + _int(2, 17)) + _msg(7, graph)


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        return 2
    root = Path(argv[1])
    try:
        from reponpc.providers.gpu_runtime import prepare_import_path

        prepare_import_path(root)
        import numpy as np
        import onnxruntime as ort  # type: ignore[import-untyped]
    except Exception:
        return 2
    if Path(ort.__file__).resolve().parent.parent != root.resolve():
        return 3
    try:
        ort.preload_dlls()
        options = ort.SessionOptions()
        options.log_severity_level = 4
        session = ort.InferenceSession(
            check_model(), sess_options=options, providers=[_CUDA, "CPUExecutionProvider"]
        )
        session.disable_fallback()
    except Exception:
        return 4
    if session.get_providers()[0] != _CUDA:
        return 5
    try:
        (answer,) = session.run(None, {"x": np.array([[3.0]], dtype=np.float32)})
    except Exception:
        return 6
    return 0 if float(answer[0][0]) == 3.0 else 7


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
