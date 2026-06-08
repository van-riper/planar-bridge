"""Structural ports the pipeline depends on, implemented by the sources.

The pipeline is typed against these Protocols rather than the concrete Scryfall
and MTGJSON sources, so any object with the right shape satisfies it, including
the test doubles. The concrete sources in this package implement them by
explicit subclassing, which lets the type checker confirm each adapter matches
its port.
"""

from typing import Protocol

from ..aliases import Face
from ..domain.metadata import MetadataInfo


class ImageSource(Protocol):
    """Reports a card's image status and downloads its image bytes."""

    async def image_status(self, scryfall_id: str) -> str | None:
        """Report the card's image status, or None when the request fails."""

    async def download_image(
        self, scryfall_id: str, face: Face | None = None
    ) -> bytes | None:
        """Download the card's image bytes, or None when the request fails."""


class MetadataSource(Protocol):
    """Reports build metadata and downloads bulk files."""

    async def fetch_metadata(self) -> MetadataInfo | None:
        """Fetch the remote build metadata, or None when the request fails."""

    async def download_bulk(self, target: str) -> bytes | None:
        """Download and decompress one bulk file, or None on failure."""
