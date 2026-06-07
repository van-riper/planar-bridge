"""Integration test for the pull_set pipeline wiring (network stubbed out)."""

import sqlite3
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from planar_bridge import pull
from planar_bridge.catalog.repository import CatalogRepository
from planar_bridge.events import EventBus
from planar_bridge.objects import CardObject, SetObject
from planar_bridge.paths import load_paths


def test_pull_set_upserts_a_downloaded_card(
    connection: sqlite3.Connection,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    make_card: Callable[..., dict[str, Any]],
    make_config: Callable[..., Any],
) -> None:
    """pull_set persists each successfully downloaded card to the catalog."""

    monkeypatch.setattr(
        CardObject, "parse_source_state", lambda self: (True, True)
    )
    monkeypatch.setattr(CardObject, "download", lambda self: True)

    repository = CatalogRepository(connection)
    paths = load_paths({"PLANAR_BRIDGE_DIR": str(tmp_path)})
    bus = EventBus()
    config = make_config()
    set_dict: dict[str, Any] = {
        "code": "TST",
        "type": "expansion",
        "cards": [make_card()],
        "tokens": [],
    }
    set_obj = SetObject(set_dict, config, paths, bus)

    pull.pull_set(set_obj, repository, "1/1", config, bus)

    stored = repository.get_card("uuid-1")
    assert stored is not None
    assert stored.is_high_resolution is True
    assert not repository.low_resolution_sets()
