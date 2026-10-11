"""Frozen builds locate prebuilt web resources outside the source checkout."""

from pathlib import Path

import pytest

from reponpc import main


def test_frozen_web_resources_use_the_bundle_directory(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(main.sys, "frozen", True, raising=False)
    monkeypatch.setattr(main.sys, "_MEIPASS", str(tmp_path / "_internal"), raising=False)
    assert main._default_web_dist() == tmp_path / "_internal" / "web_dist"


def test_checkout_web_resources_ignore_unrelated_meipass(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(main.sys, "frozen", False, raising=False)
    monkeypatch.setattr(main.sys, "_MEIPASS", str(tmp_path), raising=False)
    assert main._default_web_dist() == Path(main.__file__).resolve().parents[2] / "apps/web/dist"
