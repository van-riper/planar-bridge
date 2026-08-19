"""Pure download decisions derived from Scryfall image state.

Every function here is pure: it reads Scryfall's reported image status and the
locally recorded state, then returns whether a download is needed. Nothing in
this module performs I/O, sleeps, or touches the network.
"""

from dataclasses import dataclass

# Scryfall image statuses that carry no usable scan, so nothing is downloaded.
PLACEHOLDER_STATUSES = frozenset({"placeholder", "missing"})

# The single Scryfall status that denotes a high-resolution scan.
HIGH_RESOLUTION_STATUS = "highres_scan"


@dataclass(frozen=True, kw_only=True)
class DownloadDecision:
    """Immutable verdict for one card's image.

    Attributes:
        should_download: True when the image must be fetched, whether as a
            first download or a resolution upgrade.
        source_is_high_resolution: True when Scryfall reports the source
            scan as high-resolution. Meaningful only when a usable scan
            exists; it is False for placeholder and missing statuses.
    """

    should_download: bool
    source_is_high_resolution: bool


def decide_download(
    image_status: str,
    *,
    local_is_high_resolution: bool | None,
    image_exists: bool,
) -> DownloadDecision:
    """Decide whether a card's image needs downloading.

    A download is needed unless the source carries no usable scan, or the
    source resolution already matches the stored resolution and the file is
    present. A high-resolution source over a stored low-resolution scan is the
    resolution-upgrade case and downloads.

    Args:
        image_status: Scryfall's image_status for the card.
        local_is_high_resolution: The recorded resolution of the stored
            scan, or None when no scan has been recorded.
        image_exists: True when the image file is present on disk.

    Returns:
        The immutable verdict for the card.
    """
    if image_status in PLACEHOLDER_STATUSES:
        return DownloadDecision(
            should_download=False, source_is_high_resolution=False
        )

    source_is_high_resolution = image_status == HIGH_RESOLUTION_STATUS
    already_stored = (
        source_is_high_resolution == local_is_high_resolution and image_exists
    )

    return DownloadDecision(
        should_download=not already_stored,
        source_is_high_resolution=source_is_high_resolution,
    )
