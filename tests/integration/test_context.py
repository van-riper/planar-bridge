"""Integration tests for the catalog-facing parts of CardObject."""

import sqlite3
from collections.abc import Callable
from pathlib import Path
from typing import Any

from planar_bridge.catalog.repository import CardRow, CatalogRepository
from planar_bridge.pipeline.context import CardObject


def make_row(**overrides: Any) -> CardRow:
    """A CardRow matching the make_card defaults, overridable per test."""
    base: dict[str, Any] = {
        "filename": "uuid-1",
        "set_code": "TST",
        "uuid": "uuid-1",
        "is_high_resolution": True,
        "relative_path": "TST/uuid-1.jpg",
        "updated_at": "2026-06-07T00:00:00",
    }
    base.update(overrides)
    return CardRow(**base)


def test_local_state_is_none_for_an_unknown_card(
    connection: sqlite3.Connection,
    tmp_path: Path,
    make_card: Callable[..., dict[str, Any]],
    make_config: Callable[..., Any],
) -> None:
    """A card absent from the catalog has no local state."""
    repository = CatalogRepository(connection)

    card = CardObject(make_card(), repository, tmp_path / "TST", make_config())

    assert card.local_state is None


def test_local_state_reflects_a_stored_row(
    connection: sqlite3.Connection,
    tmp_path: Path,
    make_card: Callable[..., dict[str, Any]],
    make_config: Callable[..., Any],
) -> None:
    """A card present in the catalog reports its stored resolution."""
    repository = CatalogRepository(connection)
    repository.upsert_card(make_row(is_high_resolution=True))

    card = CardObject(make_card(), repository, tmp_path / "TST", make_config())

    assert card.local_state is True


def test_set_code_and_relative_path_for_a_normal_layout(
    connection: sqlite3.Connection,
    tmp_path: Path,
    make_card: Callable[..., dict[str, Any]],
    make_config: Callable[..., Any],
) -> None:
    """A normal card's image sits at <set>/<filename>.jpg."""
    repository = CatalogRepository(connection)

    card = CardObject(make_card(), repository, tmp_path / "TST", make_config())

    assert card.set_code == "TST"
    assert card.relative_path == "TST/uuid-1.jpg"


def test_relative_path_for_a_token_layout(
    connection: sqlite3.Connection,
    tmp_path: Path,
    make_card: Callable[..., dict[str, Any]],
    make_config: Callable[..., Any],
) -> None:
    """A token card's image sits under the tokens/ subdirectory."""
    repository = CatalogRepository(connection)

    card = CardObject(
        make_card(layout="token"),
        repository,
        tmp_path / "TST",
        make_config(),
    )

    assert card.relative_path == "TST/tokens/uuid-1.jpg"


def test_to_row_builds_a_card_row(
    connection: sqlite3.Connection,
    tmp_path: Path,
    make_card: Callable[..., dict[str, Any]],
    make_config: Callable[..., Any],
) -> None:
    """to_row assembles a CardRow from the card's derived fields."""
    repository = CatalogRepository(connection)
    card = CardObject(make_card(), repository, tmp_path / "TST", make_config())

    row = card.to_row(is_high_resolution=True)

    assert row.filename == "uuid-1"
    assert row.set_code == "TST"
    assert row.uuid == "uuid-1"
    assert row.is_high_resolution is True
    assert row.relative_path == "TST/uuid-1.jpg"
