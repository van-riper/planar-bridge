"""Load and resolve Planar Bridge configuration."""

from dataclasses import dataclass
from pathlib import Path
from tomllib import loads
from typing import Any

from .defaults import (
    DEFAULT_FILTER_LISTS,
    DEFAULT_LANGUAGE_CODE,
    DEFAULT_PULL_REPRINTS,
    LANGUAGE_MAP,
)


@dataclass(frozen=True, kw_only=True)
class AppConfig:
    """Resolved, immutable application configuration.

    Attributes:
        pull_reprints (bool): Whether to download cards flagged as reprints.
        card_language (str): MTGJSON full language name to keep
            (e.g. "English").
        pardoned_sets (frozenset[str]): Set codes kept even when
            an exempt rule matches.
        exempt_sets (frozenset[str]): Set codes to skip entirely.
        exempt_promos (frozenset[str]): Promo types that disqualify a card.
        exempt_types (frozenset[str]): Set types to skip entirely.
    """

    pull_reprints: bool
    card_language: str
    pardoned_sets: frozenset[str]
    exempt_sets: frozenset[str]
    exempt_promos: frozenset[str]
    exempt_types: frozenset[str]


def load_config(
    config_path: Path | None,
    language_override: str | None = None,
) -> AppConfig:
    """Build an AppConfig by layering config.toml over the defaults.

    Reads config_path when provided and present, overlays it on the
    built-in defaults, maps the card_language code to MTGJSON's full
    language name, and freezes the exempt/pardon collections.

    Args:
        config_path: Path to a user config.toml, or None. A missing or None
            path falls back to the defaults alone.
        language_override: A language code that, when given, takes
            precedence over the file value and the default (the CLI's
            --language).

    Returns:
        The resolved, immutable configuration.

    Raises:
        ValueError: If the resolved card_language is not a recognized code.
    """
    file_data: dict[str, Any] = {}

    if config_path and config_path.exists():
        file_data = loads(config_path.read_text(encoding="UTF-8"))

    pull_reprints = bool(file_data.get("pull_reprints", DEFAULT_PULL_REPRINTS))

    language_code = language_override or str(
        file_data.get("card_language", DEFAULT_LANGUAGE_CODE)
    )
    language_name = LANGUAGE_MAP.get(language_code)

    if language_name is None:
        raise ValueError(f"language code '{language_code}' not supported")

    filter_lists = DEFAULT_FILTER_LISTS | file_data

    return AppConfig(
        pull_reprints=pull_reprints,
        card_language=language_name,
        pardoned_sets=frozenset(filter_lists["pardoned_sets"]),
        exempt_sets=frozenset(filter_lists["exempt_sets"]),
        exempt_promos=frozenset(filter_lists["exempt_promos"]),
        exempt_types=frozenset(filter_lists["exempt_types"]),
    )
