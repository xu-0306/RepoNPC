"""Closed, packaged source of visitor color schemes."""

from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from types import MappingProxyType
from typing import Final

import yaml

from reponpc.scene.dim import DIM_OPACITY

SCENE_ROLES: Final[tuple[str, ...]] = (
    "background",
    "surface",
    "surface_alt",
    "ink",
    "muted_ink",
    "accent",
    "accent_ink",
    "border",
    "stage",
    "focus",
)
VARIANTS: Final[tuple[str, str]] = ("light", "dark")
LOCALES: Final[tuple[str, str]] = ("zh-TW", "en")
SCHEME_ID_RE: Final[re.Pattern[str]] = re.compile(r"^[a-z0-9_]+$")
HEX_COLOR_RE: Final[re.Pattern[str]] = re.compile(r"^#[0-9a-fA-F]{6}$")
TEXT_CONTRAST: Final[float] = 4.5
NON_TEXT_CONTRAST: Final[float] = 3.0


class SceneRegistryError(ValueError):
    """Packaged scheme registry failure with safe scheme/role context."""


class _UniqueKeyLoader(yaml.SafeLoader):
    """Safe YAML loader that rejects duplicate mapping keys at every depth."""


def _construct_unique_mapping(
    loader: _UniqueKeyLoader, node: yaml.MappingNode, deep: bool = False
) -> dict[object, object]:
    loader.flatten_mapping(node)
    result: dict[object, object] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        try:
            duplicate = key in result
        except TypeError:
            raise SceneRegistryError("registry contains a non-scalar mapping key") from None
        if duplicate:
            label = key if isinstance(key, str) else "<non-string>"
            raise SceneRegistryError(f"registry contains duplicate key {label!r}")
        result[key] = loader.construct_object(value_node, deep=deep)
    return result


_UniqueKeyLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _construct_unique_mapping
)


@dataclass(frozen=True, slots=True)
class Scheme:
    id: str
    version: int
    label: Mapping[str, str]
    light: Mapping[str, str]
    dark: Mapping[str, str]

    def variant(self, name: str) -> Mapping[str, str]:
        if name == "light":
            return self.light
        if name == "dark":
            return self.dark
        raise KeyError(name)


@dataclass(frozen=True, slots=True)
class SceneRegistry:
    schemes: Mapping[str, Scheme]
    aliases: Mapping[str, str]
    source_sha256: str

    def canonical_id(self, scheme_id: str) -> str:
        current = scheme_id
        seen: set[str] = set()
        while current in self.aliases:
            if current in seen:
                raise KeyError(scheme_id)
            seen.add(current)
            current = self.aliases[current]
        if current not in self.schemes:
            raise KeyError(scheme_id)
        return current

    def scheme(self, scheme_id: str) -> Scheme:
        return self.schemes[self.canonical_id(scheme_id)]


def contrast_ratio(first: str, second: str) -> float:
    """Return WCAG relative-luminance contrast for two opaque sRGB colors."""

    luminances = sorted((_luminance(first), _luminance(second)))
    return (luminances[1] + 0.05) / (luminances[0] + 0.05)


def contrast_pairs() -> tuple[tuple[str, str, float], ...]:
    pairs = [
        (text, surface, TEXT_CONTRAST)
        for text in ("ink", "muted_ink")
        for surface in ("background", "surface", "surface_alt")
    ]
    pairs.append(("accent_ink", "accent", TEXT_CONTRAST))
    pairs.extend(
        (foreground, surface, NON_TEXT_CONTRAST)
        for foreground in ("accent", "border", "focus")
        for surface in ("background", "surface", "surface_alt")
    )
    return tuple(pairs)


def parse_scene_registry(text: str) -> SceneRegistry:
    """Parse and validate registry YAML, including duplicate keys and contrast."""

    try:
        raw = yaml.load(text, Loader=_UniqueKeyLoader)
    except SceneRegistryError:
        raise
    except yaml.YAMLError:
        raise SceneRegistryError("registry YAML is malformed") from None
    return _validate_registry(raw, text.encode("utf-8"))


