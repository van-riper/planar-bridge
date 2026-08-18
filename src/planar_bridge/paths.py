from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from sys import platform


@dataclass(frozen=True, kw_only=True)
class DataPaths:
    """Absolute filesystem locations for the data directory.

    Attributes:
        data_directory (Path): Root directory for all stored data.
        mtgjson_directory (Path): Holds the MTGJSON bulk and meta files.
        bulk_path (Path): AllPrintings.sqlite inside mtgjson_directory.
        metadata_path (Path): Meta.json inside mtgjson_directory.
        config_path (Path): config.toml inside data_directory.
        database_path (Path): catalog.sqlite (the SQLite catalog) inside
            data_directory.
    """

    data_directory: Path
    mtgjson_directory: Path
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
        environment: Environment variables to read.

    Returns:
        The immutable set of absolute locations.
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
    mtgjson_directory = Path(data_directory / ".mtgjson")

    return DataPaths(
        data_directory=data_directory,
        mtgjson_directory=mtgjson_directory,
        bulk_path=Path(mtgjson_directory / "AllPrintings.sqlite"),
        metadata_path=Path(mtgjson_directory / "Meta.json"),
        config_path=Path(data_directory / "config.toml"),
        database_path=Path(data_directory / "catalog.sqlite"),
    )
    # TODO: rename config.toml to planar-bridge.toml


def ensure_directories_exist(paths: DataPaths) -> None:
    """Create the data and mtgjson directories if they do not exist.

    Args:
        paths: The absolute locations to create.
    """
    paths.data_directory.mkdir(parents=True, exist_ok=True)
    paths.mtgjson_directory.mkdir(exist_ok=True)
