"""The async pull pipeline: metadata check, then per-set card downloads.

``pull_all`` builds one shared async engine for the run, checks MTGJSON's
metadata, then walks every set. Sets are processed one at a time; within a set
its cards download concurrently under a bounded semaphore, while the shared rate
limiter keeps total throughput under Scryfall's ceiling. Progress is persisted
per card to the catalog, so a killed run resumes from confirmed state.
"""

import asyncio
import json
from dataclasses import dataclass
from os import environ

import httpx

from . import constants, utils
from .aliases import CardData, SetEntries
from .catalog.repository import CatalogRepository
from .config.loader import AppConfig, load_config
from .domain.decisions import decide_download
from .domain.metadata import MetadataInfo, compare_metadata, normalize_version
from .engine.client import AsyncHttpClient
from .engine.limiter import RateLimiter
from .events import (
    BulkDataLoaded,
    BulkDownloadStarted,
    CardDownloaded,
    CardUpgraded,
    EventBus,
    MetadataCheckStarted,
    MetadataChecked,
    RunFinished,
    SetSkipped,
    SetStarted,
)
from .objects import CardObject, SetObject
from .paths import DataPaths, ensure_directories_exist, load_paths
from .sources.mtgjson import BULK_TARGETS, MtgjsonSource
from .sources.scryfall import ScryfallSource

REQUEST_TIMEOUT_SECONDS = 30.0


@dataclass(frozen=True)
class PullContext:
    """The run-wide dependencies threaded through the set and card loops.

    Attributes:
        repository (CatalogRepository): The catalog of stored card state.
        scryfall_source (ScryfallSource): The Scryfall network source.
        config (AppConfig): Resolved filtering configuration.
        bus (EventBus): The event bus for set and card events.
    """

    repository: CatalogRepository
    scryfall_source: ScryfallSource
    config: AppConfig
    bus: EventBus


def _read_local_metadata(paths: DataPaths) -> MetadataInfo | None:
    """Read the on-disk MTGJSON metadata, or None when bulk data is absent."""

    if not (paths.bulk_path.exists() and paths.metadata_path.exists()):
        return None

    meta = json.loads(paths.metadata_path.read_bytes())["meta"]

    return MetadataInfo(
        date=meta["date"],
        version=normalize_version(meta["version"]),
    )


def _prompt_version_mismatch(source_version: str) -> None:
    """Warn about a version drift and abort unless the user opts to proceed."""

    message = "".join(
        (
            "MTGJSON has been updated to v",
            source_version + "\n",
            constants.VERS_WARNING,
        )
    )

    utils.status(message, 1)

    if not utils.boolify_str(input("Do you want to proceed? [y/N]: "), False):
        raise KeyboardInterrupt


async def pull_meta(
    paths: DataPaths,
    mtgjson_source: MtgjsonSource,
    bus: EventBus,
) -> None:
    """Check MTGJSON's metadata and refresh the bulk files when outdated.

    Args:
        paths (DataPaths): The resolved data paths.
        mtgjson_source (MtgjsonSource): The MTGJSON network source.
        bus (EventBus): The event bus for metadata events.

    Raises:
        SystemExit: When local data is already up to date.
        RuntimeError: When a network fetch fails.
    """

    bus.emit(MetadataCheckStarted())

    source_info = await mtgjson_source.fetch_metadata()
    if source_info is None:
        raise RuntimeError

    comparison = compare_metadata(
        _read_local_metadata(paths), source_info, constants.MTGJSON_VERS
    )

    bus.emit(
        MetadataChecked(
            is_outdated=comparison.is_outdated,
            version_matches_pinned=comparison.version_matches_pinned,
            source_version=source_info.version,
        )
    )

    if not comparison.is_outdated:
        raise SystemExit

    if not comparison.version_matches_pinned:
        _prompt_version_mismatch(source_info.version)

    bus.emit(BulkDownloadStarted())

    for target in BULK_TARGETS:
        content = await mtgjson_source.download_bulk(target)
        if content is None:
            raise RuntimeError
        (paths.json_directory / f"{target}.json").write_bytes(content)