def load_scene_registry(path: str | Path) -> SceneRegistry:
    try:
        text = Path(path).read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        raise SceneRegistryError("registry file cannot be read as UTF-8") from None
    return parse_scene_registry(text)


@lru_cache(maxsize=1)
def default_scene_registry() -> SceneRegistry:
    registry = load_scene_registry(Path(__file__).with_name("color_schemes.yml"))
    if "neutral" not in registry.schemes:
        raise SceneRegistryError("packaged registry is missing default scheme neutral")
    return registry


def fallback_stylesheet(registry: SceneRegistry | None = None) -> bytes:
    """Generate neutral fallback tokens for system and explicit visitor modes."""

    selected = registry or default_scene_registry()
    scheme = selected.schemes[selected.canonical_id("neutral")]
    lines = [
        "/* Generated by scripts/build_scene_assets.py; do not edit. */",
        f"/* Registry SHA-256: {selected.source_sha256} */",
        ":root,",
        ':root[data-visitor-mode="light"] {',
        *[f"  --scene-dim-opacity-{level}: {opacity:g};" for level, opacity in DIM_OPACITY.items()],
        *_role_lines(scheme.light),
        "}",
        ':root[data-visitor-mode="dark"] {',
        *[f"  --scene-dim-opacity-{level}: {opacity:g};" for level, opacity in DIM_OPACITY.items()],
        *_role_lines(scheme.dark),
        "}",
        "@media (prefers-color-scheme: dark) {",
        '  :root:not([data-visitor-mode="light"]):not([data-visitor-mode="dark"]) {',
        *(
            f"    --scene-dim-opacity-{level}: {opacity:g};"
            for level, opacity in DIM_OPACITY.items()
        ),
        *(f"  {line}" for line in _role_lines(scheme.dark)),
        "  }",
        "}",
        "",
    ]
    return "\n".join(lines).encode("utf-8")


def contrast_report(registry: SceneRegistry | None = None) -> dict[str, object]:
    selected = registry or default_scene_registry()
    schemes = []
    for scheme_id in sorted(selected.schemes):
        scheme = selected.schemes[scheme_id]
        variants = {}
        for variant in VARIANTS:
            roles = scheme.variant(variant)
            variants[variant] = {
                f"{foreground}/{background}": round(
                    contrast_ratio(roles[foreground], roles[background]), 3
                )
                for foreground, background, _minimum in contrast_pairs()
            }
        schemes.append({"id": scheme_id, "version": scheme.version, "variants": variants})
    return {"registry_sha256": selected.source_sha256, "schemes": schemes}


def _role_lines(roles: Mapping[str, str]) -> list[str]:
    return [f"  --scene-{role}: {roles[role]};" for role in SCENE_ROLES]


