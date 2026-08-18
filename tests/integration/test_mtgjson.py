"""Integration tests for the MTGJSON source."""

import asyncio
import gzip

import httpx
import pytest

from planar_bridge.domain.metadata import MetadataInfo
from planar_bridge.engine.client import AsyncHttpClient
from planar_bridge.engine.limiter import RateLimiter
from planar_bridge.sources.mtgjson import MtgjsonSource


def build_source(
    items: list[httpx.Response],
) -> tuple[MtgjsonSource, httpx.AsyncClient, list[str]]:
    """Build an MtgjsonSource over a MockTransport that records its URLs."""
    queue = list(items)
    captured_urls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured_urls.append(str(request.url))
        return queue.pop(0)

    httpx_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    client = AsyncHttpClient(httpx_client, RateLimiter(1000))
    return MtgjsonSource(client), httpx_client, captured_urls


def test_fetch_metadata_returns_the_parsed_info() -> None:
    """The metadata is parsed into a MetadataInfo with a clean version."""
    source, httpx_client, _ = build_source([
        httpx.Response(
            200,
            json={"meta": {"date": "2024-01-01", "version": "5.2.2+abc"}},
        )
    ])

    async def scenario() -> MetadataInfo | None:
        info = await source.fetch_metadata()
        await httpx_client.aclose()
        return info

    assert asyncio.run(scenario()) == MetadataInfo(
        date="2024-01-01", version="5.2.2"
    )


def test_fetch_metadata_requests_the_meta_endpoint() -> None:
    """The metadata query targets MTGJSON's Meta.json."""
    source, httpx_client, captured_urls = build_source([
        httpx.Response(200, json={"meta": {"date": "x", "version": "5.2.2"}})
    ])

    async def scenario() -> None:
        await source.fetch_metadata()
        await httpx_client.aclose()

    asyncio.run(scenario())

    assert captured_urls == ["https://mtgjson.com/api/v5/Meta.json"]


def test_fetch_metadata_is_none_on_failure() -> None:
    """A failed metadata query yields None."""
    source, httpx_client, _ = build_source([httpx.Response(404)])

    async def scenario() -> MetadataInfo | None:
        info = await source.fetch_metadata()
        await httpx_client.aclose()
        return info

    assert asyncio.run(scenario()) is None


def test_download_bulk_decompresses_the_payload() -> None:
    """A gzipped bulk file is returned decompressed."""
    payload = b'{"data": {}}'
    source, httpx_client, _ = build_source([
        httpx.Response(200, content=gzip.compress(payload))
    ])

    async def scenario() -> bytes | None:
        content = await source.download_bulk("AllPrintings")
        await httpx_client.aclose()
        return content

    assert asyncio.run(scenario()) == payload


@pytest.mark.parametrize(
    ("target", "expected_url"),
    [
        ("AllPrintings", "https://mtgjson.com/api/v5/AllPrintings.sqlite.gz"),
        ("Meta", "https://mtgjson.com/api/v5/Meta.json.gz"),
    ],
)
def test_download_bulk_requests_the_right_url(
    target: str, expected_url: str
) -> None:
    """AllPrintings comes from SQLite; Meta still comes from JSON."""
    source, httpx_client, captured_urls = build_source([
        httpx.Response(200, content=gzip.compress(b"{}"))
    ])

    async def scenario() -> None:
        await source.download_bulk(target)
        await httpx_client.aclose()

    asyncio.run(scenario())

    assert captured_urls == [expected_url]


def test_download_bulk_is_none_on_failure() -> None:
    """A failed bulk download yields None."""
    source, httpx_client, _ = build_source([httpx.Response(404)])

    async def scenario() -> bytes | None:
        content = await source.download_bulk("Meta")
        await httpx_client.aclose()
        return content

    assert asyncio.run(scenario()) is None
