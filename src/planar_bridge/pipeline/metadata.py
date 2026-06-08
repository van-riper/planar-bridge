"""The metadata phase: compare MTGJSON's build and refresh stale bulk files."""

import json
from collections.abc import Callable

from .. import constants
from ..domain.metadata import MetadataInfo, compare_metadata, normalize_version
from ..events import (
    BulkDownloadStarted,
    EventBus,
    MetadataCheckStarted,
    MetadataChecked,
    VersionMismatch,
)
from ..paths import DataPaths
from ..sources.mtgjson import BULK_TARGETS
from ..sources.ports import MetadataSource


def _read_local_metadata(paths: DataPaths) -> MetadataInfo | None:
    """Read the on-disk MTGJSON metadata, or None when bulk data is absent."""

    if not (paths.bulk_path.exists() and paths.metadata_path.exists()):
        return None

    meta = json.loads(paths.metadata_path.read_bytes())["meta"]

    return MetadataInfo(
        date=meta["date"],
        version=normalize_version(meta["version"]),
    )


def _always_approve() -> bool:
    """Approve a version drift without asking (the non-interactive default)."""

    return True


def _resolve_version_drift(
    bus: EventBus,
    source_version: str,
    approve_version: Callable[[], bool],
) -> None:
    """Emit the drift warning and abort unless the approval proceeds.

    The decision to ask the user lives in the approval callback (the CLI
    supplies it), so the pipeline stays free of any console interaction.

    Args:
        bus (EventBus): The event bus the warning is emitted on.
        source_version (str): The newer MTGJSON version reported by the source.
        approve_version (Callable[[], bool]): Returns True to proceed.

    Raises:
        KeyboardInterrupt: When the approval declines to proceed.
    """

    bus.emit(VersionMismatch(source_version=source_version))

    if not approve_version():
        raise KeyboardInterrupt


async def pull_meta(
    paths: DataPaths,
    mtgjson_source: MetadataSource,
    bus: EventBus,
    *,
    approve_version: Callable[[], bool] = _always_approve,
) -> None:
    """Check MTGJSON's metadata and refresh the bulk files when outdated.

    Args:
        paths (DataPaths): The resolved data paths.
        mtgjson_source (MetadataSource): The MTGJSON metadata source.
        bus (EventBus): The event bus for metadata events.
        approve_version (Callable[[], bool]): Consulted on a version drift to
            decide whether to proceed; the CLI supplies the prompt.

    Raises:
        SystemExit: When local data is already up to date.
        RuntimeError: When a network fetch fails.
    """

    bus.emit(MetadataCheckStarted())

    source_info = await mtgjson_source.fetch_metadata()
    if source_info is None:
        raise RuntimeError

    comparison = compare_metadata(
        _read_local_metadata(paths), source_info, constants.MTGJSON_VERS
    )

    bus.emit(
        MetadataChecked(
            is_outdated=comparison.is_outdated,
            version_matches_pinned=comparison.version_matches_pinned,
            source_version=source_info.version,
        )
    )

    if not comparison.is_outdated:
        raise SystemExit

    if not comparison.version_matches_pinned:
        _resolve_version_drift(bus, source_info.version, approve_version)

    bus.emit(BulkDownloadStarted())

    for target in BULK_TARGETS:
        content = await mtgjson_source.download_bulk(target)
        if content is None:
            raise RuntimeError
        (paths.mtgjson_directory / f"{target}.json").write_bytes(content)