async def pull_card(
    card_obj: CardObject,
    scryfall_source: ScryfallSource,
) -> tuple[bool, bool]:
    """Download one card's image when needed, writing it to disk.

    Args:
        card_obj (CardObject): The card's facts, paths, and stored state.
        scryfall_source (ScryfallSource): The Scryfall network source.

    Returns:
        tuple[bool, bool]: ``(should_record, source_is_high_resolution)``.
        ``should_record`` is False when the card is skipped (bad, already
        stored, or no usable source scan).

    Raises:
        RuntimeError: When a network request fails after its retries.
    """

    if card_obj.card.is_bad:
        return False, False

    if card_obj.local_state and card_obj.path_exists:
        return False, False

    image_status = await scryfall_source.image_status(card_obj.card.scryfall_id)
    if image_status is None:
        raise RuntimeError

    decision = decide_download(
        image_status, card_obj.local_state, card_obj.path_exists
    )

    if not decision.should_download:
        return False, False

    content = await scryfall_source.download_image(
        card_obj.card.scryfall_id, card_obj.card.face
    )
    if content is None:
        raise RuntimeError

    card_obj.img_path.parent.mkdir(parents=True, exist_ok=True)
    card_obj.img_path.write_bytes(content)

    return True, decision.source_is_high_resolution


async def pull_set(
    set_obj: SetObject,
    context: PullContext,
    progress: str,
) -> None:
    """Download every card in a set concurrently under a bounded semaphore.

    Args:
        set_obj (SetObject): The set's record, directory, and progress.
        context (PullContext): The run-wide dependencies.
        progress (str): The run-level progress string for this set.
    """

    context.bus.emit(
        SetStarted(
            set_code=set_obj.record.set_code,
            progress=progress,
            is_all_high_resolution=context.repository.is_set_high_resolution(
                set_obj.record.set_code
            ),
        )
    )

    semaphore = asyncio.Semaphore(constants.MAX_CONCURRENT_DOWNLOADS)

    async def handle(card_entry: CardData) -> None:
        async with semaphore:
            await _handle_card(set_obj, context, progress, card_entry)

    await asyncio.gather(
        *(handle(entry) for entry in set_obj.record.card_entries)
    )


async def _handle_card(
    set_obj: SetObject,
    context: PullContext,
    progress: str,
    card_entry: CardData,
) -> None:
    """Download one card and record and report it when it lands."""

    set_obj.increase_progress()

    card_obj = CardObject(
        card_entry, context.repository, set_obj.set_directory, context.config
    )

    should_record, source_state = await pull_card(
        card_obj, context.scryfall_source
    )

    if not should_record:
        return

    context.repository.upsert_card(card_obj.to_row(source_state))

    card_event = CardUpgraded if card_obj.path_exists else CardDownloaded
    context.bus.emit(
        card_event(
            set_code=set_obj.record.set_code,
            run_progress=progress,
            set_progress=set_obj.inner_progress(),
            display_label=card_obj.card.display_label,
        )
    )


async def _pull_sets(
    context: PullContext,
    paths: DataPaths,
    set_entries: SetEntries,
) -> None:
    """Walk every set in order, downloading the ones not omitted."""

    set_total = len(set_entries)

    for set_count, set_entry in enumerate(set_entries.values(), 1):

        set_obj = SetObject(set_entry, context.config, paths, context.bus)

        if set_obj.record.is_omitted:
            context.bus.emit(SetSkipped(set_code=set_obj.record.set_code))
            continue

        progress = utils.progress_str(set_count, set_total, False)
        await pull_set(set_obj, context, progress)

    context.bus.emit(
        RunFinished(
            low_resolution_set_codes=context.repository.low_resolution_sets()
        )
    )


async def pull_all(bus: EventBus) -> None:
    """Run the whole pull: metadata check, then every set's downloads.

    Args:
        bus (EventBus): The event bus, already wired to its reporters by the
            caller, that the run emits progress and outcome events on.
    """

    paths: DataPaths = load_paths(environ)
    ensure_directories_exist(paths)

    config: AppConfig = load_config(paths.config_path)

    async with httpx.AsyncClient(
        timeout=REQUEST_TIMEOUT_SECONDS,
        headers=constants.HTTP_HEADERS,
    ) as http_client:

        client = AsyncHttpClient(
            http_client, RateLimiter(constants.MAX_REQUESTS_PER_SECOND)
        )

        await pull_meta(paths, MtgjsonSource(client), bus)

        date: str = json.loads(paths.metadata_path.read_bytes())["meta"]["date"]
        bus.emit(BulkDataLoaded(date=date))

        set_entries: SetEntries = json.loads(paths.bulk_path.read_bytes())[
            "data"
        ]

        with CatalogRepository.open(paths.database_path) as repository:
            context = PullContext(
                repository, ScryfallSource(client), config, bus
            )
            await _pull_sets(context, paths, set_entries)
