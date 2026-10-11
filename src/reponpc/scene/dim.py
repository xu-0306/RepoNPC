"""Shared bounded opacity ladder for visitor background auto-dimming."""

from __future__ import annotations

from typing import Final

# The visitor stylesheet generator exports these same values as CSS custom properties.
DIM_OPACITY: Final[dict[str, float]] = {
    "none": 0.0,
    "low": 0.16,
    "medium": 0.32,
    "high": 0.48,
}
