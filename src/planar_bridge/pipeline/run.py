"""The composition root: build the shared engine and run the whole pull."""

import json
from collections.abc import Callable
from os import environ

import httpx

from .. import constants
from ..aliases import SetEntries
from ..catalog.repository import CatalogRepository
from ..config.loader import AppConfig, load_config
from ..engine.client import AsyncHttpClient
from ..engine.limiter import RateLimiter
from ..events import BulkDataLoaded, EventBus
from ..options import RunOptions
from ..paths import DataPaths, ensure_directories_exist, load_paths
from ..sources.mtgjson import MtgjsonSource
from ..sources.scryfall import ScryfallSource
from .context import PullContext
from .download import _pull_sets
from .metadata import _always_approve, pull_meta

REQUEST_TIMEOUT_SECONDS = 30.0


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
