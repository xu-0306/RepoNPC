"""Validated visitor scene palettes and deterministic resolution."""

from reponpc.scene.registry import SceneRegistryError, default_scene_registry
from reponpc.scene.resolve import (
    PublicScene,
    SceneNotice,
    SceneResolution,
    SceneResolutionError,
    resolve_scene,
)

__all__ = [
    "PublicScene",
    "SceneNotice",
    "SceneRegistryError",
    "SceneResolution",
    "SceneResolutionError",
    "default_scene_registry",
    "resolve_scene",
]
