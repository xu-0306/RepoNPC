"""Bind the published mode policy before the external head script runs."""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any

from reponpc.scene.registry import DEFAULT_SCHEME_ID, default_scene_registry

_MODE_MARKER = b'data-owner-mode="system"'
_TOGGLE_MARKER = b'data-visitor-toggle="true"'


def render_published_visitor_document(
    document: bytes, *, bundle_manager: Any, scene_supplier: Callable[[], Any]
) -> bytes:
    """Capture the applied policy; a saved draft is never a public policy source."""

    if b"data-owner-mode" not in document and b"data-visitor-toggle" not in document:
        return document
    mode, toggle, scheme, scheme_choice = "system", True, DEFAULT_SCHEME_ID, True
    if bundle_manager is not None and bundle_manager.status().active_bundle_id is not None:
        service = scene_supplier()
        if service is None:
            raise ValueError("invalid visitor document")
        with service.published_profile() as snapshot:
            scene = snapshot.document.character.scene
            if scene is None:
                raise ValueError("invalid visitor document")
            mode, toggle = scene.color_mode, scene.visitor_mode_toggle
            scheme, scheme_choice = scene.scheme.id, scene.visitor_scheme_choice
    return render_visitor_document(
        document,
        color_mode=mode,
        visitor_mode_toggle=toggle,
        default_scheme=scheme,
        visitor_scheme_choice=scheme_choice,
    )


def render_visitor_document(
    document: bytes,
    *,
    color_mode: str,
    visitor_mode_toggle: bool,
    default_scheme: str = DEFAULT_SCHEME_ID,
    visitor_scheme_choice: bool = True,
) -> bytes:
    """Bind the closed mode and scheme policy; never interpolate owner text."""

    if (
        not isinstance(color_mode, str)
        or color_mode not in {"system", "light", "dark"}
        or type(visitor_mode_toggle) is not bool
        or type(visitor_scheme_choice) is not bool
        or not isinstance(default_scheme, str)
        or len(document) > 1024 * 1024
        or b"data-default-scheme" in document
        or b"data-visitor-scheme-choice" in document
    ):
        raise ValueError("invalid visitor document")
    try:
        default_scheme = default_scene_registry().canonical_id(default_scheme)
    except KeyError:
        raise ValueError("invalid visitor document") from None
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
    policy = (
        policy[:-1]
        + b' data-default-scheme="'
        + default_scheme.encode("ascii")
        + b'" data-visitor-scheme-choice="'
        + (b"true" if visitor_scheme_choice else b"false")
        + b'">'
    )
    return document[: opening.start()] + policy + document[opening.end() :]
