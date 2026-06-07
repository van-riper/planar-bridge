"""Integration tests for the SQLite-backed CatalogRepository."""

import sqlite3
from typing import Any

import pytest

from planar_bridge.catalog.repository import CardRow, CatalogRepository


def make_card_row(**overrides: Any) -> CardRow:
    """A CardRow with sensible defaults, overridable per test."""

    base: dict[str, Any] = {
        "filename": "abcd",
        "set_code": "TST",
        "uuid": "uuid-abcd",
        "is_high_resolution": True,
        "relative_path": "TST/abcd.png",
        "updated_at": "2026-06-05T00:00:00",
    }
    base.update(overrides)
    return CardRow(**base)


def test_get_card_returns_none_when_absent(
    connection: sqlite3.Connection,
) -> None:
    """Looking up a filename that was never stored yields None."""

    repository = CatalogRepository(connection)

    assert repository.get_card("missing") is None


def test_upsert_then_get_round_trips_a_card(
    connection: sqlite3.Connection,
) -> None:
    """A stored card is read back field-for-field, with a real bool flag."""

    repository = CatalogRepository(connection)
    row = make_card_row()

    repository.upsert_card(row)
    stored = repository.get_card(row.filename)

    assert stored is not None
    assert stored == row
    assert isinstance(stored.is_high_resolution, bool)


def test_upsert_updates_an_existing_card(
    connection: sqlite3.Connection,
) -> None:
    """Upserting the same filename overwrites the prior row in place."""

    repository = CatalogRepository(connection)
    repository.upsert_card(make_card_row(is_high_resolution=False))

    repository.upsert_card(
        make_card_row(is_high_resolution=True, relative_path="TST/new.png")
    )
    stored = repository.get_card("abcd")

    assert stored is not None
    assert stored.is_high_resolution is True
    assert stored.relative_path == "TST/new.png"


def test_is_set_high_resolution_false_when_a_card_is_low_res(
    connection: sqlite3.Connection,
) -> None:
    """A set with any low-res card is not fully high-resolution."""

    repository = CatalogRepository(connection)
    repository.upsert_card(make_card_row(filename="a", is_high_resolution=True))
    repository.upsert_card(
        make_card_row(filename="b", is_high_resolution=False)
    )

    assert repository.is_set_high_resolution("TST") is False


def test_is_set_high_resolution_true_when_all_cards_high_res(
    connection: sqlite3.Connection,
) -> None:
    """A set whose every card is high-res reports fully high-resolution."""

    repository = CatalogRepository(connection)
    repository.upsert_card(make_card_row(filename="a", is_high_resolution=True))
    repository.upsert_card(make_card_row(filename="b", is_high_resolution=True))

    assert repository.is_set_high_resolution("TST") is True


def test_is_set_high_resolution_true_for_unknown_set(
    connection: sqlite3.Connection,
) -> None:
    """An unseen set is vacuously high-res, mirroring the old is_all_highres."""

    repository = CatalogRepository(connection)

    assert repository.is_set_high_resolution("NONE") is True


def test_low_resolution_sets_lists_only_sets_with_low_res_cards(
    connection: sqlite3.Connection,
) -> None:
    """Only set codes that still hold a low-res card are returned."""

    repository = CatalogRepository(connection)
    repository.upsert_card(
        make_card_row(filename="a", set_code="LOW", is_high_resolution=False)
    )
    repository.upsert_card(
        make_card_row(filename="b", set_code="HIGH", is_high_resolution=True)
    )

    assert repository.low_resolution_sets() == ("LOW",)


def test_low_resolution_cards_returns_all_low_res(
    connection: sqlite3.Connection,
) -> None:
    """Without a set filter, every low-res card across all sets is returned."""

    repository = CatalogRepository(connection)
    repository.upsert_card(
        make_card_row(filename="a", set_code="ONE", is_high_resolution=False)
    )
    repository.upsert_card(
        make_card_row(filename="b", set_code="TWO", is_high_resolution=False)
    )
    repository.upsert_card(make_card_row(filename="c", is_high_resolution=True))

    filenames = {card.filename for card in repository.low_resolution_cards()}
    assert filenames == {"a", "b"}


def test_low_resolution_cards_filters_by_set_code(
    connection: sqlite3.Connection,
) -> None:
    """With a set filter, only that set's low-res cards are returned."""

    repository = CatalogRepository(connection)
    repository.upsert_card(
        make_card_row(filename="a", set_code="ONE", is_high_resolution=False)
    )
    repository.upsert_card(
        make_card_row(filename="b", set_code="TWO", is_high_resolution=False)
    )

    cards = repository.low_resolution_cards(set_code="ONE")
    assert [card.filename for card in cards] == ["a"]


def test_close_closes_the_connection(
    connection: sqlite3.Connection,
) -> None:
    """After close, the underlying connection can no longer be used."""

    repository = CatalogRepository(connection)

    repository.close()

    with pytest.raises(sqlite3.ProgrammingError):
        connection.execute("SELECT 1 FROM cards")
