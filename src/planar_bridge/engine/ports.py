"""Structural ports the engine depends on, implemented within the engine.

The HTTP client is typed against the Limiter protocol rather than the
concrete RateLimiter, so any object that can be awaited for a turn
satisfies it, including the recording double used in tests. RateLimiter
implements it by explicit subclassing so the type checker confirms the match.
"""

from typing import Protocol


class Limiter(Protocol):  # pylint: disable=too-few-public-methods
    """A throughput limiter every request waits on before proceeding."""

    async def acquire(self) -> None:
        """Block until the caller may proceed with one request."""
