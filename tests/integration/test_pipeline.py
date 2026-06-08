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
from planar_bridge.events import (
    CardDownloaded,
    CardFailed,
    CardSkipped,
    Event,
    EventBus,
    SetSkipped,
    SetStarted,
    VersionMismatch,
)
from planar_bridge.objects import SetObject
from planar_bridge.options import RunOptions
from planar_bridge.paths import load_paths
from planar_bridge.pipeline import PullContext


class StubScryfall:
    """A Scryfall source double that reports a fixed status and bytes."""

    def __init__(
        self,
        image_status: str = "highres_scan",
        download_result: bytes | None = b"image-bytes",
    ) -> None:
        self._image_status = image_status
        self._download_result = download_result

    async def image_status(self, scryfall_id: str) -> str:
        """Return the canned image status."""

        return self._image_status

    async def download_image(
        self, scryfall_id: str, face: str | None = None
    ) -> bytes | None:
        """Return the canned download result (bytes, or None for failure)."""

        return self._download_result


class StubMtgjson:
    """An MTGJSON source double returning fixed metadata."""

    def __init__(self, info: MetadataInfo) -> None:
        self._info = info

    async def fetch_metadata(self) -> MetadataInfo:
        """Return the canned metadata info."""

        return self._info

    async def download_bulk(self, target: str) -> bytes | None:
        """Return canned bulk bytes (unused by the up-to-date path)."""

        return b"{}"


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
    context = PullContext(
        repository,
        StubScryfall(),
        config,
        bus,
        RunOptions(),
    )

    asyncio.run(pipeline.pull_set(set_obj, context, (1, 1)))

    stored = repository.get_card("uuid-1")
    assert stored is not None
    assert stored.is_high_resolution is True
    assert not repository.low_resolution_sets()


def test_dry_run_reports_a_download_without_writing(
    connection: sqlite3.Connection,
    tmp_path: Path,
    make_card: Callable[..., dict[str, Any]],
    make_config: Callable[..., Any],
) -> None:
    """A dry run emits the would-download event but persists nothing."""

    repository = CatalogRepository(connection)
    paths = load_paths({"PLANAR_BRIDGE_DIR": str(tmp_path)})
    bus = EventBus()
    received: list[Event] = []
    bus.subscribe(received.append)
    config = make_config()
    set_dict: dict[str, Any] = {
        "code": "TST",
        "type": "expansion",
        "cards": [make_card()],
        "tokens": [],
    }
    set_obj = SetObject(set_dict, config, paths, bus)
    context = PullContext(
        repository,
        StubScryfall(),
        config,
        bus,
        RunOptions(dry_run=True),
    )

    asyncio.run(pipeline.pull_set(set_obj, context, (1, 1)))

    assert any(isinstance(event, CardDownloaded) for event in received)
    assert repository.get_card("uuid-1") is None
    assert not (paths.data_directory / "TST").exists()


def test_pull_sets_emits_set_skipped_for_an_omitted_set(
    connection: sqlite3.Connection,
    tmp_path: Path,
    make_config: Callable[..., Any],
) -> None:
    """An omitted set emits SetSkipped instead of being silently skipped."""

    repository = CatalogRepository(connection)
    paths = load_paths({"PLANAR_BRIDGE_DIR": str(tmp_path)})
    bus = EventBus()
    received: list[Event] = []
    bus.subscribe(received.append)
    context = PullContext(
        repository,
        StubScryfall(),
        make_config(),
        bus,
        RunOptions(),
    )
    set_entries: dict[str, Any] = {
        "TST": {
            "code": "TST",
            "type": "expansion",
            "isOnlineOnly": True,
            "cards": [],
            "tokens": [],
        }
    }

    asyncio.run(pipeline._pull_sets(context, paths, set_entries))

    assert SetSkipped(set_code="TST") in received


def test_pull_sets_restricts_to_requested_set_codes(
    connection: sqlite3.Connection,
    tmp_path: Path,
    make_config: Callable[..., Any],
) -> None:
    """--set limits the run to the named codes; the run total reflects it."""

    repository = CatalogRepository(connection)
    paths = load_paths({"PLANAR_BRIDGE_DIR": str(tmp_path)})
    bus = EventBus()
    received: list[Event] = []
    bus.subscribe(received.append)
    context = PullContext(
        repository,
        StubScryfall(),
        make_config(),
        bus,
        RunOptions(only_sets=frozenset({"AAA"})),
    )
    set_entries: dict[str, Any] = {
        "AAA": {"code": "AAA", "type": "expansion", "cards": [], "tokens": []},
        "BBB": {"code": "BBB", "type": "expansion", "cards": [], "tokens": []},
    }

    asyncio.run(pipeline._pull_sets(context, paths, set_entries))

    started = [event for event in received if isinstance(event, SetStarted)]
    assert started == [
        SetStarted(
            set_code="AAA",
            run_count=1,
            run_total=1,
            is_all_high_resolution=True,
        )
    ]


def test_pull_set_emits_card_failed_and_continues(
    connection: sqlite3.Connection,
    tmp_path: Path,
    make_card: Callable[..., dict[str, Any]],
    make_config: Callable[..., Any],
) -> None:
    """A failed download emits CardFailed, records nothing, and does not raise."""

    repository = CatalogRepository(connection)
    paths = load_paths({"PLANAR_BRIDGE_DIR": str(tmp_path)})
    bus = EventBus()
    received: list[Event] = []
    bus.subscribe(received.append)
    config = make_config()
    set_dict: dict[str, Any] = {
        "code": "TST",
        "type": "expansion",
        "cards": [make_card()],
        "tokens": [],
    }
    set_obj = SetObject(set_dict, config, paths, bus)
    context = PullContext(
        repository,
        StubScryfall(download_result=None),
        config,
        bus,
        RunOptions(),
    )

    asyncio.run(pipeline.pull_set(set_obj, context, (1, 1)))

    assert CardFailed(set_code="TST") in received
    assert repository.get_card("uuid-1") is None


def test_pull_set_emits_card_skipped_for_a_bad_card(
    connection: sqlite3.Connection,
    tmp_path: Path,
    make_card: Callable[..., dict[str, Any]],
    make_config: Callable[..., Any],
) -> None:
    """A bad card emits CardSkipped and records nothing, without a download."""

    repository = CatalogRepository(connection)
    paths = load_paths({"PLANAR_BRIDGE_DIR": str(tmp_path)})
    bus = EventBus()
    received: list[Event] = []
    bus.subscribe(received.append)
    config = make_config()
    set_dict: dict[str, Any] = {
        "code": "TST",
        "type": "expansion",
        "cards": [make_card(isReprint=True)],
        "tokens": [],
    }
    set_obj = SetObject(set_dict, config, paths, bus)
    context = PullContext(
        repository,
        StubScryfall(),
        config,
        bus,
        RunOptions(),
    )

    asyncio.run(pipeline.pull_set(set_obj, context, (1, 1)))

    assert CardSkipped(set_code="TST") in received
    assert repository.get_card("uuid-1") is None


def test_resolve_version_drift_emits_the_event() -> None:
    """The version-drift handler emits a VersionMismatch event."""

    bus = EventBus()
    received: list[Event] = []
    bus.subscribe(received.append)

    pipeline._resolve_version_drift(bus, "5.3.0", lambda: True)

    assert VersionMismatch(source_version="5.3.0") in received


def test_resolve_version_drift_aborts_when_disapproved() -> None:
    """A disapproving callback raises KeyboardInterrupt to stop the run."""

    with pytest.raises(KeyboardInterrupt):
        pipeline._resolve_version_drift(EventBus(), "5.3.0", lambda: False)


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
