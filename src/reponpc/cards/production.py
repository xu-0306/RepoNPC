"""Build every canonical character and README card bundle asset from config."""

from __future__ import annotations

from pathlib import Path

from reponpc.cards.assets import CanonicalSprite, validate_sprite
from reponpc.cards.render import CardCopy, CardPalette, render_card_assets
from reponpc.cards.sprite_composer import compose_builtin
from reponpc.config.models import PublicConfig


def build_public_card_assets(config: PublicConfig, *, config_directory: Path) -> dict[str, bytes]:
    """Return the exact public character/card payload layout consumed by bundles."""

    sprite = _character_sprite(config, config_directory=config_directory)
    assets: dict[str, bytes] = {"public/character.png": sprite.content}
    repository_count = sum(repository.enabled for repository in config.repositories)
    for locale in config.locales.supported:
        copy = CardCopy(
            display_name=config.profile.display_name,
            headline=config.profile.headline[locale],
            call_to_action=config.card.call_to_action[locale],
            repository_count=repository_count if config.card.show_repository_count else None,
        )
        for theme in ("light", "dark"):
            configured_theme = getattr(config.card.themes, theme)
            rendered = render_card_assets(
                copy=copy,
                palette=CardPalette(**configured_theme.model_dump()),
                sprite=sprite,
                animation_enabled=config.card.animation.enabled,
                frame_duration_ms=config.card.animation.frame_duration_ms,
            )
            assets[f"public/card-{theme}-{locale}.svg"] = rendered.svg
            assets[f"public/card-{theme}-{locale}.gif"] = rendered.gif
            assets[f"public/card-{theme}-{locale}.png"] = rendered.png
    return assets


def _character_sprite(config: PublicConfig, *, config_directory: Path) -> CanonicalSprite:
    if config.character.builtin is not None:
        return validate_sprite(compose_builtin(config.character.builtin))
    custom = config.character.custom
    if custom is None:
        raise ValueError("character configuration is incomplete")
    return validate_sprite((config_directory / custom.sprite_path).read_bytes())
