"""DDL and versioning for the SQLite catalog database."""

import sqlite3

SCHEMA_VERSION: int = 1

_SCHEMA = """
CREATE TABLE IF NOT EXISTS cards (
    filename TEXT PRIMARY KEY,
    set_code TEXT NOT NULL,
    uuid TEXT NOT NULL,
    is_high_resolution INTEGER NOT NULL,
    relative_path TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_cards_set_resolution
    ON cards (set_code, is_high_resolution);

CREATE INDEX IF NOT EXISTS idx_cards_low_resolution
    ON cards (is_high_resolution)
    WHERE is_high_resolution = 0;
"""


def apply_schema(connection: sqlite3.Connection) -> None:
    """Create the catalog table and indexes and set the schema version.

    Idempotent: safe to call on an already-initialized database. Sets
    PRAGMA user_version to SCHEMA_VERSION so a future schema
    change can detect and upgrade an older database.

    Args:
        connection: An open connection to the catalog database.
    """
    connection.executescript(_SCHEMA)
    connection.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
    connection.commit()
