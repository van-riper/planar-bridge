"""The SQLite-backed bulk reader for MTGJSON's ``AllPrintings.sqlite``.

This is an anti-corruption layer: it absorbs the relational shape of MTGJSON's
SQLite distribution (the ``cardIdentifiers``/``tokenIdentifiers`` join for
``scryfallId``, comma-space list fields, ``1``/``NULL`` booleans, tokens
lacking an ``isOnlineOnly`` column) and hands the pipeline back the same
JSON-shaped set/card dictionaries the domain already consumes. Loading one set
at a time keeps memory flat, replacing the whole-file ``json.loads`` of the old
``AllPrintings.json`` path.
"""

import sqlite3
from pathlib import Path

from ..aliases import CardData, SetData
from .ports import BulkSource

# Cards and tokens are projected to the same column shape (tokens have no
# isOnlineOnly column, so it is synthesized as NULL) so one row mapper serves
# both. The list fields are split and the booleans pass through as 1/NULL.
_CARD_QUERY = """
SELECT c.uuid, c.name, c.layout, c.side, c.language,
       c.isReprint, c.isOnlineOnly, c.isFunny,
       c.otherFaceIds, c.promoTypes, i.scryfallId
FROM cards c
LEFT JOIN cardIdentifiers i ON c.uuid = i.uuid
WHERE c.setCode = ?
"""

_TOKEN_QUERY = """
SELECT t.uuid, t.name, t.layout, t.side, t.language,
       t.isReprint, NULL AS isOnlineOnly, t.isFunny,
       t.otherFaceIds, t.promoTypes, i.scryfallId
FROM tokens t
LEFT JOIN tokenIdentifiers i ON t.uuid = i.uuid
WHERE t.setCode = ?
"""


class BulkReader(BulkSource):
    """Reads JSON-shaped set data on demand from ``AllPrintings.sqlite``."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        """Wrap an open connection to the bulk database.

        Args:
            connection: An open connection to the bulk database (a file in
                production, ``:memory:`` in tests).
        """
        self._connection = connection
        self._connection.row_factory = sqlite3.Row

    @classmethod
    def open(cls, database_path: Path) -> "BulkReader":
        """Open the bulk database read-only at a filesystem path.

        The read-only URI keeps the multi-hundred-megabyte bulk file safe from
        accidental mutation; the reader only ever queries it.

        Args:
            database_path: Where the ``AllPrintings.sqlite`` file lives.

        Returns:
            BulkReader: A reader wrapping a read-only connection to that file.
        """
        connection = sqlite3.connect(f"file:{database_path}?mode=ro", uri=True)
        return cls(connection)

    def __enter__(self) -> "BulkReader":
        """Enter a context that closes the reader on exit."""
        return self

    def __exit__(self, *exc_info: object) -> None:
        """Close the reader when the context block exits."""
        self.close()

    def set_codes(self) -> tuple[str, ...]:
        """Return every set code in sorted order, for the run total and walk.

        Listing the codes is cheap and lets the pipeline count the run and then
        load each set on demand, holding only one set's cards in memory.

        Returns:
            All set codes, ascending.
        """
        rows = self._connection.execute(
            "SELECT code FROM sets ORDER BY code"
        ).fetchall()

        return tuple(row["code"] for row in rows)

    def load_set(self, set_code: str) -> SetData:
        """Load one set as a JSON-shaped dictionary the domain can consume.

        Args:
            set_code: The set code to load.

        Returns:
            The set's omit-decision fields plus its ``cards`` and
            ``tokens`` lists, each card carrying a nested ``identifiers``
            dict.
        """
        set_row = self._connection.execute(
            "SELECT code, type, isOnlineOnly, isForeignOnly "
            "FROM sets WHERE code = ?",
            (set_code,),
        ).fetchone()

        return {
            "code": set_row["code"],
            "type": set_row["type"],
            "isOnlineOnly": set_row["isOnlineOnly"],
            "isForeignOnly": set_row["isForeignOnly"],
            "cards": self._load_entries(_CARD_QUERY, set_code),
            "tokens": self._load_entries(_TOKEN_QUERY, set_code),
        }

    def _load_entries(self, query: str, set_code: str) -> list[CardData]:
        """Run a card/token query for one set and map each row to a dict."""
        rows = self._connection.execute(query, (set_code,)).fetchall()

        return [_row_to_card(row) for row in rows]

    def close(self) -> None:
        """Close the underlying database connection."""
        self._connection.close()


def _row_to_card(row: sqlite3.Row) -> CardData:
    """Rebuild one JSON-shaped card/token dict from a projected row.

    Args:
        row (sqlite3.Row): A row from the card or token query, carrying the
            common columns plus the joined ``scryfallId``.

    Returns:
        CardData: The card with split list fields, pass-through boolean flags,
        and the ``scryfallId`` nested under ``identifiers``.
    """
    return {
        "uuid": row["uuid"],
        "name": row["name"],
        "layout": row["layout"],
        "side": row["side"],
        "language": row["language"],
        "isReprint": row["isReprint"],
        "isOnlineOnly": row["isOnlineOnly"],
        "isFunny": row["isFunny"],
        "otherFaceIds": _split_list(row["otherFaceIds"]),
        "promoTypes": _split_list(row["promoTypes"]),
        "identifiers": {"scryfallId": row["scryfallId"]},
    }


def _split_list(value: str | None) -> list[str]:
    """Split a comma-space MTGJSON list field into its members.

    MTGJSON stores list columns such as ``otherFaceIds`` as ``"a, b"``; a NULL
    or empty value means there are no members.

    Args:
        value (str | None): The raw column value.

    Returns:
        list[str]: The members, stripped of whitespace, or an empty list.
    """
    if not value:
        return []

    return [member.strip() for member in value.split(",")]
