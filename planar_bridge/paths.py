from pathlib import Path
from os import getenv, name as os_name


def default_path() -> Path:

    path_env: str | None = getenv("PLANAR_BRIDGE_DIR")
    is_posix: bool = os_name == "posix"

    if path_env is None:

        path_env = getenv(
            "XDG_DATA_HOME" if is_posix else "AppData",
            "~/.local/share" if is_posix else "%UserProfile%/AppData",
        )

        path_env += "/planar-bridge"

    path_obj: Path = Path(path_env).resolve()

    if not path_obj.exists():
        raise FileNotFoundError(path_obj)

    return path_obj


DATA_DIR: Path = default_path()

JSON_DIR: Path = DATA_DIR / ".json"
JSON_DIR.mkdir(exist_ok=True)

BULK_PATH: Path = JSON_DIR / "AllPrintings.json"
META_PATH: Path = JSON_DIR / "Meta.json"

CONFIG_PATH: Path = DATA_DIR / "config.toml"
