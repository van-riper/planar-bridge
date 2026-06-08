"""Integration tests for the SQLite-backed bulk reader.

Written before the implementation (TDD): these assertions pin the contract
for ``BulkReader``, which reconstructs the JSON-shaped set/card dictionaries
the domain consumes from MTGJSON's relational ``AllPrintings.sqlite``.

The fixtures build a tiny database mirroring the real schema's quirks (the
``cardIdentifiers`` join for ``scryfallId``, comma-space list fields, ``1``/
``NULL`` booleans, and tokens lacking an ``isOnlineOnly`` column) rather than
shipping the 600MB production file.
"""

import sqlite3
from pathlib import Path
from typing import Any

import pytest

from planar_bridge.sources.bulk import BulkReader

_SCHEMA = """
CREATE TABLE sets (
    code TEXT, type TEXT, isOnlineOnly INTEGER, isForeignOnly INTEGER
);
CREATE TABLE cards (
    uuid TEXT, name TEXT, layout TEXT, side TEXT, language TEXT,
    isReprint INTEGER, isOnlineOnly INTEGER, isFunny INTEGER,
    otherFaceIds TEXT, promoTypes TEXT, setCode TEXT
);
CREATE TABLE tokens (
    uuid TEXT, name TEXT, layout TEXT, side TEXT, language TEXT,
    isReprint INTEGER, isFunny INTEGER,
    otherFaceIds TEXT, promoTypes TEXT, setCode TEXT
);
CREATE TABLE cardIdentifiers (uuid TEXT, scryfallId TEXT);
CREATE TABLE tokenIdentifiers (uuid TEXT, scryfallId TEXT);
"""


def _create_schema(connection: sqlite3.Connection) -> None:
    connection.executescript(_SCHEMA)


def _insert_set(
    connection: sqlite3.Connection, code: str, **overrides: Any
) -> None:
    row: dict[str, Any] = {
        "code": code,
        "type": "expansion",
        "isOnlineOnly": None,
        "isForeignOnly": None,
    }
    row.update(overrides)
    connection.execute(
        "INSERT INTO sets (code, type, isOnlineOnly, isForeignOnly) "
        "VALUES (:code, :type, :isOnlineOnly, :isForeignOnly)",
        row,
    )


def _insert_card(
    connection: sqlite3.Connection,
    *,
    set_code: str = "TST",
    scryfall_id: str | None = "scry-1",
    **overrides: Any,
) -> None:
    row: dict[str, Any] = {
        "uuid": "uuid-1",
        "name": "Llanowar Elves",
        "layout": "normal",
        "side": None,
        "language": "English",
        "isReprint": None,
        "isOnlineOnly": None,
        "isFunny": None,
        "otherFaceIds": None,
        "promoTypes": None,
        "setCode": set_code,
    }
    row.update(overrides)
    connection.execute(
        "INSERT INTO cards (uuid, name, layout, side, language, isReprint, "
        "isOnlineOnly, isFunny, otherFaceIds, promoTypes, setCode) VALUES "
        "(:uuid, :name, :layout, :side, :language, :isReprint, :isOnlineOnly, "
        ":isFunny, :otherFaceIds, :promoTypes, :setCode)",
        row,
    )
    connection.execute(
        "INSERT INTO cardIdentifiers (uuid, scryfallId) VALUES (?, ?)",
        (row["uuid"], scryfall_id),
    )


def _insert_token(
    connection: sqlite3.Connection,
    *,
    set_code: str = "TST",
    scryfall_id: str | None = "scry-tok",
    **overrides: Any,
) -> None:
    row: dict[str, Any] = {
        "uuid": "uuid-tok",
        "name": "Soldier",
        "layout": "token",
        "side": None,
        "language": "English",
        "isReprint": None,
        "isFunny": None,
        "otherFaceIds": None,
        "promoTypes": None,
        "setCode": set_code,
    }
    row.update(overrides)
    connection.execute(
        "INSERT INTO tokens (uuid, name, layout, side, language, isReprint, "
        "isFunny, otherFaceIds, promoTypes, setCode) VALUES "
        "(:uuid, :name, :layout, :side, :language, :isReprint, :isFunny, "
        ":otherFaceIds, :promoTypes, :setCode)",
        row,
    )
    connection.execute(
        "INSERT INTO tokenIdentifiers (uuid, scryfallId) VALUES (?, ?)",
        (row["uuid"], scryfall_id),
    )


def test_set_codes_lists_every_set_in_sorted_order(
    connection: sqlite3.Connection,
) -> None:
    """set_codes returns all set codes, ordered for a stable run sequence."""

    _create_schema(connection)
    _insert_set(connection, "BBB")
    _insert_set(connection, "AAA")

    reader = BulkReader(connection)

    assert reader.set_codes() == ("AAA", "BBB")


def test_load_set_returns_the_set_metadata(
    connection: sqlite3.Connection,
) -> None:
    """A loaded set carries the omit-decision fields the domain reads."""

    _create_schema(connection)
    _insert_set(
        connection, "TST", type="funny", isOnlineOnly=1, isForeignOnly=None
    )

    set_data = BulkReader(connection).load_set("TST")

    assert set_data["code"] == "TST"
    assert set_data["type"] == "funny"
    assert set_data["isOnlineOnly"] == 1
    assert set_data["isForeignOnly"] is None


