"""The async pull pipeline: metadata check, then per-set card downloads.

``pull_all`` builds one shared async engine for the run, checks MTGJSON's
metadata, then walks every set. Sets are processed one at a time; within a set
its cards download concurrently under a bounded semaphore, while the shared rate
limiter keeps total throughput under Scryfall's ceiling. Progress is persisted
per card to the catalog, so a killed run resumes from confirmed state.
"""

import asyncio
import json
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum, auto
from os import environ

import httpx

from . import constants
from .aliases import CardData, SetData, SetEntries
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
    CardFailed,
    CardSkipped,
    CardUpgraded,
    EventBus,
    MetadataCheckStarted,
    MetadataChecked,
    RunFinished,
    SetSkipped,
    SetStarted,
    VersionMismatch,
)
from .objects import CardObject, SetObject
from .options import RunOptions
from .paths import DataPaths, ensure_directories_exist, load_paths
from .sources.mtgjson import BULK_TARGETS, MtgjsonSource
from .sources.ports import ImageSource, MetadataSource
from .sources.scryfall import ScryfallSource

REQUEST_TIMEOUT_SECONDS = 30.0


class CardOutcome(Enum):
    """The result of handling one card in the pull loop."""

    DOWNLOADED = auto()
    SKIPPED = auto()
    FAILED = auto()


@dataclass(frozen=True)
class PullContext:
    """The run-wide dependencies threaded through the set and card loops.

    Attributes:
        repository (CatalogRepository): The catalog of stored card state.
        scryfall_source (ImageSource): The card-image source.
        config (AppConfig): Resolved filtering configuration.
        bus (EventBus): The event bus for set and card events.
        options (RunOptions): The per-run command-line switches.
    """

    repository: CatalogRepository
    scryfall_source: ImageSource
    config: AppConfig
    bus: EventBus
    options: RunOptions


def _read_local_metadata(paths: DataPaths) -> MetadataInfo | None:
    """Read the on-disk MTGJSON metadata, or None when bulk data is absent."""

    if not (paths.bulk_path.exists() and paths.metadata_path.exists()):
        return None

    meta = json.loads(paths.metadata_path.read_bytes())["meta"]

    return MetadataInfo(
        date=meta["date"],
        version=normalize_version(meta["version"]),
    )


def _always_approve() -> bool:
    """Approve a version drift without asking (the non-interactive default)."""

    return True


def _resolve_version_drift(
    bus: EventBus,
    source_version: str,
    approve_version: Callable[[], bool],
) -> None:
    """Emit the drift warning and abort unless the approval proceeds.

    The decision to ask the user lives in the approval callback (the CLI
    supplies it), so the pipeline stays free of any console interaction.

    Args:
        bus (EventBus): The event bus the warning is emitted on.
        source_version (str): The newer MTGJSON version reported by the source.
        approve_version (Callable[[], bool]): Returns True to proceed.

    Raises:
        KeyboardInterrupt: When the approval declines to proceed.
    """

    bus.emit(VersionMismatch(source_version=source_version))

    if not approve_version():
        raise KeyboardInterrupt


