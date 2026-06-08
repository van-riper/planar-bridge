"""MTGJSON metadata and bulk access built on the async HTTP client.

The source knows MTGJSON's URL shapes and that its bulk files arrive gzipped.
It reports the remote build metadata as a domain ``MetadataInfo`` and returns
decompressed bulk payloads, leaving the file write to the pipeline. It replaces
the network halves of the old ``MetaObject.__fetch_source`` and ``pull_bulk``.
"""

import gzip

from ..domain.metadata import MetadataInfo, normalize_version
from ..engine.client import AsyncHttpClient
from .ports import MetadataSource

MTGJSON_API_URL = "https://mtgjson.com/api/v5/"

# The bulk files Planar Bridge maintains locally.
BULK_TARGETS = ("AllPrintings", "Meta")


class MtgjsonSource(MetadataSource):
    """Fetches build metadata and bulk files from MTGJSON."""

    def __init__(self, client: AsyncHttpClient) -> None:
        """Build the source over an async HTTP client.

        Args:
            client (AsyncHttpClient): The rate-limited client used for every
                MTGJSON request.
        """

        self._client = client

    async def fetch_metadata(self) -> MetadataInfo | None:
        """Fetch MTGJSON's current build metadata.

        Returns:
            MetadataInfo | None: The remote build date and normalized version,
            or None when the request fails.
        """

        url = f"{MTGJSON_API_URL}Meta.json"
        response = await self._client.get(url)

        if response is None:
            return None

        meta = response.json()["meta"]

        return MetadataInfo(
            date=meta["date"],
            version=normalize_version(meta["version"]),
        )

    async def download_bulk(self, target: str) -> bytes | None:
        """Download and decompress one MTGJSON bulk file.

        Args:
            target (str): The bulk file stem, such as ``"AllPrintings"``.

        Returns:
            bytes | None: The decompressed JSON bytes, or None when the request
            fails.
        """

        url = f"{MTGJSON_API_URL}{target}.json.gz"
        response = await self._client.get(url)

        if response is None:
            return None

        return gzip.decompress(response.content)
