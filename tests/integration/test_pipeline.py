"""Integration tests for the async pull pipeline wiring (network stubbed)."""

import asyncio
import gzip
import json
import sqlite3
from collections.abc import Callable
from pathlib import Path
from typing import Any

import httpx
import pytest

from planar_bridge.catalog.repository import CardRow, CatalogRepository
from planar_bridge.domain.metadata import MetadataInfo
from planar_bridge.events import (
    BulkDownloadStarted,
    CardDownloaded,
    CardFailed,
    CardSkipped,
    Event,
    EventBus,
    SetSkipped,
    SetStarted,
    VersionMismatch,
)
from planar_bridge.options import RunOptions
from planar_bridge.paths import load_paths
from planar_bridge.pipeline import PullContext, download, metadata, run
from planar_bridge.pipeline.context import SetObject


class StubScryfall:
    """A Scryfall source double that reports a fixed status and bytes."""

    def __init__(
        self,
        image_status: str | None = "highres_scan",
        download_result: bytes | None = b"image-bytes",
    ) -> None:
        self._image_status = image_status
        self._download_result = download_result

    async def image_status(self, scryfall_id: str) -> str | None:
        """Return the canned image status (None models a failed query)."""
        return self._image_status

    async def download_image(
        self, scryfall_id: str, face: str | None = None
    ) -> bytes | None:
        """Return the canned download result (bytes, or None for failure)."""
        return self._download_result


class StubMtgjson:
    """An MTGJSON source double with configurable metadata and bulk results."""

    def __init__(
        self,
        info: MetadataInfo | None,
        download_result: bytes | None = b"{}",
    ) -> None:
        self._info = info
        self._download_result = download_result

    async def fetch_metadata(self) -> MetadataInfo | None:
        """Return the canned metadata info (None models a failed fetch)."""
        return self._info

    async def download_bulk(self, target: str) -> bytes | None:
        """Return the canned bulk bytes (None models a failed download)."""
        return self._download_result


class StubBulk:
    """A bulk source double backed by an in-memory dict of set entries."""

    def __init__(self, sets: dict[str, dict[str, Any]]) -> None:
        self._sets = sets

    def set_codes(self) -> tuple[str, ...]:
        """Return the configured set codes in insertion order."""
        return tuple(self._sets)

    def load_set(self, set_code: str) -> dict[str, Any]:
        """Return the configured set entry for a code."""
        return self._sets[set_code]


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
    set_obj = SetObject(set_dict, config, paths)
    context = PullContext(
        repository,
        StubScryfall(),
        config,
        bus,
        RunOptions(),
    )

    asyncio.run(download.pull_set(set_obj, context, (1, 1)))

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
    set_obj = SetObject(set_dict, config, paths)
    context = PullContext(
        repository,
        StubScryfall(),
        config,
        bus,
        RunOptions(dry_run=True),
    )

    asyncio.run(download.pull_set(set_obj, context, (1, 1)))

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

    asyncio.run(download._pull_sets(context, paths, StubBulk(set_entries)))

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

    asyncio.run(download._pull_sets(context, paths, StubBulk(set_entries)))

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
    """A failed download emits CardFailed and does not crash the run."""
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
    set_obj = SetObject(set_dict, config, paths)
    context = PullContext(
        repository,
        StubScryfall(download_result=None),
        config,
        bus,
        RunOptions(),
    )

    asyncio.run(download.pull_set(set_obj, context, (1, 1)))

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
    set_obj = SetObject(set_dict, config, paths)
    context = PullContext(
        repository,
        StubScryfall(),
        config,
        bus,
        RunOptions(),
    )

    asyncio.run(download.pull_set(set_obj, context, (1, 1)))

    assert CardSkipped(set_code="TST") in received
    assert repository.get_card("uuid-1") is None


def test_resolve_version_drift_emits_the_event() -> None:
    """The version-drift handler emits a VersionMismatch event."""
    bus = EventBus()
    received: list[Event] = []
    bus.subscribe(received.append)

    metadata._resolve_version_drift(bus, "5.3.0", lambda: True)

    assert VersionMismatch(source_version="5.3.0") in received


def test_resolve_version_drift_aborts_when_disapproved() -> None:
    """A disapproving callback raises KeyboardInterrupt to stop the run."""
    with pytest.raises(KeyboardInterrupt):
        metadata._resolve_version_drift(EventBus(), "5.3.0", lambda: False)


def test_pull_meta_keeps_an_existing_meta_json(tmp_path: Path) -> None:
    """A newer source build date does not re-download an existing Meta.json."""
    paths = load_paths({"PLANAR_BRIDGE_DIR": str(tmp_path)})
    paths.mtgjson_directory.mkdir(parents=True)
    paths.metadata_path.write_text(
        json.dumps({"meta": {"date": "2024-01-01", "version": "5.3.0"}})
    )
    paths.bulk_path.write_bytes(b"sqlite-placeholder")
    bus = EventBus()
    source = StubMtgjson(MetadataInfo(date="2030-06-05", version="5.3.0"))

    asyncio.run(metadata.pull_meta(paths, source, bus))

    meta = json.loads(paths.metadata_path.read_bytes())["meta"]
    assert meta["date"] == "2024-01-01"