async def pull_meta(
    paths: DataPaths,
    mtgjson_source: MetadataSource,
    bus: EventBus,
    *,
    approve_version: Callable[[], bool] = _always_approve,
) -> None:
    """Check MTGJSON's metadata and refresh the bulk files when outdated.

    Args:
        paths (DataPaths): The resolved data paths.
        mtgjson_source (MetadataSource): The MTGJSON metadata source.
        bus (EventBus): The event bus for metadata events.
        approve_version (Callable[[], bool]): Consulted on a version drift to
            decide whether to proceed; the CLI supplies the prompt.

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
        _resolve_version_drift(bus, source_info.version, approve_version)

    bus.emit(BulkDownloadStarted())

    for target in BULK_TARGETS:
        content = await mtgjson_source.download_bulk(target)
        if content is None:
            raise RuntimeError
        (paths.json_directory / f"{target}.json").write_bytes(content)


async def pull_card(
    card_obj: CardObject,
    scryfall_source: ImageSource,
    *,
    dry_run: bool = False,
) -> tuple[CardOutcome, bool]:
    """Download one card's image when needed, writing it to disk.

    Args:
        card_obj (CardObject): The card's facts, paths, and stored state.
        scryfall_source (ImageSource): The card-image source.
        dry_run (bool): When True, stop once a download is decided on; report
            DOWNLOADED without fetching the bytes or writing the file.

    Returns:
        tuple[CardOutcome, bool]: The outcome, plus whether the stored scan is
        high-resolution (meaningful only when the outcome is DOWNLOADED). A
        network failure yields FAILED rather than raising, so one bad card does
        not stop the run.
    """

    if card_obj.card.is_bad:
        return CardOutcome.SKIPPED, False

    if card_obj.local_state and card_obj.path_exists:
        return CardOutcome.SKIPPED, False

    image_status = await scryfall_source.image_status(card_obj.card.scryfall_id)
    if image_status is None:
        return CardOutcome.FAILED, False

    decision = decide_download(
        image_status, card_obj.local_state, card_obj.path_exists
    )

    if not decision.should_download:
        return CardOutcome.SKIPPED, False

    if not dry_run:
        content = await scryfall_source.download_image(
            card_obj.card.scryfall_id, card_obj.card.face
        )
        if content is None:
            return CardOutcome.FAILED, False

        card_obj.img_path.parent.mkdir(parents=True, exist_ok=True)
        card_obj.img_path.write_bytes(content)

    return CardOutcome.DOWNLOADED, decision.source_is_high_resolution


async def pull_set(
    set_obj: SetObject,
    context: PullContext,
    run_position: tuple[int, int],
) -> None:
    """Download every card in a set concurrently under a bounded semaphore.

    Args:
        set_obj (SetObject): The set's record, directory, and progress.
        context (PullContext): The run-wide dependencies.
        run_position (tuple[int, int]): This set's (count, total) position in
            the run; the reporter formats it into the run-level progress label.
    """

    run_count, run_total = run_position

    context.bus.emit(
        SetStarted(
            set_code=set_obj.record.set_code,
            run_count=run_count,
            run_total=run_total,
            is_all_high_resolution=context.repository.is_set_high_resolution(
                set_obj.record.set_code
            ),
        )
    )

    semaphore = asyncio.Semaphore(constants.MAX_CONCURRENT_DOWNLOADS)

    async def handle(card_entry: CardData) -> None:
        async with semaphore:
            await _handle_card(set_obj, context, run_position, card_entry)

    await asyncio.gather(
        *(handle(entry) for entry in set_obj.record.card_entries)
    )


async def _handle_card(
    set_obj: SetObject,
    context: PullContext,
    run_position: tuple[int, int],
    card_entry: CardData,
) -> None:
    """Download one card and record and report its outcome."""

    set_obj.increase_progress()

    card_obj = CardObject(
        card_entry, context.repository, set_obj.set_directory, context.config
    )

    outcome, source_state = await pull_card(
        card_obj, context.scryfall_source, dry_run=context.options.dry_run
    )
    set_code = set_obj.record.set_code

    if outcome is CardOutcome.SKIPPED:
        context.bus.emit(CardSkipped(set_code=set_code))
        return

    if outcome is CardOutcome.FAILED:
        context.bus.emit(CardFailed(set_code=set_code))
        return

    if not context.options.dry_run:
        context.repository.upsert_card(card_obj.to_row(source_state))

    run_count, run_total = run_position
    set_count, set_total = set_obj.progress

    card_event = CardUpgraded if card_obj.path_exists else CardDownloaded
    context.bus.emit(
        card_event(
            set_code=set_code,
            run_count=run_count,
            run_total=run_total,
            set_count=set_count,
            set_total=set_total,
            display_label=card_obj.card.display_label,
        )
    )


def _selected_entries(
    set_entries: SetEntries,
    only_sets: frozenset[str],
) -> list[SetData]:
    """Return the set entries to process, restricted by ``--set`` when given.

    Args:
        set_entries (SetEntries): Every set keyed by its code.
        only_sets (frozenset[str]): The requested set codes; an empty set
            means no restriction.

    Returns:
        list[SetData]: The entries to walk, in their original order.
    """

    if not only_sets:
        return list(set_entries.values())

    return [entry for code, entry in set_entries.items() if code in only_sets]


async def _pull_sets(
    context: PullContext,
    paths: DataPaths,
    set_entries: SetEntries,
) -> None:
    """Walk every requested set in order, downloading the ones not omitted."""

    selected = _selected_entries(set_entries, context.options.only_sets)
    set_total = len(selected)

    for set_count, set_entry in enumerate(selected, 1):

        set_obj = SetObject(set_entry, context.config, paths, context.bus)

        if set_obj.record.is_omitted:
            context.bus.emit(SetSkipped(set_code=set_obj.record.set_code))
            continue

        await pull_set(set_obj, context, (set_count, set_total))

    context.bus.emit(
        RunFinished(
            low_resolution_set_codes=context.repository.low_resolution_sets()
        )
    )


async def pull_all(
    bus: EventBus,
    options: RunOptions = RunOptions(),
    approve_version: Callable[[], bool] = _always_approve,
) -> None:
    """Run the whole pull: metadata check, then every set's downloads.

    Args:
        bus (EventBus): The event bus, already wired to its reporters by the
            caller, that the run emits progress and outcome events on.
        options (RunOptions): The per-run switches from the command line.
        approve_version (Callable[[], bool]): Consulted on a version drift; the
            CLI builds it from ``--assume-yes`` and the interactive prompt.
    """

    paths: DataPaths = load_paths(environ)
    ensure_directories_exist(paths)

    config: AppConfig = load_config(paths.config_path, options.language)

    async with httpx.AsyncClient(
        timeout=REQUEST_TIMEOUT_SECONDS,
        headers=constants.HTTP_HEADERS,
    ) as http_client:

        client = AsyncHttpClient(
            http_client, RateLimiter(constants.MAX_REQUESTS_PER_SECOND)
        )

        await pull_meta(
            paths,
            MtgjsonSource(client),
            bus,
            approve_version=approve_version,
        )

        date: str = json.loads(paths.metadata_path.read_bytes())["meta"]["date"]
        bus.emit(BulkDataLoaded(date=date))

        set_entries: SetEntries = json.loads(paths.bulk_path.read_bytes())[
            "data"
        ]

        with CatalogRepository.open(paths.database_path) as repository:
            context = PullContext(
                repository, ScryfallSource(client), config, bus, options
            )
            await _pull_sets(context, paths, set_entries)
