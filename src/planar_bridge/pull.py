import json
import signal
from os import environ

from . import utils
from .aliases import SetEntries
from .config.loader import AppConfig, load_config
from .objects import CardObject, MetaObject, SetObject
from .paths import DataPaths, ensure_directories_exist, load_paths


def remaining_sets(
    set_entries: SetEntries,
    config: AppConfig,
    paths: DataPaths,
) -> None:

    set_list: list[str] = []

    for set_entry in set_entries.values():

        set_obj: SetObject = SetObject(set_entry, config, paths)

        if (
            not set_obj.states_obj.is_all_highres()
            and set_obj.states_obj.states_path.exists()
        ):
            set_list.append(set_obj.set_code)

    sets_str = (", ").join(map(str, set_list))
    utils.status("Remaining sets with low res scans: " + sets_str, 0)


def pull_meta(paths: DataPaths) -> None:

    utils.status("Comparing local & source files...", 0)

    meta_obj: MetaObject = MetaObject(paths)

    if meta_obj.is_outdated():
        utils.status("Downloading bulk files...", 0)
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


def pull_set(set_obj: SetObject, progress: str, config: AppConfig) -> None:

    card_obj: CardObject

    message: tuple[str, ...] = (
        progress,
        set_obj.set_code.ljust(6),
        "AllHighRes:",
        str(set_obj.states_obj.is_all_highres()),
    )

    utils.status((" ").join(map(str, message)), 2)

    signal.signal(signal.SIGINT, set_obj.handle_sigint)

    for card_entry in set_obj.card_entries:

        set_obj.increase_progress()

        card_obj = CardObject(
            card_entry,
            set_obj.states_obj,
            set_obj.set_dir,
            config,
        )

        img_name, source_state = pull_card(card_obj)

        if not img_name:

            if not source_state:
                set_obj.states_obj.write_states()
                raise RuntimeError

            continue

        set_obj.states_obj.take_state(img_name, source_state)

        card_obj.messager(
            progress,
            set_obj.inner_progress(),
            set_obj.set_code,
        )

    set_obj.states_obj.write_states()


def pull_all() -> None:

    set_obj: SetObject
    set_entries: SetEntries

    paths: DataPaths = load_paths(environ)
    ensure_directories_exist(paths)

    config: AppConfig = load_config(paths.config_path)

    pull_meta(paths)

    date: str = json.loads(paths.metadata_path.read_bytes())["meta"]["date"]
    utils.status(f"Loading bulk data ({date})...", 0)

    set_entries = json.loads(paths.bulk_path.read_bytes())["data"]

    set_count: int = 0
    set_total: int = len(set_entries)

    for set_entry in set_entries.values():

        set_count += 1
        set_obj = SetObject(set_entry, config, paths)

        if set_obj.to_omit:
            continue

        progress: str = utils.progress_str(set_count, set_total, False)

        pull_set(set_obj, progress, config)

    utils.status("Finished successfully.", 0)

    remaining_sets(set_entries, config, paths)
