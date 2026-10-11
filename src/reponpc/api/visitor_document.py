"""Bind the published mode policy before the external head script runs."""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any

_MODE_MARKER = b'data-owner-mode="system"'
_TOGGLE_MARKER = b'data-visitor-toggle="true"'


def render_published_visitor_document(
    document: bytes, *, bundle_manager: Any, scene_supplier: Callable[[], Any]
) -> bytes:
    """Capture the applied policy; a saved draft is never a public policy source."""

    if b"data-owner-mode" not in document and b"data-visitor-toggle" not in document:
        return document
    mode, toggle = "system", True
    if bundle_manager is not None and bundle_manager.status().active_bundle_id is not None:
        service = scene_supplier()
        if service is None:
            raise ValueError("invalid visitor document")
        with service.published_profile() as snapshot:
            scene = snapshot.document.character.scene
            if scene is None:
                raise ValueError("invalid visitor document")
            mode, toggle = scene.color_mode, scene.visitor_mode_toggle
    return render_visitor_document(document, color_mode=mode, visitor_mode_toggle=toggle)


def render_visitor_document(
    document: bytes, *, color_mode: str, visitor_mode_toggle: bool
) -> bytes:
    """Replace only the two closed build markers; never interpolate owner text."""

    if (
        not isinstance(color_mode, str)
        or color_mode not in {"system", "light", "dark"}
        or type(visitor_mode_toggle) is not bool
        or len(document) > 1024 * 1024
    ):
        raise ValueError("invalid visitor document")
    opening = re.search(rb"<html\s[^>]*>", document)
    if opening is None or any(
        document.count(marker) != 1 or marker not in opening[0]
        for marker in (_MODE_MARKER, _TOGGLE_MARKER)
    ):
        raise ValueError("invalid visitor document")
    policy = opening[0].replace(
        _MODE_MARKER, b'data-owner-mode="' + color_mode.encode("ascii") + b'"'
    )
    policy = policy.replace(
        _TOGGLE_MARKER,
        b'data-visitor-toggle="' + (b"true" if visitor_mode_toggle else b"false") + b'"',
    )
    return document[: opening.start()] + policy + document[opening.end() :]
