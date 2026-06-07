"""Shared fixtures for the integration test suite."""

import sqlite3

import pytest


@pytest.fixture
def connection():
    """Yield an in-memory SQLite connection, closed after the test."""

    conn = sqlite3.connect(":memory:")
    yield conn
    conn.close()
