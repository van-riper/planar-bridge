"""A shared async rate limiter that caps total request throughput.

The limiter spaces grants by a fixed minimum interval so that, however many
coroutines share one instance, the combined request rate stays at or below the
configured ceiling. This replaces the per-call sleep that paced the old
serial downloader and is load-bearing for honoring Scryfall's rate limit.
"""

import asyncio
from collections.abc import Callable
from time import monotonic

from planar_bridge.engine.ports import Limiter, Sleeper


class RateLimiter(Limiter):  # pylint: disable=too-few-public-methods
    """Caps the global request rate by spacing grants across coroutines.

    Each acquire reserves the next free time slot under a lock, then
    waits until that slot arrives. The lock guards only the scheduling, so the
    waits themselves overlap and concurrency is preserved while the grant rate
    stays bounded.
    """

    def __init__(
        self,
        max_requests_per_second: float,
        *,
        clock: Callable[[], float] = monotonic,
        sleeper: Sleeper = asyncio.sleep,
    ) -> None:
        """Build a limiter for a maximum request rate.

        Args:
            max_requests_per_second: The throughput ceiling. Must be
                positive.
            clock: Returns the current time in seconds. Injected for
                deterministic testing.
            sleeper: Awaitable sleep for a number of seconds. Injected for
                deterministic testing.

        Raises:
            ValueError: If max_requests_per_second is not positive.
        """
        if max_requests_per_second <= 0:
            raise ValueError(
                "max_requests_per_second must be positive, got "
                f"{max_requests_per_second}"
            )

        self._minimum_interval_seconds: float = 1.0 / max_requests_per_second
        self._clock: Callable[[], float] = clock
        self._sleeper: Sleeper = sleeper
        self._lock: asyncio.Lock = asyncio.Lock()
        self._next_available_time: float | None = None

    async def acquire(self) -> None:
        """Wait until the next request is allowed to proceed."""
        async with self._lock:
            now: float = self._clock()
            if (
                self._next_available_time is None
                or now >= self._next_available_time
            ):
                scheduled_time = now
            else:
                scheduled_time = self._next_available_time

            self._next_available_time = (
                scheduled_time + self._minimum_interval_seconds
            )
            delay_seconds: float = scheduled_time - now

        if delay_seconds > 0:
            await self._sleeper(delay_seconds)
