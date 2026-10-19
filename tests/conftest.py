from __future__ import annotations

import logging
from collections.abc import Iterator

import pytest


@pytest.fixture
def reponpc_logger() -> Iterator[logging.Logger]:
    """Restore process logging after tests that explicitly prepare a server."""

    logger = logging.getLogger("reponpc")
    handlers = logger.handlers[:]
    level, propagate = logger.level, logger.propagate
    try:
        yield logger
    finally:
        for handler in logger.handlers[:]:
            if handler not in handlers and getattr(handler, "_reponpc_owned", False):
                logger.removeHandler(handler)
                handler.close()
        logger.handlers[:] = handlers
        logger.setLevel(level)
        logger.propagate = propagate
