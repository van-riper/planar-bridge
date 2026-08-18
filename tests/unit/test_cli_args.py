"""Unit tests for command-line argument parsing.

These pin the mapping from argv to a RunOptions value: the permissive
defaults, each flag, the repeatable and uppercased --set, and the short
-y alias.
"""

from planar_bridge.cli.args import parse_args
from planar_bridge.options import RunOptions


def test_defaults_are_a_full_permissive_run() -> None:
    """No arguments yields the default RunOptions: a full, prompted run."""
    options = parse_args([])

    assert options == RunOptions()
    assert options.assume_yes is False
    assert options.dry_run is False
    assert options.only_sets == frozenset()
    assert options.language is None


def test_toggle_flags_parse_into_run_options() -> None:
    """The boolean and language flags map onto their RunOptions fields."""
    options = parse_args(["--assume-yes", "--dry-run", "--language", "ja"])

    assert options.assume_yes is True
    assert options.dry_run is True
    assert options.language == "ja"


def test_set_is_repeatable_and_uppercased() -> None:
    """--set accepts repeats and normalizes each code to upper case."""
    options = parse_args(["--set", "lea", "--set", "leb"])

    assert options.only_sets == frozenset({"LEA", "LEB"})


def test_short_yes_flag_is_an_alias() -> None:
    """-y is accepted as the short form of --assume-yes."""
    assert parse_args(["-y"]).assume_yes is True
