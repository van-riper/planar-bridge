from dataclasses import dataclass
from pathlib import Path
from time import sleep
from typing import Any, Literal, NoReturn
import gzip
import json

from requests import Response, Session

from .config import CONFIG
from . import constants
from . import paths
from . import utils


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


@dataclass
class CardFields:

    uuid: str
    layout: str
    scry_id: str
    message_substr: str
    is_bad: bool
    filename: str
    face: Literal["front", "back"] | None

    def __init__(self, card_dict: dict[str, Any]) -> None:

        self.uuid = card_dict["uuid"]
        self.layout = card_dict["layout"]
        self.scry_id = card_dict["identifiers"]["scryfallId"]
        self.message_substr = self.uuid + " | " + card_dict["name"]
        self.is_bad = self.__init_is_bad(card_dict)
        self.filename = self.__init_filename(card_dict)

        if self.layout in constants.LAYOUT_TWOSIDED:
            if card_dict.get("side") == "a":
                self.face = "front"
            else:
                self.face = "back"
        else:
            self.face = None

    def __init_is_bad(self, card_dict: dict[str, Any]) -> bool:

        promos: list[str] | None = card_dict.get("promoTypes")

        if promos is None:
            promos = []

        promos_crosscheck: set[str] = set(CONFIG.exempt_promos) & set(promos)

        is_bad_conditions: tuple[bool, ...] = (
            bool(card_dict.get("isReprint")) and not CONFIG.pull_reprints,
            card_dict["language"] not in [CONFIG.card_lang, "Phyrexian"],
            card_dict["name"] in ["Checklist", "Double-Faced"],
            bool(card_dict.get("isOnlineOnly")),
            self.layout in constants.LAYOUT_BAD,
            bool(card_dict.get("isFunny")),
            len(promos_crosscheck) > 0,
        )

        return any(is_bad_conditions)

    def __init_filename(self, card_dict: dict[str, Any]) -> str:

        faces_list: list[str] | None = card_dict.get("otherFaceIds")

        if self.layout in constants.LAYOUT_COMBINED and faces_list is not None:
            faces_list.append(self.uuid)
            faces_list.sort()
            return ("_").join(map(str, faces_list))

        return self.uuid


class CardObject:

    def __init__(
        self, card_dict: dict[str, Any], states_obj: StatesObject, set_dir: Path
    ) -> None:

        self.card: CardFields = CardFields(card_dict)

        self.local_state: bool | None = states_obj.get_state(self.card.filename)

        if self.card.layout in constants.LAYOUT_TOKEN:
            set_dir = set_dir / "tokens"

        self.img_path: Path = set_dir / (self.card.filename + ".jpg")
        self.path_exists: bool = self.img_path.exists()

    def parse_source_state(self) -> tuple[bool, bool]:

        url: str

        sleep(constants.TIMEOUT)

        url = f"https://api.scryfall.com/cards/{self.card.scry_id}?format=json"
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

        url = f"https://api.scryfall.com/cards/{self.card.scry_id}?format=image"

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
            self.card.message_substr,
        )

        utils.status((" ").join(message), 5 if self.path_exists else 4)


class SetObject:

    def __init__(self, set_dict: dict[str, Any]) -> None:

        self.set_code: str = set_dict["code"]
        self.set_dir: Path = paths.DATA_DIR / self.set_code
        self.is_partial: bool = bool(set_dict.get("isPartialPreview"))
        self.states_obj: StatesObject = StatesObject(
            self.set_dir / ".states.json"
        )

        to_omit_conditions: tuple[bool, ...] = (
            bool(str(set_dict["type"]) in CONFIG.exempt_types),
            bool(self.set_code in CONFIG.exempt_sets),
            bool(set_dict.get("isForeignOnly")),
            bool(set_dict.get("isOnlineOnly")),
        )

        self.to_omit: bool = any(to_omit_conditions)

        if self.to_omit and self.set_code in CONFIG.pardoned_sets:
            self.to_omit = False

        self.card_entries: list[dict[str, Any]] = [
            *list(set_dict["cards"]),
            *list(set_dict["tokens"]),
        ]

        self.progress: tuple[int, int] = (0, len(self.card_entries))

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

    def __init__(self) -> None:

        self.local: dict[str, str] = {}
        self.source: dict[str, str] = {}

        self.jsons_exist: bool = (
            paths.BULK_PATH.exists() and paths.META_PATH.exists()
        )

        if self.jsons_exist:
            self.local = self.__fix_vers(
                json.loads(paths.META_PATH.read_bytes())["meta"]
            )

        self.source = self.__init_source()

    def __fix_vers(self, to_fix: dict[str, str]) -> dict[str, str]:

        to_fix.update({"version": to_fix["version"].split("+")[0]})
        return to_fix

    def __init_source(self) -> dict[str, str] | NoReturn:

        url: str = "https://mtgjson.com/api/v5/Meta.json"
        meta: Response | None = utils.handle_response(session, url)

        if meta is None:
            raise RuntimeError

        return self.__fix_vers(meta.json()["meta"])

    def pull_bulk(self) -> None | NoReturn:

        for target in ("AllPrintings", "Meta"):

            url: str = f"https://mtgjson.com/api/v5/{target}.json.gz"
            bulk_json: Response | None = utils.handle_response(session, url)

            if bulk_json is None:
                raise RuntimeError

            fob: Path = paths.JSON_DIR / f"{target}.json"
            fob.write_bytes(gzip.decompress(bulk_json.content))

    def is_outdated(self) -> bool | NoReturn:

        if not self.jsons_exist and not self.local:
            return True

        same_date: bool = self.local["date"] == self.source["date"]

        if same_date:
            raise SystemExit

        if self.local["version"] != constants.MTGJSON_VERS:

            message: tuple[str, ...] = (
                "MTGJSON has been updated to v",
                self.source["version"] + "\n",
                constants.VERS_WARNING,
            )

            utils.status(("").join(message), 1)
            proceed: str = input("Do you want to proceed? [y/N]: ")

            if not utils.boolify_str(proceed, False):
                raise KeyboardInterrupt

        return not same_date
