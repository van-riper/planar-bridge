"""Console entry point: parse args, guard the Python version, run the pull.

The version guard runs at import time so the installed console script fails
fast on an unsupported interpreter, matching the behavior the old
__main__ module had.
"""

import asyncio
from collections.abc import Sequence
from sys import version_info

from planar_bridge.events import EventBus, Interrupted
from planar_bridge.pipeline import pull_all
from planar_bridge.reporters.console import ConsoleReporter
from planar_bridge.cli.args import parse_args
from planar_bridge.cli.prompt import approval_for

if version_info.major != 3 or version_info.minor < 13:
    raise SystemExit("Python version must be at least 3.13")

# Conventional shell exit code for a process ended by Ctrl-C (128 + SIGINT).
INTERRUPT_EXIT_CODE = 130


def run(argv: Sequence[str] | None = None) -> None:
    """Parse arguments and run the async pull pipeline, clean on Ctrl-C.

    Ctrl-C surfaces as a KeyboardInterrupt out of asyncio.run rather than
    inside the coroutine, so the interrupt is caught here and reported through
    the event bus. Progress is already persisted per card, so nothing is lost.

    Args:
        argv: The argument vector, or None to read sys.argv.

    Raises:
        SystemExit: With the conventional interrupt code when Ctrl-C is caught.
    """
    options = parse_args(argv)
    approve_version = approval_for(assume_yes=options.assume_yes)

    bus = EventBus()
    bus.subscribe(ConsoleReporter().handle)

    try:
        asyncio.run(pull_all(bus, options, approve_version))
    except KeyboardInterrupt:
        bus.emit(Interrupted())
        raise SystemExit(INTERRUPT_EXIT_CODE) from None
