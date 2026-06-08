"""Unit tests for the CLI's interactive version-drift prompt."""

import pytest

from planar_bridge.cli.prompt import approval_for, confirm_version_drift


def test_confirm_version_drift_reads_yes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A yes answer at the prompt approves proceeding."""

    monkeypatch.setattr("builtins.input", lambda _: "y")
    assert confirm_version_drift() is True


def test_confirm_version_drift_reads_no(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A no (or empty) answer declines, defaulting to no."""

    monkeypatch.setattr("builtins.input", lambda _: "")
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
