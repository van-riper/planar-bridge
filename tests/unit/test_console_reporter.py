"""Unit tests for the console reporter.

These pin the reporter's event-to-line rendering: the exact label and
message for each event, and silence for events with no output. ANSI color
codes and the timestamp are stripped so the assertions read clearly.
"""

import re

from pytest import CaptureFixture

from planar_bridge.constants import VERS_WARNING
from planar_bridge.events import (
    BulkDataLoaded,
    BulkDownloadStarted,
    CardDownloaded,
    CardFailed,
    CardSkipped,
    CardUpgraded,
    Event,
    Interrupted,
    MetadataChecked,
    MetadataCheckStarted,
    RunFinished,
    RunStarted,
    SetSkipped,
    SetStarted,
    VersionMismatch,
)
from planar_bridge.reporters.console import ConsoleReporter

_ANSI = re.compile(r"\x1b\[[0-9;]*m")
_TIMESTAMP = re.compile(r"^\[\d{2}:\d{2}:\d{2}\] ")


def visible_lines(captured: str) -> list[str]:
    """Strip ANSI color codes and the timestamp prefix from each line."""

    cleaned = []
    for raw in captured.splitlines():
        cleaned.append(_TIMESTAMP.sub("", _ANSI.sub("", raw)))
    return cleaned


def emitted(capsys: CaptureFixture[str], event: Event) -> list[str]:
    """Render one event and return its decluttered output lines."""

    ConsoleReporter().handle(event)
    return visible_lines(capsys.readouterr().out)


def test_info_narration_lines(capsys: CaptureFixture[str]) -> None:
    """Narration events render as INFO lines with their exact text."""

    assert emitted(capsys, MetadataCheckStarted()) == [
        "INFO: Comparing local & source files..."
    ]
    assert emitted(capsys, BulkDownloadStarted()) == [
        "INFO: Downloading bulk files..."
    ]
    assert emitted(capsys, BulkDataLoaded(date="2026-06-01")) == [
        "INFO: Loading bulk data (2026-06-01)..."
    ]


def test_metadata_checked_is_silent_when_outdated(
    capsys: CaptureFixture[str],
) -> None:
    """An outdated verdict prints nothing; the download itself narrates."""

    event = MetadataChecked(
        is_outdated=True, version_matches_pinned=True, source_version="5.2.2"
    )
    assert emitted(capsys, event) == []


def test_metadata_checked_reports_up_to_date(
    capsys: CaptureFixture[str],
) -> None:
    """A current verdict announces that there is nothing to download."""

    event = MetadataChecked(
        is_outdated=False, version_matches_pinned=True, source_version="5.2.2"
    )
    assert emitted(capsys, event) == ["INFO: Local data is up to date."]


def test_version_mismatch_warns_with_the_changelog_block(
    capsys: CaptureFixture[str],
) -> None:
    """A mismatch warns and reproduces the multi-line version notice."""

    lines = emitted(capsys, VersionMismatch(source_version="5.2.3"))
    assert lines[0] == "WARNING: MTGJSON has been updated to v5.2.3"
    assert lines[1:] == ["WARNING: " + w for w in VERS_WARNING.splitlines()]


def test_set_started_is_a_load_set_line(capsys: CaptureFixture[str]) -> None:
    """SetStarted renders the padded set code and the AllHighRes flag."""

    event = SetStarted(
        set_code="LEA", progress="(12.3%)", is_all_high_resolution=False
    )
    assert emitted(capsys, event) == [
        f"LOAD SET: (12.3%) {'LEA'.ljust(6)} AllHighRes: False"
    ]


def test_card_downloaded_and_upgraded_share_a_line(
    capsys: CaptureFixture[str],
) -> None:
    """Both card outcomes render the same line under different labels."""

    fields = {
        "set_code": "LEA",
        "run_progress": "(50%)",
        "set_progress": "(50%)>",
        "display_label": "uuid | Black Lotus",
    }
    body = f"(50%) {'LEA'.ljust(6)} (50%)> uuid | Black Lotus"
    assert emitted(capsys, CardDownloaded(**fields)) == [f"NEW CARD: {body}"]
    assert emitted(capsys, CardUpgraded(**fields)) == [f"ENHANCED: {body}"]


def test_run_finished_prints_summary_then_remaining(
    capsys: CaptureFixture[str],
) -> None:
    """RunFinished prints the success line then the low-res set list."""

    event = RunFinished(low_resolution_set_codes=("LEA", "LEB"))
    assert emitted(capsys, event) == [
        "INFO: Finished successfully.",
        "INFO: Remaining sets with low res scans: LEA, LEB",
    ]


def test_interrupted_is_an_error_line(capsys: CaptureFixture[str]) -> None:
    """Interrupted renders the interrupt message as an ERROR line."""

    assert emitted(capsys, Interrupted()) == [
        "ERROR: Interrupted (Ctrl-C), exiting. Progress is saved."
    ]


def test_silent_events_print_nothing(capsys: CaptureFixture[str]) -> None:
    """Forward-looking events with no legacy line render nothing."""

    silent: tuple[Event, ...] = (
        RunStarted(),
        SetSkipped(set_code="LEA"),
        CardSkipped(set_code="LEA"),
        CardFailed(set_code="LEA"),
    )
    for event in silent:
        assert emitted(capsys, event) == []
