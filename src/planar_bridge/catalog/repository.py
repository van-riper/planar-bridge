"""The CatalogRepository: a SQLite-backed store of per-card resolution state.

This is the only layer that knows SQLite. It replaces the per-set
.states.json files with one catalog database, persisting each card write
immediately so a killed run resumes from confirmed state, matching the old
StatesObject "confirmed only" contract.
"""

import sqlite3
from dataclasses import dataclass
from pathlib import Path

from planar_bridge.catalog.schema import apply_schema


@dataclass(frozen=True, kw_only=True)
class CardRow:
    """One card's persisted catalog state.

    Attributes:
        filename: The image filename stem, the catalog primary key.
        set_code: The MTGJSON set code the card belongs to.
        uuid: The card's MTGJSON UUID.
        is_high_resolution: True when the stored scan is high-resolution.
        relative_path: The card's image path relative to the data
            directory (the set directory, with tokens/ for token layouts).
        updated_at: ISO-8601 timestamp of the row's last write.
    """

    filename: str
    set_code: str
    uuid: str
    is_high_resolution: bool
    relative_path: str
    updated_at: str


class CatalogRepository:
    """A SQLite-backed catalog of per-card resolution state."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        """Wrap an open connection, applying the schema so the tables exist.

        Args:
            connection: An open connection to the catalog database (a file
                path in production, :memory: in tests).
        """
        self._connection = connection
        self._connection.row_factory = sqlite3.Row
        apply_schema(self._connection)

    @classmethod
    def open(cls, database_path: Path) -> "CatalogRepository":
        """Open (or create) the catalog database at a filesystem path.

        Keeps sqlite3 confined to this package: callers hand over a path and
        get back a ready repository without touching the database driver.

        Args:
            database_path: Where the SQLite catalog file lives.

        Returns:
            A repository wrapping a connection to that file.
        """
        return cls(sqlite3.connect(database_path))

    def __enter__(self) -> "CatalogRepository":
        """Enter a context that closes the repository on exit.

        Returns:
            This repository.
        """
        return self

    def __exit__(self, *exc_info: object) -> None:
        """Close the repository when the context block exits."""
        self.close()

    def get_card(self, filename: str) -> CardRow | None:
        """Return the stored row for a filename, or None when absent.

        Args:
            filename: The image filename stem to look up.

        Returns:
            The stored row, or None when no such card exists.
        """
        row = self._connection.execute(
            "SELECT filename, set_code, uuid, is_high_resolution, "
            "relative_path, updated_at FROM cards WHERE filename = ?",
            (filename,),
        ).fetchone()

        return _row_to_card(row) if row is not None else None

    def upsert_card(self, row: CardRow) -> None:
        """Insert or replace a card row, committing immediately.

        Args:
            row: The card state to persist.
        """
        self._connection.execute(
            "INSERT INTO cards (filename, set_code, uuid, is_high_resolution, "
            "relative_path, updated_at) VALUES (?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(filename) DO UPDATE SET "
            "set_code = excluded.set_code, uuid = excluded.uuid, "
            "is_high_resolution = excluded.is_high_resolution, "
            "relative_path = excluded.relative_path, "
            "updated_at = excluded.updated_at",
            (
                row.filename,
                row.set_code,
                row.uuid,
                int(row.is_high_resolution),
                row.relative_path,
                row.updated_at,
            ),
        )
        self._connection.commit()

    def is_set_high_resolution(self, set_code: str) -> bool:
        """Report whether a set holds no low-resolution cards.

        Vacuously True for a set with no stored cards, mirroring the old
        StatesObject.is_all_highres on an empty map.

        Args:
            set_code: The set code to check.

        Returns:
            True when the set has no low-resolution card.
        """
        row = self._connection.execute(
            "SELECT NOT EXISTS(SELECT 1 FROM cards "
            "WHERE set_code = ? AND is_high_resolution = 0)",
            (set_code,),
        ).fetchone()

        return bool(row[0])

    def low_resolution_sets(self) -> tuple[str, ...]:
        """Return the set codes that still hold at least one low-res card.

        Returns:
            The distinct set codes needing more work.
        """
        rows = self._connection.execute(
            "SELECT DISTINCT set_code FROM cards "
            "WHERE is_high_resolution = 0 ORDER BY set_code"
        ).fetchall()

        return tuple(row[0] for row in rows)

    def low_resolution_cards(
        self, set_code: str | None = None
    ) -> list[CardRow]:
        """Return the low-resolution cards, optionally limited to one set.

        Args:
            set_code: When given, restrict the result to this set.

        Returns:
            The matching low-resolution card rows.
        """
        query = (
            "SELECT filename, set_code, uuid, is_high_resolution, "
            "relative_path, updated_at FROM cards WHERE is_high_resolution = 0"
        )
        parameters: tuple[str, ...] = ()
        if set_code is not None:
            query += " AND set_code = ?"
            parameters = (set_code,)
        query += " ORDER BY filename"

        rows = self._connection.execute(query, parameters).fetchall()

        return [_row_to_card(row) for row in rows]

    def close(self) -> None:
        """Close the underlying database connection."""
        self._connection.close()


def _row_to_card(row: sqlite3.Row) -> CardRow:
    """Build a CardRow from a database row, restoring the bool flag.

    Args:
        row: A row carrying every cards column.

    Returns:
        The reconstructed card state.
    """
    return CardRow(
        filename=row["filename"],
        set_code=row["set_code"],
        uuid=row["uuid"],
        is_high_resolution=bool(row["is_high_resolution"]),
        relative_path=row["relative_path"],
        updated_at=row["updated_at"],
    )
