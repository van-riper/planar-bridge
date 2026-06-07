from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from sys import platform


@dataclass(frozen=True, kw_only=True)
class DataPaths:
    """Absolute filesystem locations for the data directory.

    Attributes:
        data_directory (Path): Root directory for all stored data.
        json_directory (Path): Holds the MTGJSON bulk and meta files.
        bulk_path (Path): AllPrintings.json inside json_directory.
        metadata_path (Path): Meta.json inside json_directory.
        config_path (Path): config.toml inside data_directory.
        database_path (Path): catalog.db (the SQLite catalog) inside
            data_directory.
    """

    data_directory: Path
    json_directory: Path
    bulk_path: Path
    metadata_path: Path
    config_path: Path
    database_path: Path


def load_paths(environment: Mapping[str, str]) -> DataPaths:
    """Load all absolute data paths from an ``environment`` mapping.

    Pure: uses PLANAR_BRIDGE_DIR when set, otherwise falls back to
    $HOME/.local/share (or %APPDATA% on Windows), then builds the
    sub-paths under it. Does no filesystem work.

    Args:
        environment (Mapping[str, str]): Environment variables to read.

    Returns:
        DataPaths: The immutable set of absolute locations.
    """

    # TODO: rename PLANAR_BRIDGE_DIR to PLANAR_BRIDGE_PATH
    # Assign if PLANAR_BRIDGE_DIR is set
    data_directory = environment.get("PLANAR_BRIDGE_DIR")

    # Fallback to system data folders otherwise
    if data_directory is None:

        match platform:
            case "linux" | "darwin":
                base_path = environment["HOME"] + "/.local/share"
            case "win32":
                base_path = environment["APPDATA"]
            case _:
                raise RuntimeError(f"platform '{platform}' is not supported")

        data_directory = base_path + "/planar-bridge"

    data_directory = Path(data_directory).absolute()
    json_directory = Path(data_directory / ".json")

    return DataPaths(
        data_directory=data_directory,
        json_directory=json_directory,
        bulk_path=Path(json_directory / "AllPrintings.json"),
        metadata_path=Path(json_directory / "Meta.json"),
        config_path=Path(data_directory / "config.toml"),
        database_path=Path(data_directory / "catalog.db"),
    )
    # TODO: rename config.toml to planar-bridge.toml


def ensure_directories_exist(paths: DataPaths) -> None:
    """Create the data and json directories if they do not exist.

    Args:
        paths (DataPaths): The absolute locations to create.
    """

    paths.data_directory.mkdir(parents=True, exist_ok=True)
    paths.json_directory.mkdir(exist_ok=True)
