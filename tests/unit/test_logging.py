from __future__ import annotations

import io
import json
import logging
import subprocess
import sys
from datetime import UTC, datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path

import pytest

import reponpc.observability.logging as safe_logging
from reponpc.observability.logging import configure_logging, get_safe_logger


def test_info_stream_is_exact_json_without_propagation(
    reponpc_logger: logging.Logger, monkeypatch: pytest.MonkeyPatch
) -> None:
    stream = io.StringIO()
    monkeypatch.setattr(sys, "stderr", stream)

    class FixedDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            assert tz is UTC
            return datetime(2026, 10, 19, tzinfo=UTC)

    monkeypatch.setattr(safe_logging, "datetime", FixedDatetime)
    other_loggers = [
        logging.getLogger(n) for n in ("", "uvicorn", "uvicorn.error", "uvicorn.access")
    ]
    before = [(logger.handlers[:], logger.level, logger.propagate) for logger in other_loggers]
    configure_logging("INFO")
    get_safe_logger("reponpc.test.configuration").emit(logging.INFO, "chat.stream.complete")

    assert stream.getvalue() == (
        '{"timestamp":"2026-10-19T00:00:00+00:00","severity":"INFO",'
        '"event":"chat.stream.complete"}\n'
    )
    assert reponpc_logger.level == logging.INFO
    assert reponpc_logger.propagate is False
    assert [
        (logger.handlers[:], logger.level, logger.propagate) for logger in other_loggers
    ] == before


def test_warning_filters_info_but_writes_warning(
    reponpc_logger: logging.Logger, monkeypatch: pytest.MonkeyPatch
) -> None:
    stream = io.StringIO()
    monkeypatch.setattr(sys, "stderr", stream)
    configure_logging("WARNING")
    logger = get_safe_logger("reponpc.test.configuration")
    logger.emit(logging.INFO, "test.hidden")
    logger.emit(logging.WARNING, "test.visible")

    lines = stream.getvalue().splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0])["event"] == "test.visible"
    assert json.loads(lines[0])["severity"] == "WARNING"
    assert reponpc_logger.level == logging.WARNING


def test_reconfiguration_keeps_foreign_handler_and_writes_once_per_sink(
    reponpc_logger: logging.Logger,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    stream = io.StringIO()
    monkeypatch.setattr(sys, "stderr", stream)
    reponpc_logger.addHandler(caplog.handler)
    file_path = tmp_path / "logs" / "reponpc.log"
    try:
        configure_logging("INFO", file_path=file_path)
        configure_logging("INFO", file_path=file_path)
        get_safe_logger("reponpc.test.configuration").emit(logging.INFO, "test.once")

        assert caplog.handler in reponpc_logger.handlers
        assert len(caplog.records) == 1
        assert len(reponpc_logger.handlers) == 3
        assert len(stream.getvalue().splitlines()) == 1
        assert json.loads(stream.getvalue())["event"] == "test.once"
        assert file_path.read_text(encoding="utf-8") == stream.getvalue()
        files = [h for h in reponpc_logger.handlers if isinstance(h, RotatingFileHandler)]
        assert len(files) == 1
        assert files[0].maxBytes == 1_048_576
        assert files[0].backupCount == 3
        assert files[0].encoding == "utf-8"
        stderr_handlers = [h for h in reponpc_logger.handlers if type(h) is logging.StreamHandler]
        assert len(stderr_handlers) == 1
        assert stderr_handlers[0].stream is stream
    finally:
        reponpc_logger.removeHandler(caplog.handler)


def test_reconfiguration_replaces_only_owned_sinks(
    reponpc_logger: logging.Logger, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    first, second = io.StringIO(), io.StringIO()
    monkeypatch.setattr(sys, "stderr", first)
    old_file, new_file = tmp_path / "first.log", tmp_path / "other" / "second.log"
    configure_logging("WARNING", file_path=old_file)
    monkeypatch.setattr(sys, "stderr", second)
    configure_logging("INFO", file_path=new_file)
    get_safe_logger("reponpc.test.configuration").emit(logging.INFO, "test.replaced")

    assert first.getvalue() == ""
    assert old_file.read_text(encoding="utf-8") == ""
    assert new_file.read_text(encoding="utf-8") == second.getvalue()
    assert len(second.getvalue().splitlines()) == 1
    configure_logging("INFO")
    assert not any(isinstance(h, RotatingFileHandler) for h in reponpc_logger.handlers)


def test_importing_main_does_not_configure_logging() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import logging; "
            "names = ('reponpc', '', 'uvicorn', 'uvicorn.error', 'uvicorn.access'); "
            "loggers = [logging.getLogger(n) for n in names]; "
            "before = [(x.handlers[:], x.level, x.propagate) for x in loggers]; "
            "import reponpc.main; "
            "assert [(x.handlers[:], x.level, x.propagate) for x in loggers] == before",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
