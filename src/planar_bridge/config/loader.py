"""Load and resolve Planar Bridge configuration."""

from dataclasses import dataclass
from pathlib import Path
from tomllib import loads
from typing import Any

from planar_bridge.config.defaults import (
    DEFAULT_FILTER_LISTS,
    DEFAULT_LANGUAGE_CODE,
    DEFAULT_PULL_REPRINTS,
    LANGUAGE_MAP,
)

_FILTER_LIST_KEYS = (
    "pardoned_sets",
    "exempt_sets",
    "exempt_promos",
    "exempt_types",
)


@dataclass(frozen=True, kw_only=True)
class AppConfig:
    """Resolved, immutable application configuration.

    Attributes:
        pull_reprints: Whether to download cards flagged as reprints.
        card_language: MTGJSON full language name to keep (e.g. "English").
        pardoned_sets: Set codes kept even when an exempt rule matches.
        exempt_sets: Set codes to skip entirely.
        exempt_promos: Promo types that disqualify a card.
        exempt_types: Set types to skip entirely.
    """

    pull_reprints: bool
    card_language: str
    pardoned_sets: frozenset[str]
    exempt_sets: frozenset[str]
    exempt_promos: frozenset[str]
    exempt_types: frozenset[str]


def _validate_filter_lists(filter_lists: dict[str, Any]) -> None:
    """Raise on a filter-list config value that is not a list.

    A string is iterable, so a typo omitting a TOML array's brackets
    (e.g. `exempt_sets = "MB1"`) would otherwise pass through as a
    frozenset of that string's characters with no error at all.

    Args:
        filter_lists: The merged filter lists, keyed by config field name.

    Raises:
        TypeError: If any of the filter-list values is not a list.
    """
    for key in _FILTER_LIST_KEYS:
        value = filter_lists[key]
        if not isinstance(value, list):
            type_name = type(value).__name__
            message = f"{key} must be a list of strings, got {type_name}"
            raise TypeError(message)


def load_config(
    config_path: Path | None,
    language_override: str | None = None,
) -> AppConfig:
    """Build an AppConfig by layering planar-bridge.toml over the defaults.

    Reads config_path when provided and present, overlays it on the
    built-in defaults, maps the card_language code to MTGJSON's full
    language name, and freezes the exempt/pardon collections.

    Args:
        config_path: Path to a user planar-bridge.toml, or None. A missing
            or None path falls back to the defaults alone.
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
        message = f"language code '{language_code}' not supported"
        raise ValueError(message)

    filter_lists = DEFAULT_FILTER_LISTS | file_data
    _validate_filter_lists(filter_lists)

    return AppConfig(
        pull_reprints=pull_reprints,
        card_language=language_name,
        pardoned_sets=frozenset(filter_lists["pardoned_sets"]),
        exempt_sets=frozenset(filter_lists["exempt_sets"]),
        exempt_promos=frozenset(filter_lists["exempt_promos"]),
        exempt_types=frozenset(filter_lists["exempt_types"]),
    )
