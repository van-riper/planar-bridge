"""Shared fixtures for the integration test suite."""

import sqlite3
from collections.abc import Callable, Iterator
from typing import Any

import pytest

from planar_bridge.config.loader import AppConfig


@pytest.fixture
def connection() -> Iterator[sqlite3.Connection]:
    """Yield an in-memory SQLite connection, closed after the test."""
    conn = sqlite3.connect(":memory:")
    yield conn
    conn.close()


@pytest.fixture
def make_config() -> Callable[..., AppConfig]:
    """Return a factory for permissive AppConfigs, overridable per call."""

    def _make_config(**overrides: Any) -> AppConfig:
        base: dict[str, Any] = {
            "pull_reprints": False,
            "card_language": "English",
            "pardoned_sets": frozenset(),
            "exempt_sets": frozenset(),
            "exempt_promos": frozenset({"prerelease"}),
            "exempt_types": frozenset(),
        }
        base.update(overrides)
        return AppConfig(**base)

    return _make_config


@pytest.fixture
def make_card() -> Callable[..., dict[str, Any]]:
    """Return a factory for minimal, non-bad MTGJSON card entries."""

    def _make_card(**overrides: Any) -> dict[str, Any]:
        base: dict[str, Any] = {
            "uuid": "uuid-1",
            "identifiers": {"scryfallId": "scry-1"},
            "layout": "normal",
            "name": "Llanowar Elves",
            "language": "English",
        }
        base.update(overrides)
        return base

    return _make_card
