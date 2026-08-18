"""Integration tests for the SQLite catalog schema."""

import sqlite3

from planar_bridge.catalog import schema


def _table_names(connection: sqlite3.Connection) -> set[str]:
    """Return the names of every table in the database."""
    rows = connection.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table'"
    ).fetchall()
    return {row[0] for row in rows}


def _index_names(connection: sqlite3.Connection) -> set[str]:
    """Return the names of every index in the database."""
    rows = connection.execute(
        "SELECT name FROM sqlite_master WHERE type = 'index'"
    ).fetchall()
    return {row[0] for row in rows}


def _column_names(connection: sqlite3.Connection, table: str) -> set[str]:
    """Return the column names of table."""
    rows = connection.execute(f"PRAGMA table_info({table})").fetchall()
    return {row[1] for row in rows}


def test_apply_schema_creates_cards_table(
    connection: sqlite3.Connection,
) -> None:
    """The cards table exists after the schema is applied."""
    schema.apply_schema(connection)

    assert "cards" in _table_names(connection)


def test_cards_table_has_expected_columns(
    connection: sqlite3.Connection,
) -> None:
    """The cards table carries exactly the catalog's card columns."""
    schema.apply_schema(connection)

    assert _column_names(connection, "cards") == {
        "filename",
        "set_code",
        "uuid",
        "is_high_resolution",
        "relative_path",
        "updated_at",
    }


def test_apply_schema_creates_indexes(
    connection: sqlite3.Connection,
) -> None:
    """Both cards indexes exist after the schema is applied."""
    schema.apply_schema(connection)

    assert {
        "idx_cards_set_resolution",
        "idx_cards_low_resolution",
    } <= _index_names(connection)


def test_apply_schema_sets_user_version(
    connection: sqlite3.Connection,
) -> None:
    """The schema stamps PRAGMA user_version with the schema version."""
    schema.apply_schema(connection)

    user_version = connection.execute("PRAGMA user_version").fetchone()[0]
    assert user_version == schema.SCHEMA_VERSION
    assert schema.SCHEMA_VERSION >= 1


def test_apply_schema_is_idempotent(
    connection: sqlite3.Connection,
) -> None:
    """Applying the schema twice is harmless and leaves the table intact."""
    schema.apply_schema(connection)
    schema.apply_schema(connection)

    assert "cards" in _table_names(connection)
