"""Scryfall card image access built on the async HTTP client.

The source knows Scryfall's URL shapes and response format. It reports a card's
image status and downloads its image bytes, leaving the download decision to
``domain.decisions`` and the file write to the pipeline. It replaces the
network halves of the old ``CardObject.parse_source_state`` and ``download``.
"""

from ..aliases import Face
from ..engine.client import AsyncHttpClient
from .ports import ImageSource

SCRYFALL_API_CARD_URL = "https://api.scryfall.com/cards/"


class ScryfallSource(ImageSource):
    """Fetches card image status and image bytes from Scryfall."""

    def __init__(self, client: AsyncHttpClient) -> None:
        """Build the source over an async HTTP client.

        Args:
            client (AsyncHttpClient): The rate-limited client used for every
                Scryfall request.
        """

        self._client = client

    async def image_status(self, scryfall_id: str) -> str | None:
        """Report Scryfall's image status for a card.

        Args:
            scryfall_id (str): The card's Scryfall identifier.

        Returns:
            str | None: The card's ``image_status``, or None when the request
            fails.
        """

        url = f"{SCRYFALL_API_CARD_URL}{scryfall_id}?format=json"
        response = await self._client.get(url)

        if response is None:
            return None

        return response.json()["image_status"]

    async def download_image(
        self,
        scryfall_id: str,
        face: Face | None = None,
    ) -> bytes | None:
        """Download a card's image bytes from Scryfall.

        Args:
            scryfall_id (str): The card's Scryfall identifier.
            face (Face | None): The face to fetch for a two-sided card, or None
                for a single-faced card.

        Returns:
            bytes | None: The image bytes, or None when the request fails.
        """

        url = f"{SCRYFALL_API_CARD_URL}{scryfall_id}?format=image"

        if face is not None:
            url += f"&face={face}"

        response = await self._client.get(url)

        if response is None:
            return None

        return response.content
