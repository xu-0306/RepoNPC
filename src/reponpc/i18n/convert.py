"""Registry-selected deterministic Chinese conversion for authoring (ADR-079)."""

from functools import lru_cache

from opencc import OpenCC  # type: ignore[import-untyped]

from reponpc.i18n.languages import converter_for, is_language_tag


@lru_cache
def _converter(name: str) -> OpenCC:
    return OpenCC(name)


def can_convert(source: str, target: str) -> bool:
    return is_language_tag(target) and converter_for(source, target) is not None


def convert(text: str, source: str, target: str) -> str:
    name = converter_for(source, target) if is_language_tag(target) else None
    if name is None:
        raise ValueError(f"no converter from {source} to {target}")
    return _converter(name).convert(text)
