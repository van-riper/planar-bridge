"""The download loop: walk the sets and decide, fetch, and record each card."""

import asyncio
from enum import Enum, auto

from .. import constants
from ..aliases import CardData, SetData, SetEntries
from ..domain.decisions import decide_download
from ..events import (
    CardDownloaded,
    CardFailed,
    CardSkipped,
    CardUpgraded,
    RunFinished,
    SetSkipped,
    SetStarted,
)
from ..objects import CardObject, SetObject
from ..paths import DataPaths
from ..sources.ports import ImageSource
from .context import PullContext


class CardOutcome(Enum):
    """The result of handling one card in the pull loop."""

    DOWNLOADED = auto()
    SKIPPED = auto()
    FAILED = auto()


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
