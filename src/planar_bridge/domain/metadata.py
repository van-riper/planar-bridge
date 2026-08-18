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


def normalize_version(version: str) -> str:
    """Strip any build suffix from a version string.

    Args:
        version: A raw MTGJSON version string, possibly carrying a
            ``+<build>`` suffix.

    Returns:
        The version with any build suffix removed.
    """
    return version.split("+", maxsplit=1)[0]


def version_matches_pin(
    local: MetadataInfo | None,
    pinned_version: str,
) -> bool:
    """Report whether the local data matches the pinned MTGJSON version.

    The bulk download is no longer gated on MTGJSON's daily build date (which
    changes mostly for prices, outside this project's scope); the only version
    concern left is whether the locally stored data was built with the version
    the code is validated against. Vacuously true when no local data is present.

    Args:
        local: The local metadata, or None when no local data is present.
        pinned_version: The version the code is pinned to. Assumed
            already normalized.

    Returns:
        True when there is no local data, or the local version equals the
        pinned version.
    """
    return local is None or local.version == pinned_version