def test_pull_meta_downloads_meta_json_when_missing(
    tmp_path: Path,
) -> None:
    """A missing Meta.json is fetched; the bulk database is left to run.py."""
    paths = load_paths({"PLANAR_BRIDGE_DIR": str(tmp_path)})
    paths.mtgjson_directory.mkdir(parents=True)
    bus = EventBus()
    source = StubMtgjson(MetadataInfo(date="2030-01-01", version="5.3.0"))

    asyncio.run(metadata.pull_meta(paths, source, bus))

    assert paths.metadata_path.read_bytes() == b"{}"
    assert not paths.bulk_path.exists()


def test_download_bulk_database_writes_the_bulk_path(
    tmp_path: Path,
) -> None:
    """The bulk download writes the fetched bytes to the sqlite bulk path."""
    paths = load_paths({"PLANAR_BRIDGE_DIR": str(tmp_path)})
    paths.mtgjson_directory.mkdir(parents=True)
    bus = EventBus()
    received: list[Event] = []
    bus.subscribe(received.append)
    source = StubMtgjson(MetadataInfo(date="x", version="5.3.0"))

    asyncio.run(run._download_bulk_database(paths, source, bus))

    assert paths.bulk_path.read_bytes() == b"{}"
    assert any(isinstance(event, BulkDownloadStarted) for event in received)


def test_download_bulk_database_skips_when_present(tmp_path: Path) -> None:
    """An existing bulk file is reused: no download, no banner emitted."""
    paths = load_paths({"PLANAR_BRIDGE_DIR": str(tmp_path)})
    paths.mtgjson_directory.mkdir(parents=True)
    paths.bulk_path.write_bytes(b"existing-sqlite")
    bus = EventBus()
    received: list[Event] = []
    bus.subscribe(received.append)
    source = StubMtgjson(MetadataInfo(date="x", version="5.3.0"))

    asyncio.run(run._download_bulk_database(paths, source, bus))

    assert paths.bulk_path.read_bytes() == b"existing-sqlite"
    assert not any(isinstance(e, BulkDownloadStarted) for e in received)


def test_download_bulk_database_raises_when_download_fails(
    tmp_path: Path,
) -> None:
    """A failed bulk download raises RuntimeError instead of writing."""
    paths = load_paths({"PLANAR_BRIDGE_DIR": str(tmp_path)})
    paths.mtgjson_directory.mkdir(parents=True)
    source = StubMtgjson(
        MetadataInfo(date="x", version="5.3.0"), download_result=None
    )

    with pytest.raises(RuntimeError):
        asyncio.run(run._download_bulk_database(paths, source, EventBus()))


def test_pull_meta_raises_when_metadata_fetch_fails(tmp_path: Path) -> None:
    """A failed metadata fetch raises RuntimeError rather than continuing."""
    paths = load_paths({"PLANAR_BRIDGE_DIR": str(tmp_path)})
    source = StubMtgjson(None)

    with pytest.raises(RuntimeError):
        asyncio.run(metadata.pull_meta(paths, source, EventBus()))


def test_pull_meta_warns_on_pinned_version_drift(tmp_path: Path) -> None:
    """Local data built on a non-pinned version emits a VersionMismatch."""
    paths = load_paths({"PLANAR_BRIDGE_DIR": str(tmp_path)})
    paths.mtgjson_directory.mkdir(parents=True)
    paths.metadata_path.write_text(
        json.dumps({"meta": {"date": "2024-01-01", "version": "5.2.0"}})
    )
    paths.bulk_path.write_bytes(b"sqlite-placeholder")
    bus = EventBus()
    received: list[Event] = []
    bus.subscribe(received.append)
    source = StubMtgjson(MetadataInfo(date="2026-06-05", version="5.3.0"))

    asyncio.run(metadata.pull_meta(paths, source, bus))

    assert any(isinstance(e, VersionMismatch) for e in received)


def test_pull_meta_raises_when_meta_download_fails(tmp_path: Path) -> None:
    """A failed Meta.json download raises RuntimeError."""
    paths = load_paths({"PLANAR_BRIDGE_DIR": str(tmp_path)})
    paths.mtgjson_directory.mkdir(parents=True)
    source = StubMtgjson(
        MetadataInfo(date="x", version="5.3.0"), download_result=None
    )

    with pytest.raises(RuntimeError):
        asyncio.run(metadata.pull_meta(paths, source, EventBus()))


def test_pull_set_emits_card_failed_when_status_unavailable(
    connection: sqlite3.Connection,
    tmp_path: Path,
    make_card: Callable[..., dict[str, Any]],
    make_config: Callable[..., Any],
) -> None:
    """An unavailable image status fails the card without raising."""
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
    set_obj = SetObject(set_dict, config, paths)
    context = PullContext(
        repository,
        StubScryfall(image_status=None),
        config,
        bus,
        RunOptions(),
    )

    asyncio.run(download.pull_set(set_obj, context, (1, 1)))

    assert CardFailed(set_code="TST") in received


