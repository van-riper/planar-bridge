"""An async HTTP client with rate limiting and a redesigned retry policy.

The client funnels every request through the shared rate limiter, then retries
transient failures with capped, jittered exponential backoff. Permanent client
errors (such as 404) are treated as fatal and fail fast rather than burning the
whole retry budget. This replaces the old ``utils.handle_response`` that retried
every error with a fixed escalating sleep.
"""

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from random import random

import httpx

from .ports import Limiter

# HTTP statuses worth retrying: rate limiting and transient server faults.
RETRYABLE_STATUS_CODES = frozenset({408, 429, 500, 502, 503, 504})


def is_retryable_status(status_code: int) -> bool:
    """Report whether an HTTP status is worth retrying.

    Args:
        status_code (int): The HTTP status code of a failed response.

    Returns:
        bool: True for transient rate-limit and server faults, False for
        permanent client errors.
    """

    return status_code in RETRYABLE_STATUS_CODES


def backoff_seconds(
    attempt: int,
    *,
    base_seconds: float,
    maximum_seconds: float,
    jitter_fraction: float,
    random_source: Callable[[], float] = random,
) -> float:
    """Compute the backoff delay before the next retry.

    The delay doubles with each attempt, is clamped to a ceiling, then gains a
    random jitter so concurrent retries do not align into a new burst.

    Args:
        attempt (int): Zero-based index of the attempt that just failed.
        base_seconds (float): Delay after the first failure, before doubling.
        maximum_seconds (float): Ceiling for the pre-jitter delay.
        jitter_fraction (float): Fraction of the capped delay added as jitter.
        random_source (Callable[[], float]): Returns a value in ``[0, 1)``.
            Injected for deterministic testing.

    Returns:
        float: The number of seconds to wait before retrying.
    """

    exponential = base_seconds * (2**attempt)
    capped = min(exponential, maximum_seconds)
    jitter = capped * jitter_fraction * random_source()

    return capped + jitter


@dataclass(frozen=True, kw_only=True)
class RetryPolicy:
    """Immutable retry knobs for the async client.

    Attributes:
        max_attempts (int): Total tries before giving up.
        base_seconds (float): First-retry backoff, before doubling.
        maximum_seconds (float): Ceiling for the pre-jitter backoff.
        jitter_fraction (float): Fraction of the backoff added as jitter.
        random_source (Callable[[], float]): Returns a value in ``[0, 1)``,
            injected for deterministic testing of the jitter.
    """

    max_attempts: int = 4
    base_seconds: float = 1.0
    maximum_seconds: float = 30.0
    jitter_fraction: float = 0.25
    random_source: Callable[[], float] = random

    def backoff_for(self, attempt: int) -> float:
        """Return the backoff delay for the attempt that just failed.

        Args:
            attempt (int): Zero-based index of the failed attempt.

        Returns:
            float: Seconds to wait before the next retry.
        """

        return backoff_seconds(
            attempt,
            base_seconds=self.base_seconds,
            maximum_seconds=self.maximum_seconds,
            jitter_fraction=self.jitter_fraction,
            random_source=self.random_source,
        )


class AsyncHttpClient:  # pylint: disable=too-few-public-methods
    """Rate-limited async HTTP client with capped, jittered retries."""

    def __init__(
        self,
        client: httpx.AsyncClient,
        limiter: Limiter,
        *,
        policy: RetryPolicy = RetryPolicy(),
        sleeper: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        """Build a client over an httpx session and a shared limiter.

        Args:
            client (httpx.AsyncClient): The underlying httpx session. Its
                lifecycle is owned by the caller.
            limiter (Limiter): The shared limiter every request waits on.
            policy (RetryPolicy): The retry knobs governing backoff and the
                attempt budget.
            sleeper (Callable[[float], Awaitable[None]]): Awaitable sleep.
                Injected for deterministic testing.
        """

        self._client = client
        self._limiter = limiter
        self._policy = policy
        self._sleeper = sleeper

    async def get(self, url: str) -> httpx.Response | None:
        """Fetch a URL, retrying transient failures.

        Each attempt first waits on the shared limiter. A successful response
        is returned. A fatal status fails fast with None. Transient failures
        retry with capped, jittered backoff until the attempt budget runs out.

        Args:
            url (str): The absolute URL to fetch.

        Returns:
            httpx.Response | None: The successful response, or None when the
            request fails fatally or exhausts its retries.
        """

        for attempt in range(self._policy.max_attempts):

            await self._limiter.acquire()

            try:
                response = await self._client.get(url, follow_redirects=True)
                response.raise_for_status()
                return response

            except httpx.HTTPStatusError as error:
                if not is_retryable_status(error.response.status_code):
                    return None

            except httpx.TransportError:
                pass

            if attempt + 1 < self._policy.max_attempts:
                await self._sleeper(self._policy.backoff_for(attempt))

        return None
