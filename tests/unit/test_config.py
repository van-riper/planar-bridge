"""Unit tests for configuration loading.

Written before the implementation (TDD): these assertions define the
contract for `AppConfig` and `load_config`.
"""

from pathlib import Path

import pytest

from planar_bridge.config import AppConfig, load_config


def test_defaults_apply_when_file_absent(tmp_path: Path) -> None:
    """A missing config file yields the documented defaults."""

    config = load_config(tmp_path / "absent.toml")
    assert isinstance(config, AppConfig)
    assert config.pull_reprints is False
    assert config.card_language == "English"
    assert "30A" in config.pardoned_sets


def test_file_values_override_defaults(tmp_path: Path) -> None:
    """Values in config.toml take precedence over the defaults."""

    config_path = tmp_path / "config.toml"
    config_path.write_text(
        'pull_reprints = true\ncard_language = "ja"\n',
        encoding="UTF-8",
    )
    config = load_config(config_path)
    assert config.pull_reprints is True
    assert config.card_language == "Japanese"


def test_language_code_maps_to_full_name(tmp_path: Path) -> None:
    """card_language is stored as MTGJSON's full language name."""

    config_path = tmp_path / "config.toml"
    config_path.write_text('card_language = "de"\n', encoding="UTF-8")
    assert load_config(config_path).card_language == "German"


def test_exempt_collections_are_frozensets(tmp_path: Path) -> None:
    """Exempt/pardon collections are frozensets for fast membership."""

    config = load_config(tmp_path / "absent.toml")
    assert isinstance(config.exempt_types, frozenset)
    assert "token" in config.exempt_types


def test_unknown_language_code_raises(tmp_path: Path) -> None:
    """An unrecognized card_language raises ValueError."""

    config_path = tmp_path / "config.toml"
    config_path.write_text('card_language = "xx"\n', encoding="UTF-8")
    with pytest.raises(ValueError):
        load_config(config_path)


def test_language_override_beats_file_and_default(tmp_path: Path) -> None:
    """A language override takes precedence over the file and the default."""

    config_path = tmp_path / "config.toml"
    config_path.write_text('card_language = "de"\n', encoding="UTF-8")
    config = load_config(config_path, language_override="ja")
    assert config.card_language == "Japanese"


def test_unknown_language_override_raises(tmp_path: Path) -> None:
    """An unrecognized override code raises ValueError like the file path."""

    with pytest.raises(ValueError):
        load_config(tmp_path / "absent.toml", language_override="xx")
