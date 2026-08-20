"""Console entry point: parse args, guard the Python version, run the pull.

The version guard runs at import time so the installed console script fails
fast on an unsupported interpreter, matching the behavior the old
__main__ module had.
"""

import asyncio
from collections.abc import Sequence
from sys import version_info

from planar_bridge.cli.args import parse_args
from planar_bridge.cli.prompt import approval_for
from planar_bridge.events import EventBus, Interrupted, RunFailed
from planar_bridge.pipeline import pull_all
from planar_bridge.reporters.console import ConsoleReporter

# The check stays even though pyproject.toml pins the minimum version:
# it protects a direct script invocation under an interpreter that never
# consulted that metadata.
if version_info[:2] < (3, 13):  # ruff: ignore[outdated-version-block]
    message = "Python version must be at least 3.13"
    raise SystemExit(message)

# Conventional shell exit code for a process ended by Ctrl-C (128 + SIGINT).
INTERRUPT_EXIT_CODE = 130

# Generic failure exit code for a run aborted by an unreachable source.
RUN_FAILED_EXIT_CODE = 1


def run(argv: Sequence[str] | None = None) -> None:
    """Parse arguments and run the async pull pipeline, clean on failure.

    Ctrl-C surfaces as a KeyboardInterrupt out of asyncio.run rather than
    inside the coroutine, so the interrupt is caught here and reported through
    the event bus. Progress is already persisted per card, so nothing is lost.
    A source that could not be reached after retries surfaces as a
    RuntimeError, and a bad --language or config value (including malformed
    TOML) surfaces as a ValueError; both are reported the same way rather
    than as a raw traceback.

    Args:
        argv: The argument vector, or None to read sys.argv.

    Raises:
        SystemExit: With the conventional interrupt code on Ctrl-C, or
            RUN_FAILED_EXIT_CODE when a source could not be reached or the
            configuration is invalid.
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
    except (RuntimeError, ValueError) as error:
        bus.emit(RunFailed(message=str(error)))
        raise SystemExit(RUN_FAILED_EXIT_CODE) from None