def test_load_set_nests_scryfall_id_under_identifiers(
    connection: sqlite3.Connection,
) -> None:
    """The joined scryfallId is nested where build_card_fields reads it."""

    _create_schema(connection)
    _insert_set(connection, "TST")
    _insert_card(connection, scryfall_id="scry-xyz")

    set_data = BulkReader(connection).load_set("TST")

    (card,) = set_data["cards"]
    assert card["identifiers"]["scryfallId"] == "scry-xyz"


def test_load_set_splits_comma_space_list_fields(
    connection: sqlite3.Connection,
) -> None:
    """otherFaceIds and promoTypes split on the comma and strip the space."""

    _create_schema(connection)
    _insert_set(connection, "TST")
    _insert_card(
        connection,
        otherFaceIds="aaa, bbb",
        promoTypes="universesbeyond, rainbowfoil",
    )

    (card,) = BulkReader(connection).load_set("TST")["cards"]

    assert card["otherFaceIds"] == ["aaa", "bbb"]
    assert card["promoTypes"] == ["universesbeyond", "rainbowfoil"]


def test_load_set_empty_list_fields_become_empty_lists(
    connection: sqlite3.Connection,
) -> None:
    """A NULL list field reconstructs as an empty list, not None."""

    _create_schema(connection)
    _insert_set(connection, "TST")
    _insert_card(connection, otherFaceIds=None, promoTypes=None)

    (card,) = BulkReader(connection).load_set("TST")["cards"]

    assert card["otherFaceIds"] == []
    assert card["promoTypes"] == []


def test_load_set_passes_boolean_flags_through(
    connection: sqlite3.Connection,
) -> None:
    """The 1/NULL flags pass through unchanged for the domain's truthiness."""

    _create_schema(connection)
    _insert_set(connection, "TST")
    _insert_card(connection, isReprint=1, isFunny=None)

    (card,) = BulkReader(connection).load_set("TST")["cards"]

    assert card["isReprint"] == 1
    assert card["isFunny"] is None


def test_load_set_includes_tokens_with_a_synthesized_online_flag(
    connection: sqlite3.Connection,
) -> None:
    """Tokens load from their own tables; the absent flag becomes None."""

    _create_schema(connection)
    _insert_set(connection, "TST")
    _insert_token(connection, scryfall_id="scry-tok")

    set_data = BulkReader(connection).load_set("TST")

    (token,) = set_data["tokens"]
    assert token["identifiers"]["scryfallId"] == "scry-tok"
    assert token["isOnlineOnly"] is None


def test_load_set_keeps_cards_and_tokens_separate(
    connection: sqlite3.Connection,
) -> None:
    """A set's cards and tokens land in their own lists, not commingled."""

    _create_schema(connection)
    _insert_set(connection, "TST")
    _insert_card(connection, uuid="card-uuid")
    _insert_token(connection, uuid="token-uuid")

    set_data = BulkReader(connection).load_set("TST")

    assert [c["uuid"] for c in set_data["cards"]] == ["card-uuid"]
    assert [t["uuid"] for t in set_data["tokens"]] == ["token-uuid"]


def test_load_set_filters_by_set_code(
    connection: sqlite3.Connection,
) -> None:
    """Only the requested set's cards are returned, not another set's."""

    _create_schema(connection)
    _insert_set(connection, "AAA")
    _insert_set(connection, "BBB")
    _insert_card(connection, uuid="a", set_code="AAA")
    _insert_card(connection, uuid="b", set_code="BBB")

    set_data = BulkReader(connection).load_set("AAA")

    assert [c["uuid"] for c in set_data["cards"]] == ["a"]


def test_open_reads_a_file_database(tmp_path: Path) -> None:
    """open() connects to a real file and reads a set back."""

    database_path = tmp_path / "AllPrintings.sqlite"
    builder = sqlite3.connect(database_path)
    _create_schema(builder)
    _insert_set(builder, "TST")
    _insert_card(builder)
    builder.commit()
    builder.close()

    with BulkReader.open(database_path) as reader:
        assert reader.set_codes() == ("TST",)
        assert reader.load_set("TST")["cards"][0]["uuid"] == "uuid-1"


def test_open_is_read_only(tmp_path: Path) -> None:
    """open() refuses writes, protecting the bulk file from mutation."""

    database_path = tmp_path / "AllPrintings.sqlite"
    builder = sqlite3.connect(database_path)
    _create_schema(builder)
    builder.commit()
    builder.close()

    with BulkReader.open(database_path) as reader:
        with pytest.raises(sqlite3.OperationalError):
            reader._connection.execute(  # pylint: disable=protected-access
                "INSERT INTO sets (code) VALUES ('NEW')"
            )


def test_close_closes_the_connection(
    connection: sqlite3.Connection,
) -> None:
    """After close, the underlying connection can no longer be used."""

    _create_schema(connection)
    reader = BulkReader(connection)

    reader.close()

    with pytest.raises(sqlite3.ProgrammingError):
        connection.execute("SELECT 1 FROM sets")
