"""Integration tests for the Scryfall source."""

import asyncio

import httpx

from planar_bridge.engine.client import AsyncHttpClient
from planar_bridge.engine.limiter import RateLimiter
from planar_bridge.sources.scryfall import ScryfallSource

SCRYFALL_ID = "scry-1"


def build_source(
    items: list[httpx.Response],
) -> tuple[ScryfallSource, httpx.AsyncClient, list[str]]:
    """Build a ScryfallSource over a MockTransport that records its URLs."""
    queue = list(items)
    captured_urls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured_urls.append(str(request.url))
        return queue.pop(0)

    httpx_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    client = AsyncHttpClient(httpx_client, RateLimiter(1000))
    return ScryfallSource(client), httpx_client, captured_urls


def test_image_status_returns_the_reported_status() -> None:
    """The image_status field is read from the card JSON."""
    source, httpx_client, _ = build_source(
        [httpx.Response(200, json={"image_status": "highres_scan"})]
    )

    async def scenario() -> str | None:
        status = await source.image_status(SCRYFALL_ID)
        await httpx_client.aclose()
        return status

    assert asyncio.run(scenario()) == "highres_scan"


def test_image_status_requests_the_json_format() -> None:
    """The status query targets the card's JSON representation."""
    source, httpx_client, captured_urls = build_source(
        [httpx.Response(200, json={"image_status": "lowres"})]
    )

    async def scenario() -> None:
        await source.image_status(SCRYFALL_ID)
        await httpx_client.aclose()

    asyncio.run(scenario())

    assert captured_urls == [
        "https://api.scryfall.com/cards/scry-1?format=json"
    ]


def test_image_status_is_none_on_failure() -> None:
    """A failed status query yields None."""
    source, httpx_client, _ = build_source([httpx.Response(404)])

    async def scenario() -> str | None:
        status = await source.image_status(SCRYFALL_ID)
        await httpx_client.aclose()
        return status

    assert asyncio.run(scenario()) is None


def test_download_image_returns_the_content() -> None:
    """A successful image request returns the raw bytes."""
    source, httpx_client, _ = build_source(
        [httpx.Response(200, content=b"image-bytes")]
    )

    async def scenario() -> bytes | None:
        content = await source.download_image(SCRYFALL_ID)
        await httpx_client.aclose()
        return content

    assert asyncio.run(scenario()) == b"image-bytes"


def test_download_image_requests_the_image_format() -> None:
    """A single-faced download targets the image representation."""
    source, httpx_client, captured_urls = build_source(
        [httpx.Response(200, content=b"image-bytes")]
    )

    async def scenario() -> None:
        await source.download_image(SCRYFALL_ID)
        await httpx_client.aclose()

    asyncio.run(scenario())

    assert captured_urls == [
        "https://api.scryfall.com/cards/scry-1?format=image"
    ]


def test_download_image_appends_the_face_for_two_sided_cards() -> None:
    """A two-faced download names the requested face in the URL."""
    source, httpx_client, captured_urls = build_source(
        [httpx.Response(200, content=b"back-bytes")]
    )

    async def scenario() -> None:
        await source.download_image(SCRYFALL_ID, face="back")
        await httpx_client.aclose()

    asyncio.run(scenario())

    assert captured_urls == [
        "https://api.scryfall.com/cards/scry-1?format=image&face=back"
    ]


def test_download_image_is_none_on_failure() -> None:
    """A failed image request yields None."""
    source, httpx_client, _ = build_source([httpx.Response(404)])

    async def scenario() -> bytes | None:
        content = await source.download_image(SCRYFALL_ID)
        await httpx_client.aclose()
        return content

    assert asyncio.run(scenario()) is None
