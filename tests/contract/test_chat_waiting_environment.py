"""Longer default does not silently replace explicit deployment choices."""

from pathlib import Path

import pytest

from reponpc.config.environment import EnvironmentValidationError, load_environment
from tests.contract.test_environment import deployment_environment


@pytest.mark.parametrize("setting,expected", [(None, 180), ("45", 45), ("300", 300)])
def test_chat_deadline_default_and_existing_explicit_values(
    setting: str | None, expected: int, tmp_path: Path
) -> None:
    values = deployment_environment()
    if setting is not None:
        values["REPONPC_CHAT_TIMEOUT_SECONDS"] = setting
    assert load_environment(values, secret_roots=(tmp_path,)).chat_timeout_seconds == expected


@pytest.mark.parametrize("setting", ["0", "301"])
def test_chat_deadline_bounds_remain_closed(setting: str, tmp_path: Path) -> None:
    with pytest.raises(EnvironmentValidationError):
        load_environment(
            deployment_environment(REPONPC_CHAT_TIMEOUT_SECONDS=setting), secret_roots=(tmp_path,)
        )
