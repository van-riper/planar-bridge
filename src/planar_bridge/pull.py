import json
import signal
from os import environ

from . import utils
from .aliases import SetEntries
from .config.loader import AppConfig, load_config
from .events import (
    BulkDataLoaded,
    BulkDownloadStarted,
    CardDownloaded,
    CardUpgraded,
    EventBus,
    MetadataCheckStarted,
    RunFinished,
    SetStarted,
)
from .objects import CardObject, MetaObject, SetObject
from .paths import DataPaths, ensure_directories_exist, load_paths
from .reporters.console import ConsoleReporter


def remaining_sets(
    set_entries: SetEntries,
    config: AppConfig,
    paths: DataPaths,
    bus: EventBus,
) -> tuple[str, ...]:

    set_list: list[str] = []

    for set_entry in set_entries.values():

        set_obj: SetObject = SetObject(set_entry, config, paths, bus)

        if (
            not set_obj.states_obj.is_all_highres()
            and set_obj.states_obj.states_path.exists()
        ):
            set_list.append(set_obj.record.set_code)

    return tuple(set_list)


def pull_meta(paths: DataPaths, bus: EventBus) -> None:

    bus.emit(MetadataCheckStarted())

    meta_obj: MetaObject = MetaObject(paths, bus)

    if meta_obj.is_outdated():
        bus.emit(BulkDownloadStarted())
        meta_obj.pull_bulk()


def pull_card(card_obj: CardObject) -> tuple[str, bool]:

    if card_obj.card.is_bad:
        return "", True

    if card_obj.local_state and card_obj.path_exists:
        return "", True

    control_bool, source_state = card_obj.parse_source_state()

    if not control_bool:

        if not source_state:
            return "", False

        return "", True

    if not card_obj.download():
        return "", False

    return card_obj.card.filename, source_state


def pull_set(
    set_obj: SetObject,
    progress: str,
    config: AppConfig,
    bus: EventBus,
) -> None:

    card_obj: CardObject

    bus.emit(
        SetStarted(
            set_code=set_obj.record.set_code,
            progress=progress,
            is_all_high_resolution=set_obj.states_obj.is_all_highres(),
        )
    )

    signal.signal(signal.SIGINT, set_obj.handle_sigint)

    for card_entry in set_obj.record.card_entries:

        set_obj.increase_progress()

        card_obj = CardObject(
            card_entry,
            set_obj.states_obj,
            set_obj.set_directory,
            config,
        )

        img_name, source_state = pull_card(card_obj)

        if not img_name:

            if not source_state:
                set_obj.states_obj.write_states()
                raise RuntimeError

            continue

        set_obj.states_obj.take_state(img_name, source_state)

        card_event = CardUpgraded if card_obj.path_exists else CardDownloaded

        bus.emit(
            card_event(
                set_code=set_obj.record.set_code,
                run_progress=progress,
                set_progress=set_obj.inner_progress(),
                display_label=card_obj.card.display_label,
            )
        )

    set_obj.states_obj.write_states()


def pull_all() -> None:

    set_obj: SetObject
    set_entries: SetEntries

    bus: EventBus = EventBus()
    bus.subscribe(ConsoleReporter().handle)

    paths: DataPaths = load_paths(environ)
    ensure_directories_exist(paths)

    config: AppConfig = load_config(paths.config_path)

    pull_meta(paths, bus)

    date: str = json.loads(paths.metadata_path.read_bytes())["meta"]["date"]
    bus.emit(BulkDataLoaded(date=date))

    set_entries = json.loads(paths.bulk_path.read_bytes())["data"]

    set_count: int = 0
    set_total: int = len(set_entries)

    for set_entry in set_entries.values():

        set_count += 1
        set_obj = SetObject(set_entry, config, paths, bus)

        if set_obj.record.is_omitted:
            continue

        progress: str = utils.progress_str(set_count, set_total, False)

        pull_set(set_obj, progress, config, bus)

    low_resolution_set_codes: tuple[str, ...] = remaining_sets(
        set_entries, config, paths, bus
    )

    bus.emit(RunFinished(low_resolution_set_codes=low_resolution_set_codes))