def _validate_registry(raw: object, source: bytes) -> SceneRegistry:
    if not isinstance(raw, dict) or set(raw) != {"schemes", "aliases"}:
        raise SceneRegistryError("registry must contain exactly schemes and aliases")
    raw_schemes = raw["schemes"]
    raw_aliases = raw["aliases"]
    if not isinstance(raw_schemes, list) or not raw_schemes:
        raise SceneRegistryError("registry schemes must be a non-empty list")
    if not isinstance(raw_aliases, dict):
        raise SceneRegistryError("registry aliases must be a mapping")

    schemes: dict[str, Scheme] = {}
    for entry in raw_schemes:
        if not isinstance(entry, dict) or set(entry) != {"id", "version", "label", "light", "dark"}:
            raise SceneRegistryError(
                "scheme entry must contain exactly id, version, label, light and dark"
            )
        scheme_id = entry["id"]
        version = entry["version"]
        if not isinstance(scheme_id, str) or not SCHEME_ID_RE.fullmatch(scheme_id):
            raise SceneRegistryError("scheme id is malformed")
        if scheme_id in schemes:
            raise SceneRegistryError(f"scheme {scheme_id}: duplicate id")
        if not isinstance(version, int) or isinstance(version, bool) or version < 1:
            raise SceneRegistryError(f"scheme {scheme_id}: version must be a positive integer")
        label = entry["label"]
        if not isinstance(label, dict) or set(label) != set(LOCALES):
            raise SceneRegistryError(f"scheme {scheme_id}: label must include exactly zh-TW and en")
        if any(
            not isinstance(label[locale], str) or not label[locale].strip() for locale in LOCALES
        ):
            raise SceneRegistryError(f"scheme {scheme_id}: label values must be non-empty strings")

        variants: dict[str, Mapping[str, str]] = {}
        for variant in VARIANTS:
            raw_roles = entry[variant]
            if not isinstance(raw_roles, dict):
                raise SceneRegistryError(f"scheme {scheme_id} {variant}: roles must be a mapping")
            actual = set(raw_roles)
            if actual != set(SCENE_ROLES):
                missing = sorted(set(SCENE_ROLES) - actual)
                unknown = sorted(str(role) for role in actual - set(SCENE_ROLES))
                detail = (
                    f"missing {', '.join(missing)}" if missing else f"unknown {', '.join(unknown)}"
                )
                raise SceneRegistryError(f"scheme {scheme_id} {variant}: {detail} role")
            roles: dict[str, str] = {}
            for role in SCENE_ROLES:
                value = raw_roles[role]
                if not isinstance(value, str) or not HEX_COLOR_RE.fullmatch(value):
                    raise SceneRegistryError(
                        f"scheme {scheme_id} {variant}: role {role} must be #rrggbb"
                    )
                roles[role] = value.lower()
            for foreground, background, minimum in contrast_pairs():
                ratio = contrast_ratio(roles[foreground], roles[background])
                if ratio + 1e-9 < minimum:
                    raise SceneRegistryError(
                        f"scheme {scheme_id} {variant}: contrast {foreground}/{background} "
                        f"is {ratio:.3f}:1; requires {minimum:.1f}:1"
                    )
            variants[variant] = MappingProxyType(roles)

        schemes[scheme_id] = Scheme(
            id=scheme_id,
            version=version,
            label=MappingProxyType({locale: label[locale] for locale in LOCALES}),
            light=variants["light"],
            dark=variants["dark"],
        )

    aliases: dict[str, str] = {}
    for alias, target in raw_aliases.items():
        if (
            not isinstance(alias, str)
            or not SCHEME_ID_RE.fullmatch(alias)
            or not isinstance(target, str)
            or not SCHEME_ID_RE.fullmatch(target)
        ):
            raise SceneRegistryError("registry alias IDs must match [a-z0-9_]+")
        if alias in schemes:
            raise SceneRegistryError(f"alias {alias}: conflicts with a live scheme id")
        aliases[alias] = target
    for alias in aliases:
        current = alias
        visited: set[str] = set()
        while current in aliases:
            if current in visited:
                raise SceneRegistryError(f"alias {alias}: alias cycle")
            visited.add(current)
            current = aliases[current]
        if current not in schemes:
            raise SceneRegistryError(f"alias {alias}: dangling target")

    normalized_source = source.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    return SceneRegistry(
        schemes=MappingProxyType(schemes),
        aliases=MappingProxyType(aliases),
        source_sha256=hashlib.sha256(normalized_source).hexdigest(),
    )


def _luminance(color: str) -> float:
    channels = tuple(int(color[index : index + 2], 16) / 255 for index in (1, 3, 5))
    linear = tuple(
        channel / 12.92 if channel <= 0.04045 else ((channel + 0.055) / 1.055) ** 2.4
        for channel in channels
    )
    return sum(
        weight * channel for weight, channel in zip((0.2126, 0.7152, 0.0722), linear, strict=True)
    )
