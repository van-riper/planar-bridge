"""Unit tests for path resolution.

Written before the implementation (TDD): these assertions define the
contract for DataPaths, load_paths and ensure_directories_exist.
"""

from pathlib import Path

import pytest

from planar_bridge.paths import ensure_directories_exist, load_paths


def test_planar_bridge_dir_takes_precedence() -> None:
    """PLANAR_BRIDGE_DIR wins over XDG_DATA_HOME."""
    paths = load_paths({
        "PLANAR_BRIDGE_DIR": "/data/pb",
        "XDG_DATA_HOME": "/xdg",
    })
    assert paths.data_directory == Path("/data/pb")


@pytest.mark.parametrize(
    ("platform_name", "environment", "expected"),
    [
        (
            "linux",
            {"HOME": "/home/u"},
            Path("/home/u/.local/share/planar-bridge"),
        ),
        (
            "darwin",
            {"HOME": "/Users/u"},
            Path("/Users/u/.local/share/planar-bridge"),
        ),
        (
            "win32",
            {"APPDATA": "/appdata"},
            Path("/appdata/planar-bridge"),
        ),
    ],
)
def test_platform_fallback_paths(
    monkeypatch: pytest.MonkeyPatch,
    platform_name: str,
    environment: dict[str, str],
    expected: Path,
) -> None:
    """On linux/macOS the base is $HOME/.local/share; on Windows %APPDATA%."""
    monkeypatch.setattr("planar_bridge.paths.platform", platform_name)
    paths = load_paths(environment)
    assert paths.data_directory == expected


def test_unsupported_platform_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An unrecognized platform raises RuntimeError."""
    monkeypatch.setattr("planar_bridge.paths.platform", "freebsd")
    with pytest.raises(RuntimeError):
        load_paths({})


def test_derived_paths_sit_under_data_directory() -> None:
    """The mtgjson, bulk, metadata and config paths derive from the data dir."""
    paths = load_paths({"PLANAR_BRIDGE_DIR": "/data/pb"})
    assert paths.mtgjson_directory == Path("/data/pb/.mtgjson")
    assert paths.bulk_path == Path("/data/pb/.mtgjson/AllPrintings.sqlite")
    assert paths.metadata_path == Path("/data/pb/.mtgjson/Meta.json")
    assert paths.config_path == Path("/data/pb/config.toml")


def test_database_path_sits_under_data_directory() -> None:
    """The catalog database is catalog.sqlite in the data directory."""
    paths = load_paths({"PLANAR_BRIDGE_DIR": "/data/pb"})
    assert paths.database_path == Path("/data/pb/catalog.sqlite")


def test_load_paths_does_no_filesystem_work(tmp_path: Path) -> None:
    """load_paths neither raises on a missing dir nor creates it."""
    missing = tmp_path / "absent"
    paths = load_paths({"PLANAR_BRIDGE_DIR": str(missing)})
    assert paths.data_directory == missing
    assert not missing.exists()


def test_ensure_directories_exist_creates_data_and_mtgjson(
    tmp_path: Path,
) -> None:
    """ensure_directories_exist creates the data and mtgjson directories."""
    paths = load_paths({"PLANAR_BRIDGE_DIR": str(tmp_path / "pb")})
    ensure_directories_exist(paths)
    assert paths.data_directory.is_dir()
    assert paths.mtgjson_directory.is_dir()
