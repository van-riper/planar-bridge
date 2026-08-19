"""Integration tests for the async HTTP client and its retry policy."""

import asyncio

import httpx
import pytest

from planar_bridge.engine.client import (
    AsyncHttpClient,
    RetryPolicy,
    backoff_seconds,
    is_retryable_status,
)
from planar_bridge.engine.ports import Sleeper

URL = "https://example.test/resource"

# One queue item is either a response to return or an exception to raise.
QueueItem = httpx.Response | Exception


class RecordingLimiter:
    """A limiter double that counts how often it is acquired."""

    def __init__(self) -> None:
        """Start with no acquisitions recorded."""
        self.acquisitions = 0

    async def acquire(self) -> None:
        """Record one acquisition."""
        self.acquisitions += 1


class RecordingSleeper:
    """A sleeper double that records the delays it is asked to wait."""

    def __init__(self) -> None:
        """Start with no delays recorded."""
        self.delays: list[float] = []

    async def __call__(self, delay: float) -> None:
        """Record a requested delay without waiting."""
        self.delays.append(delay)


def build_client(
    items: list[QueueItem],
    *,
    limiter: RecordingLimiter | None = None,
    sleeper: Sleeper | None = None,
    policy: RetryPolicy | None = None,
) -> tuple[AsyncHttpClient, httpx.AsyncClient, dict[str, int]]:
    """Build an AsyncHttpClient over a scripted MockTransport."""
    queue = list(items)
    calls = {"count": 0}

    def handler(_request: httpx.Request) -> httpx.Response:
        """Return the next queued response or raise the next queued error."""
        calls["count"] += 1
        item = queue.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    httpx_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    client = AsyncHttpClient(
        httpx_client,
        limiter or RecordingLimiter(),
        sleeper=sleeper or RecordingSleeper(),
        policy=policy or RetryPolicy(),
    )
    return client, httpx_client, calls


@pytest.mark.parametrize(
    ("status_code", "expected"),
    [(429, True), (500, True), (503, True), (404, False), (403, False)],
)
def test_is_retryable_status(status_code: int, *, expected: bool) -> None:
    """Transient server statuses are retryable; client errors are not."""
    assert is_retryable_status(status_code) is expected


def test_backoff_grows_exponentially_from_the_base() -> None:
    """Backoff doubles with each attempt before any cap or jitter."""
    delay = backoff_seconds(
        2,
        base_seconds=1.0,
        maximum_seconds=30.0,
        jitter_fraction=0.0,
        random_source=lambda: 0.0,
    )

    assert delay == pytest.approx(4.0)


def test_backoff_is_capped_at_the_maximum() -> None:
    """A large attempt count is clamped to the maximum backoff."""
    delay = backoff_seconds(
        10,
        base_seconds=1.0,
        maximum_seconds=5.0,
        jitter_fraction=0.0,
        random_source=lambda: 0.0,
    )

    assert delay == pytest.approx(5.0)


def test_backoff_adds_jitter_above_the_capped_delay() -> None:
    """Jitter extends the capped delay by up to the jitter fraction."""
    delay = backoff_seconds(
        2,
        base_seconds=1.0,
        maximum_seconds=30.0,
        jitter_fraction=0.5,
        random_source=lambda: 1.0,
    )

    assert delay == pytest.approx(6.0)


def test_get_returns_the_response_on_success() -> None:
    """A 200 response is returned to the caller."""
    client, httpx_client, calls = build_client([
        httpx.Response(200, content=b"ok")
    ])

    async def scenario() -> httpx.Response | None:
        """Issue the GET request.

        Returns:
            The successful response.
        """
        response = await client.get(URL)
        await httpx_client.aclose()
        return response

    response = asyncio.run(scenario())

    assert response is not None
    assert response.content == b"ok"
    assert calls["count"] == 1


def test_get_follows_a_redirect() -> None:
    """A 302 to a file origin is followed to the final response.

    Scryfall's ?format=image redirects from api.scryfall.com to a
    *.scryfall.io file origin, so the client must follow redirects.
    """

    def handler(request: httpx.Request) -> httpx.Response:
        """Redirect the image path once, then serve the final image.

        Returns:
            A redirect for the image path, else the final response.
        """
        if request.url.path == "/image":
            return httpx.Response(
                302, headers={"Location": "https://files.test/final"}
            )
        return httpx.Response(200, content=b"image-bytes")

    httpx_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    client = AsyncHttpClient(httpx_client, RecordingLimiter())

    async def scenario() -> httpx.Response | None:
        """Issue the GET request.

        Returns:
            The response after following the redirect.
        """
        response = await client.get("https://example.test/image")
        await httpx_client.aclose()
        return response

    response = asyncio.run(scenario())

    assert response is not None
    assert response.content == b"image-bytes"


def test_get_retries_a_retryable_status_then_succeeds() -> None:
    """A 503 is retried until a success arrives, sleeping between tries."""
    limiter = RecordingLimiter()
    sleeper = RecordingSleeper()
    client, httpx_client, calls = build_client(
        [
            httpx.Response(503),
            httpx.Response(503),
            httpx.Response(200, content=b"ok"),
        ],
        limiter=limiter,
        sleeper=sleeper,
    )

    async def scenario() -> httpx.Response | None:
        """Issue the GET request.

        Returns:
            The response after the retried statuses clear.
        """
        response = await client.get(URL)
        await httpx_client.aclose()
        return response

    response = asyncio.run(scenario())

    assert response is not None
    assert response.status_code == 200
    assert calls["count"] == 3
    assert len(sleeper.delays) == 2
    assert limiter.acquisitions == 3


def test_get_retries_a_transport_error_then_succeeds() -> None:
    """A dropped connection is treated as retryable."""
    client, httpx_client, calls = build_client([
        httpx.ConnectError("boom"),
        httpx.Response(200, content=b"ok"),
    ])

    async def scenario() -> httpx.Response | None:
        """Issue the GET request.

        Returns:
            The response after the transport error clears.
        """
        response = await client.get(URL)
        await httpx_client.aclose()
        return response

    response = asyncio.run(scenario())

    assert response is not None
    assert calls["count"] == 2


def test_get_gives_up_immediately_on_a_fatal_status() -> None:
    """A 404 is not retried; the client gives up at once."""
    sleeper = RecordingSleeper()
    client, httpx_client, calls = build_client(
        [httpx.Response(404)], sleeper=sleeper
    )

    async def scenario() -> httpx.Response | None:
        """Issue the GET request.

        Returns:
            None, since the fatal status is not retried.
        """
        response = await client.get(URL)
        await httpx_client.aclose()
        return response

    response = asyncio.run(scenario())

    assert response is None
    assert calls["count"] == 1
    assert sleeper.delays == []


def test_get_gives_up_after_the_maximum_attempts() -> None:
    """A persistent retryable failure stops after the attempt budget."""
    sleeper = RecordingSleeper()
    client, httpx_client, calls = build_client(
        [httpx.Response(503) for _ in range(4)],
        sleeper=sleeper,
        policy=RetryPolicy(max_attempts=4),
    )

    async def scenario() -> httpx.Response | None:
        """Issue the GET request.

        Returns:
            None, since the attempt budget runs out first.
        """
        response = await client.get(URL)
        await httpx_client.aclose()
        return response

    response = asyncio.run(scenario())

    assert response is None
    assert calls["count"] == 4
    assert len(sleeper.delays) == 3
