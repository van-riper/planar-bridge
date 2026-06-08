"""Console entry point: guard the Python version and run the pull pipeline."""

import asyncio
from sys import version_info

from .events import EventBus, Interrupted
from .pipeline import pull_all
from .reporters.console import ConsoleReporter

if version_info.major != 3 or version_info.minor < 13:
    raise SystemExit("Python version must be at least 3.13")

# Conventional shell exit code for a process ended by Ctrl-C (128 + SIGINT).
INTERRUPT_EXIT_CODE = 130


def main() -> None:
    """Run the async pull pipeline, exiting cleanly on Ctrl-C.

    Ctrl-C surfaces as a KeyboardInterrupt out of asyncio.run rather than
    inside the coroutine, so the interrupt is caught here and reported through
    the event bus. Progress is already persisted per card, so nothing is lost.

    Raises:
        SystemExit: With the conventional interrupt code when Ctrl-C is caught.
    """

    bus = EventBus()
    bus.subscribe(ConsoleReporter().handle)

    try:
        asyncio.run(pull_all(bus))
    except KeyboardInterrupt:
        bus.emit(Interrupted())
        raise SystemExit(INTERRUPT_EXIT_CODE) from None


if __name__ == "__main__":
    main()
