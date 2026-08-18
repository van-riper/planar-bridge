"""The composition root: build the shared engine and run the whole pull."""

import json
from collections.abc import Callable
from os import environ

import httpx

from .. import constants
from ..catalog.repository import CatalogRepository
from ..config.loader import AppConfig, load_config
from ..engine.client import AsyncHttpClient
from ..engine.limiter import RateLimiter
from ..events import BulkDataLoaded, BulkDownloadStarted, EventBus
from ..options import RunOptions
from ..paths import DataPaths, ensure_directories_exist, load_paths
from ..sources.bulk import BulkReader
from ..sources.mtgjson import MtgjsonSource
from ..sources.ports import MetadataSource
from ..sources.scryfall import ScryfallSource
from .context import PullContext
from .download import _pull_sets
from .metadata import _always_approve, pull_meta

REQUEST_TIMEOUT_SECONDS = 30.0


async def _download_bulk_database(
    paths: DataPaths,
    mtgjson_source: MetadataSource,
    bus: EventBus,
) -> None:
    """Download the MTGJSON bulk database when it is missing.

    The large AllPrintings.sqlite is fetched only when no copy is present, so a
    run reuses the bulk already on disk rather than re-downloading it.

    Args:
        paths (DataPaths): The resolved data paths.
        mtgjson_source (MetadataSource): The MTGJSON source.
        bus (EventBus): The event bus the download banner is emitted on.

    Raises:
        RuntimeError: When the download fails.
    """
    if paths.bulk_path.exists():
        return

    bus.emit(BulkDownloadStarted())

    content = await mtgjson_source.download_bulk("AllPrintings")
    if content is None:
        raise RuntimeError

    paths.bulk_path.write_bytes(content)


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

        mtgjson_source = MtgjsonSource(client)

        await pull_meta(
            paths,
            mtgjson_source,
            bus,
            approve_version=approve_version,
        )

        await _download_bulk_database(paths, mtgjson_source, bus)

        date: str = json.loads(paths.metadata_path.read_bytes())["meta"]["date"]
        bus.emit(BulkDataLoaded(date=date))

        with (
            BulkReader.open(paths.bulk_path) as bulk,
            CatalogRepository.open(paths.database_path) as repository,
        ):
            context = PullContext(
                repository, ScryfallSource(client), config, bus, options
            )
            await _pull_sets(context, paths, bulk)
