"""Integration tests for the async pull pipeline wiring (network stubbed)."""

import asyncio
import json
import sqlite3
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from planar_bridge import pipeline
from planar_bridge.catalog.repository import CatalogRepository
from planar_bridge.domain.metadata import MetadataInfo
from planar_bridge.events import EventBus
from planar_bridge.objects import SetObject
from planar_bridge.paths import load_paths
from planar_bridge.pipeline import PullContext


class StubScryfall:
    """A Scryfall source double that reports a fixed status and bytes."""

    def __init__(self, image_status: str = "highres_scan") -> None:
        self._image_status = image_status

    async def image_status(self, scryfall_id: str) -> str:
        """Return the canned image status."""

        return self._image_status

    async def download_image(
        self, scryfall_id: str, face: str | None = None
    ) -> bytes:
        """Return canned image bytes."""

        return b"image-bytes"


class StubMtgjson:
    """An MTGJSON source double returning fixed metadata."""

    def __init__(self, info: MetadataInfo) -> None:
        self._info = info

    async def fetch_metadata(self) -> MetadataInfo:
        """Return the canned metadata info."""

        return self._info


def test_pull_set_upserts_a_downloaded_card(
    connection: sqlite3.Connection,
    tmp_path: Path,
    make_card: Callable[..., dict[str, Any]],
    make_config: Callable[..., Any],
) -> None:
    """pull_set persists each successfully downloaded card to the catalog."""

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
    context = PullContext(repository, StubScryfall(), config, bus)

    asyncio.run(pipeline.pull_set(set_obj, context, "1/1"))

    stored = repository.get_card("uuid-1")
    assert stored is not None
    assert stored.is_high_resolution is True
    assert not repository.low_resolution_sets()


def test_pull_meta_exits_when_up_to_date(tmp_path: Path) -> None:
    """pull_meta exits cleanly when local data already matches the source."""

    paths = load_paths({"PLANAR_BRIDGE_DIR": str(tmp_path)})
    paths.json_directory.mkdir(parents=True)
    paths.metadata_path.write_text(
        json.dumps({"meta": {"date": "2024-01-01", "version": "5.2.2"}})
    )
    paths.bulk_path.write_text(json.dumps({"data": {}}))
    bus = EventBus()
    source = StubMtgjson(MetadataInfo(date="2024-01-01", version="5.2.2"))

    with pytest.raises(SystemExit):
        asyncio.run(pipeline.pull_meta(paths, source, bus))