def test_pull_set_skips_a_placeholder_card(
    connection: sqlite3.Connection,
    tmp_path: Path,
    make_card: Callable[..., dict[str, Any]],
    make_config: Callable[..., Any],
) -> None:
    """A placeholder image carries no usable scan, so the card is skipped."""
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
    set_obj = SetObject(set_dict, config, paths)
    context = PullContext(
        repository,
        StubScryfall(image_status="placeholder"),
        config,
        bus,
        RunOptions(),
    )

    asyncio.run(download.pull_set(set_obj, context, (1, 1)))

    assert CardSkipped(set_code="TST") in received
    assert repository.get_card("uuid-1") is None


def test_pull_set_skips_an_already_downloaded_card(
    connection: sqlite3.Connection,
    tmp_path: Path,
    make_card: Callable[..., dict[str, Any]],
    make_config: Callable[..., Any],
) -> None:
    """A card recorded high-res with its file present skips before Scryfall."""
    repository = CatalogRepository(connection)
    paths = load_paths({"PLANAR_BRIDGE_DIR": str(tmp_path)})
    set_directory = paths.data_directory / "TST"
    set_directory.mkdir(parents=True)
    (set_directory / "uuid-1.jpg").write_bytes(b"img")
    repository.upsert_card(
        CardRow(
            filename="uuid-1",
            set_code="TST",
            uuid="uuid-1",
            is_high_resolution=True,
            relative_path="TST/uuid-1.jpg",
            updated_at="2026-01-01T00:00:00",
        )
    )
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
    set_obj = SetObject(set_dict, config, paths)
    context = PullContext(
        repository,
        StubScryfall(),
        config,
        bus,
        RunOptions(),
    )

    asyncio.run(download.pull_set(set_obj, context, (1, 1)))

    assert CardSkipped(set_code="TST") in received


def _write_bulk_sqlite(database_path: Path) -> None:
    """Build a one-set, one-card AllPrintings.sqlite the reader can load."""
    connection = sqlite3.connect(database_path)
    connection.executescript("""
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
        INSERT INTO sets (code, type) VALUES ('TST', 'expansion');
        INSERT INTO cards (uuid, name, layout, language, setCode)
            VALUES ('uuid-1', 'Llanowar Elves', 'normal', 'English', 'TST');
        INSERT INTO cardIdentifiers (uuid, scryfallId)
            VALUES ('uuid-1', 'scry-1');
        """)
    connection.commit()
    connection.close()


def test_pull_all_runs_end_to_end(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """pull_all wires the whole run: fetch, bulk, stream, download, persist."""
    monkeypatch.setenv("PLANAR_BRIDGE_DIR", str(tmp_path))
    monkeypatch.delenv("XDG_DATA_HOME", raising=False)
    # Make the rate limiter effectively instant for the test.
    monkeypatch.setattr(run.constants, "MAX_REQUESTS_PER_SECOND", 100_000.0)

    source_db = tmp_path / "bulk-source.sqlite"
    _write_bulk_sqlite(source_db)
    bulk_gz = gzip.compress(source_db.read_bytes())
    meta_bytes = json.dumps(
        {"meta": {"date": "2026-06-05", "version": "5.3.0"}}
    ).encode()

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if url.endswith("Meta.json"):
            return httpx.Response(200, content=meta_bytes)
        if url.endswith("Meta.json.gz"):
            return httpx.Response(200, content=gzip.compress(meta_bytes))
        if url.endswith("AllPrintings.sqlite.gz"):
            return httpx.Response(200, content=bulk_gz)
        if "format=json" in url:
            return httpx.Response(200, json={"image_status": "highres_scan"})
        if "format=image" in url:
            return httpx.Response(200, content=b"image-bytes")
        raise AssertionError(f"unexpected request: {url}")

    original_client = httpx.AsyncClient

    def fake_client(*args: Any, **kwargs: Any) -> httpx.AsyncClient:
        kwargs["transport"] = httpx.MockTransport(handler)
        return original_client(*args, **kwargs)

    monkeypatch.setattr(run.httpx, "AsyncClient", fake_client)

    bus = EventBus()
    received: list[Event] = []
    bus.subscribe(received.append)

    asyncio.run(run.pull_all(bus, RunOptions(only_sets=frozenset({"TST"}))))

    assert any(isinstance(e, CardDownloaded) for e in received)
    assert paths_has_image(tmp_path)
    with CatalogRepository.open(tmp_path / "catalog.sqlite") as repository:
        assert repository.get_card("uuid-1") is not None


def paths_has_image(data_directory: Path) -> bool:
    """True when at least one downloaded scan exists under the data dir."""
    return any(data_directory.rglob("*.jpg"))
