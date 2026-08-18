"""Build the argument parser and resolve argv into a RunOptions value."""

from argparse import ArgumentParser
from collections.abc import Sequence

from ..options import RunOptions


def build_parser() -> ArgumentParser:
    """Construct the Planar Bridge argument parser.

    Returns:
        ArgumentParser: A parser for the run-level flags. The ``set`` option
        uses an append action so it may be repeated.
    """
    parser = ArgumentParser(
        prog="planar-bridge",
        description="Download and upgrade a local library of MTG card scans.",
    )

    parser.add_argument(
        "-y",
        "--assume-yes",
        action="store_true",
        help="skip the version-mismatch prompt and proceed",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="report what would download without writing images or the catalog",
    )
    parser.add_argument(
        "--set",
        action="append",
        metavar="CODE",
        help="restrict the run to this set code (repeatable)",
    )
    parser.add_argument(
        "--language",
        metavar="CODE",
        help="override the configured card-language code for this run",
    )

    return parser


def parse_args(argv: Sequence[str] | None = None) -> RunOptions:
    """Parse argv into a RunOptions value.

    Args:
        argv (Sequence[str] | None): The argument vector, or None to read
            ``sys.argv``.

    Returns:
        RunOptions: The resolved per-run switches. Set codes are upper-cased
        so case does not matter on the command line.
    """
    parsed = build_parser().parse_args(argv)

    only_sets = frozenset(code.upper() for code in (parsed.set or ()))

    return RunOptions(
        assume_yes=parsed.assume_yes,
        dry_run=parsed.dry_run,
        only_sets=only_sets,
        language=parsed.language,
    )
