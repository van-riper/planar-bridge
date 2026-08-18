"""Typed events emitted during a download run.

The engine emits these as plain facts about what happened; reporters
subscribe and decide how to present them. Events carry data only: color,
the timestamp, label text, and all other formatting live in the reporter,
never here. This is what lets a console reporter and a future Textual
reporter consume the same stream without the engine knowing either exists.
"""

from dataclasses import dataclass


@dataclass(frozen=True, kw_only=True)
class Event:
    """Base class for every event. Carries no data on its own."""


@dataclass(frozen=True, kw_only=True)
class RunStarted(Event):
    """A download run has begun."""


@dataclass(frozen=True, kw_only=True)
class MetadataCheckStarted(Event):
    """Local and source MTGJSON metadata are about to be compared."""


@dataclass(frozen=True, kw_only=True)
class VersionMismatch(Event):
    """The source MTGJSON version differs from the pinned version.

    Attributes:
        source_version: The newer MTGJSON version reported by the source.
    """

    source_version: str


@dataclass(frozen=True, kw_only=True)
class BulkDownloadStarted(Event):
    """The bulk MTGJSON files are about to be downloaded."""


@dataclass(frozen=True, kw_only=True)
class BulkDataLoaded(Event):
    """The bulk set data has been read into memory.

    Attributes:
        date: The build date of the loaded bulk data.
    """

    date: str


@dataclass(frozen=True, kw_only=True)
class SetStarted(Event):
    """Processing of one set has begun.

    Attributes:
        set_code: The set's MTGJSON code.
        run_count: This set's position in the run (sets handled so far).
        run_total: The total number of sets in the run.
        is_all_high_resolution: True when every recorded scan in the
            set is already high resolution.
    """

    set_code: str
    run_count: int
    run_total: int
    is_all_high_resolution: bool


@dataclass(frozen=True, kw_only=True)
class SetSkipped(Event):
    """A set was omitted from the run.

    Attributes:
        set_code: The omitted set's MTGJSON code.
    """

    set_code: str


@dataclass(frozen=True, kw_only=True)
class CardEvent(Event):
    """Shared payload for the two card-image outcomes that report a line.

    Attributes:
        set_code: The card's set code.
        run_count: The set's position in the run (sets handled so far).
        run_total: The total number of sets in the run.
        set_count: The card's position in its set (cards handled so far).
        set_total: The total number of cards in the set.
        display_label: The card's human-readable label.
    """

    set_code: str
    run_count: int
    run_total: int
    set_count: int
    set_total: int
    display_label: str


@dataclass(frozen=True, kw_only=True)
class CardDownloaded(CardEvent):
    """A new card image was downloaded for the first time."""


@dataclass(frozen=True, kw_only=True)
class CardUpgraded(CardEvent):
    """An existing card image was replaced with a higher-resolution scan."""


@dataclass(frozen=True, kw_only=True)
class CardSkipped(Event):
    """A card needed no download (bad card or already up to date).

    Attributes:
        set_code: The skipped card's set code.
    """

    set_code: str


@dataclass(frozen=True, kw_only=True)
class CardFailed(Event):
    """A card image could not be retrieved after exhausting retries.

    Attributes:
        set_code: The failed card's set code.
    """

    set_code: str


@dataclass(frozen=True, kw_only=True)
class RunFinished(Event):
    """The run completed successfully.

    Attributes:
        low_resolution_set_codes: Set codes that still hold
            at least one low-resolution scan after the run.
    """

    low_resolution_set_codes: tuple[str, ...]


@dataclass(frozen=True, kw_only=True)
class Interrupted(Event):
    """The run received SIGINT (Ctrl-C) and is saving state before exiting."""
