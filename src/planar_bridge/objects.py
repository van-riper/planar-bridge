import gzip
import json
from pathlib import Path
from time import sleep
from typing import NoReturn

from requests import Response, Session

from . import constants, utils
from .aliases import CardData, SetData
from .config.loader import AppConfig
from .domain import layouts
from .domain.card_model import CardFields, build_card_fields
from .domain.metadata import (
    MetadataComparison,
    MetadataInfo,
    compare_metadata,
    normalize_version,
)
from .domain.set_model import SetRecord, build_set_record
from .paths import DataPaths

session = Session()


class StatesObject:

    def __init__(self, states_path: Path) -> None:

        self.states_path: Path = states_path
        self.states_dict: dict[str, bool] = self.read_states()

    def read_states(self) -> dict[str, bool]:

        states_dict: dict[str, bool] = {}

        if self.states_path.exists():
            states_dict = json.loads(self.states_path.read_bytes())

        return states_dict

    def write_states(self) -> None:

        if self.states_dict == self.read_states() or not self.states_dict:
            return

        self.states_path.write_text(
            json.dumps(self.states_dict, sort_keys=True),
            encoding="UTF-8",
        )

    def get_state(self, name: str) -> bool | None:

        return self.states_dict.get(name)

    def take_state(self, name: str, res: bool) -> None:

        self.states_dict[name] = res

    def is_all_highres(self) -> bool:

        return all(self.states_dict.values())


class CardObject:

    def __init__(
        self,
        card_dict: CardData,
        states_obj: StatesObject,
        set_directory: Path,
        config: AppConfig,
    ) -> None:

        self.card: CardFields = build_card_fields(card_dict, config)

        self.local_state: bool | None = states_obj.get_state(self.card.filename)

        if self.card.layout in layouts.LAYOUT_TOKEN:
            set_directory = set_directory / "tokens"

        self.img_path: Path = set_directory / (self.card.filename + ".jpg")
        self.path_exists: bool = self.img_path.exists()

    def parse_source_state(self) -> tuple[bool, bool]:

        url: str

        sleep(constants.TIMEOUT)

        url = f"https://api.scryfall.com/cards/{self.card.scryfall_id}?format=json"
        source: Response | None = utils.handle_response(session, url)

        if source is None:
            return False, False

        source_res: str = source.json()["image_status"]

        if source_res in ["placeholder", "missing"]:
            return False, True

        source_state: bool = source_res == "highres_scan"

        if source_state == self.local_state and self.path_exists:
            return False, True

        return True, source_state

    def download(self) -> bool:

        url: str

        self.img_path.parent.mkdir(exist_ok=True, parents=True)

        sleep(constants.TIMEOUT)

        url = f"https://api.scryfall.com/cards/{self.card.scryfall_id}?format=image"

        if self.card.face is not None:
            url += "&face=" + self.card.face

        img: Response | None = utils.handle_response(session, url)

        if img is None:
            return False

        self.img_path.write_bytes(img.content)

        return True

    def messager(self, progress: str, set_progress: str, set_code: str) -> None:

        message: tuple[str, ...] = (
            progress,
            set_code.ljust(6),
            set_progress,
            self.card.display_label,
        )

        utils.status((" ").join(message), 5 if self.path_exists else 4)


class SetObject:

    def __init__(
        self,
        set_dict: SetData,
        config: AppConfig,
        paths: DataPaths,
    ) -> None:

        self.record: SetRecord = build_set_record(set_dict, config)
        self.set_directory: Path = paths.data_directory / self.record.set_code
        self.states_obj: StatesObject = StatesObject(
            self.set_directory / ".states.json"
        )
        self.progress: tuple[int, int] = (0, len(self.record.card_entries))

    def increase_progress(self) -> None:

        self.progress = (self.progress[0] + 1, self.progress[1])

    def inner_progress(self) -> str:

        return utils.progress_str(*self.progress, True)

    # pylint: disable=unused-argument
    def handle_sigint(self, signum, frame) -> NoReturn:

        utils.status("SIGINT recieved (Ctrl-C), saving & exiting...", 6)
        self.states_obj.write_states()
        raise KeyboardInterrupt


class MetaObject:

    def __init__(self, paths: DataPaths) -> None:

        self.paths: DataPaths = paths
        self.local: MetadataInfo | None = None

        self.jsons_exist: bool = (
            paths.bulk_path.exists() and paths.metadata_path.exists()
        )

        if self.jsons_exist:
            local_meta = json.loads(paths.metadata_path.read_bytes())["meta"]
            self.local = self.__parse_info(local_meta)

        self.source: MetadataInfo = self.__fetch_source()

    def __parse_info(self, meta: dict[str, str]) -> MetadataInfo:

        return MetadataInfo(
            date=meta["date"],
            version=normalize_version(meta["version"]),
        )

    def __fetch_source(self) -> MetadataInfo | NoReturn:

        url: str = "https://mtgjson.com/api/v5/Meta.json"
        meta: Response | None = utils.handle_response(session, url)

        if meta is None:
            raise RuntimeError

        return self.__parse_info(meta.json()["meta"])

    def pull_bulk(self) -> None | NoReturn:

        for target in ("AllPrintings", "Meta"):

            url: str = f"https://mtgjson.com/api/v5/{target}.json.gz"
            bulk_json: Response | None = utils.handle_response(session, url)

            if bulk_json is None:
                raise RuntimeError

            fob: Path = self.paths.json_directory / f"{target}.json"
            fob.write_bytes(gzip.decompress(bulk_json.content))

    def is_outdated(self) -> bool | NoReturn:

        comparison: MetadataComparison = compare_metadata(
            self.local, self.source, constants.MTGJSON_VERS
        )

        if not comparison.is_outdated:
            raise SystemExit

        if not comparison.version_matches_pinned:

            message: tuple[str, ...] = (
                "MTGJSON has been updated to v",
                self.source.version + "\n",
                constants.VERS_WARNING,
            )

            utils.status(("").join(message), 1)
            proceed: str = input("Do you want to proceed? [y/N]: ")

            if not utils.boolify_str(proceed, False):
                raise KeyboardInterrupt

        return comparison.is_outdated
