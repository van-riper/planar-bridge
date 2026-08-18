"""The metadata phase: check the MTGJSON version and refresh Meta.json."""

import json
from collections.abc import Callable

from .. import constants
from ..domain.metadata import (
    MetadataInfo,
    normalize_version,
    version_matches_pin,
)
from ..events import EventBus, MetadataCheckStarted, VersionMismatch
from ..paths import DataPaths
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
    """Warn on a pinned-version drift and refresh Meta.json when missing.

    The bulk files are not re-fetched on MTGJSON's daily rebuild; both Meta.json
    and the bulk database (downloaded by the composition root) are pulled only
    when absent. Detecting genuinely new data, such as a set release, is left to
    a future phase. Only the small Meta.json is fetched here.

    Args:
        paths: The resolved data paths.
        mtgjson_source: The MTGJSON metadata source.
        bus: The event bus for metadata events.
        approve_version: Consulted on a version drift to decide whether
            to proceed; the CLI supplies the prompt.

    Raises:
        RuntimeError: When a network fetch fails.
    """
    bus.emit(MetadataCheckStarted())

    source_info = await mtgjson_source.fetch_metadata()
    if source_info is None:
        raise RuntimeError

    local_info = _read_local_metadata(paths)
    if not version_matches_pin(local_info, constants.MTGJSON_VERSION):
        _resolve_version_drift(bus, source_info.version, approve_version)

    # Fetch Meta.json only when it is missing; an existing copy is kept.
    if paths.metadata_path.exists():
        return

    content = await mtgjson_source.download_bulk("Meta")
    if content is None:
        raise RuntimeError
    paths.metadata_path.write_bytes(content)
