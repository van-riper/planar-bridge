"""Unit tests for the shared async rate limiter."""

import asyncio

import pytest

from planar_bridge.engine.limiter import RateLimiter


class FakeClock:
    """A controllable clock and sleeper for deterministic limiter tests."""

    def __init__(self) -> None:
        """Start the clock at zero with no sleeps recorded."""
        self.now = 0.0
        self.sleeps: list[float] = []

    def time(self) -> float:
        """Return the current fake time in seconds."""
        return self.now

    async def sleep(self, duration: float) -> None:
        """Record the sleep and advance the fake clock by its duration."""
        self.sleeps.append(duration)
        self.now += duration


def test_non_positive_rate_is_rejected() -> None:
    """A rate of zero or below has no sensible interval and is rejected."""
    with pytest.raises(ValueError, match="must be positive"):
        RateLimiter(0)


def test_first_acquire_does_not_wait() -> None:
    """The first acquire is granted immediately without sleeping."""
    clock = FakeClock()
    limiter = RateLimiter(10, clock=clock.time, sleeper=clock.sleep)

    asyncio.run(limiter.acquire())

    assert clock.sleeps == []


def test_serial_acquires_are_spaced_by_the_interval() -> None:
    """Back-to-back acquires are spaced by one over the rate."""
    clock = FakeClock()
    limiter = RateLimiter(10, clock=clock.time, sleeper=clock.sleep)

    async def scenario() -> None:
        """Acquire the limiter three times back to back."""
        await limiter.acquire()
        await limiter.acquire()
        await limiter.acquire()

    asyncio.run(scenario())

    assert clock.sleeps == pytest.approx([0.1, 0.1])
    assert clock.now == pytest.approx(0.2)


def test_idle_gap_does_not_bank_credit() -> None:
    """A long idle gap does not let later acquires fire early in a burst."""
    clock = FakeClock()
    limiter = RateLimiter(10, clock=clock.time, sleeper=clock.sleep)

    async def scenario() -> None:
        """Acquire the limiter, jump the clock forward, then acquire again."""
        await limiter.acquire()
        clock.now = 1.0
        await limiter.acquire()

    asyncio.run(scenario())

    assert clock.sleeps == []
