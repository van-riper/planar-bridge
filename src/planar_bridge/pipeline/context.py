"""The run-wide context shared across the pipeline's set and card loops."""

from dataclasses import dataclass

from ..catalog.repository import CatalogRepository
from ..config.loader import AppConfig
from ..events import EventBus
from ..options import RunOptions
from ..sources.ports import ImageSource


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
