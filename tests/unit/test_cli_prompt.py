"""Unit tests for the CLI's interactive version-drift prompt."""

import pytest

from planar_bridge.cli.prompt import (
    _ask_yes_no,
    approval_for,
    confirm_version_drift,
)


@pytest.mark.parametrize(
    "text, expected",
    [("y", True), ("Y", True), (" y ", True), ("n", False), ("N", False)],
)
def test_ask_yes_no_accepts_y_or_n(
    monkeypatch: pytest.MonkeyPatch, text: str, expected: bool
) -> None:
    """A y or n answer (any case, surrounding space) returns its bool."""

    monkeypatch.setattr("builtins.input", lambda _: text)
    assert _ask_yes_no("Proceed?") is expected


def test_ask_yes_no_reprompts_until_valid(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Anything other than y or n re-prompts until a valid answer arrives."""

    answers = iter(["", "maybe", "y"])
    monkeypatch.setattr("builtins.input", lambda _: next(answers))
    assert _ask_yes_no("Proceed?") is True


def test_ask_yes_no_treats_eof_as_no(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A closed input stream declines rather than raising."""

    def raise_eof(_: str) -> str:
        raise EOFError

    monkeypatch.setattr("builtins.input", raise_eof)
    assert _ask_yes_no("Proceed?") is False


def test_confirm_version_drift_reads_yes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A yes answer at the prompt approves proceeding."""

    monkeypatch.setattr("builtins.input", lambda _: "y")
    assert confirm_version_drift() is True


def test_confirm_version_drift_reads_no(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A no answer declines."""

    monkeypatch.setattr("builtins.input", lambda _: "n")
    assert confirm_version_drift() is False


def test_approval_for_assume_yes_skips_the_prompt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """--assume-yes yields an approval that proceeds without prompting."""

    def fail_if_prompted(_: str) -> str:
        raise AssertionError("input() must not be called under --assume-yes")

    monkeypatch.setattr("builtins.input", fail_if_prompted)
    assert approval_for(assume_yes=True)() is True


def test_approval_for_interactive_uses_the_prompt() -> None:
    """Without --assume-yes the approval is the interactive prompt."""

    assert approval_for(assume_yes=False) is confirm_version_drift
