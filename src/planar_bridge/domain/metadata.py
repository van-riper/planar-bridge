"""Pure metadata facts derived from MTGJSON Meta entries.

Every function here is pure: it reads metadata values and returns a derived
result. Nothing in this module performs I/O, prompts the user, or exits.
"""

from dataclasses import dataclass


@dataclass(frozen=True, kw_only=True)
class MetadataInfo:
    """One MTGJSON metadata entry.

    Attributes:
        date (str): The build date of the metadata.
        version (str): The MTGJSON version, with any build suffix removed.
    """

    date: str
    version: str


@dataclass(frozen=True, kw_only=True)
class MetadataComparison:
    """Immutable verdict from comparing local and source metadata.

    Attributes:
        has_local_data (bool): True when local metadata is present.
        is_outdated (bool): True when there is no local data or the local date
            differs from the source date (i.e. a download is needed). The
            "up to date" case is simply its negation.
        version_matches_pinned (bool): True when there is no local data, or the
            local version equals the pinned version.
    """

    has_local_data: bool
    is_outdated: bool
    version_matches_pinned: bool


def normalize_version(version: str) -> str:
    """Strip any build suffix from a version string.

    Args:
        version (str): A raw MTGJSON version string, possibly carrying a
            ``+<build>`` suffix.

    Returns:
        str: The version with any build suffix removed.
    """

    return version.split("+")[0]


def compare_metadata(
    local: MetadataInfo | None,
    source: MetadataInfo,
    pinned_version: str,
) -> MetadataComparison:
    """Compare local metadata against source and the pinned version.

    Args:
        local (MetadataInfo | None): The local metadata, or None when no local
            data is present.
        source (MetadataInfo): The source metadata.
        pinned_version (str): The version the code is pinned to. Assumed
            already normalized.

    Returns:
        MetadataComparison: The immutable verdict for the comparison.
    """

    has_local_data = local is not None

    is_outdated = local is None or local.date != source.date

    version_matches_pinned = local is None or local.version == pinned_version

    return MetadataComparison(
        has_local_data=has_local_data,
        is_outdated=is_outdated,
        version_matches_pinned=version_matches_pinned,
    )
