from tomllib import loads
from typing import Any

from const import LANGUAGE_MAP, DEFAULT_CONFIG
from paths import CONFIG_PATH


class Config:

    def __init__(self) -> None:

        config: dict[str, Any] = {}

        if CONFIG_PATH.exists():
            config = loads(CONFIG_PATH.read_text(encoding="UTF-8"))

        config = DEFAULT_CONFIG | config

        for code, name in LANGUAGE_MAP.items():
            if code == config["card_lang"]:
                config.update({"card_lang": name})

        self.pull_reprints: bool = config["pull_reprints"]
        self.card_lang: str = config["card_lang"]
        self.pardoned_sets: list[str] = config["pardoned_sets"]
        self.continuous_sets: list[str] = config["continuous_sets"]
        self.exempt_sets: list[str] = config["exempt_sets"]
        self.exempt_promos: list[str] = config["exempt_promos"]
        self.exempt_types: list[str] = config["exempt_types"]


CONFIG: Config = Config()
