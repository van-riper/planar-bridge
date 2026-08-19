"""Unit tests for the console reporter.

These pin the reporter's event-to-line rendering: the exact label and
message for each event, and silence for events with no output. ANSI color
codes and the timestamp are stripped so the assertions read clearly.
"""

import re

import pytest

from planar_bridge.constants import VERSION_WARNING
from planar_bridge.events import (
    BulkDataLoaded,
    BulkDownloadStarted,
    CardDownloaded,
    CardFailed,
    CardSkipped,
    CardUpgraded,
    Event,
    Interrupted,
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


def emitted(capsys: pytest.CaptureFixture[str], event: Event) -> list[str]:
    """Render one event and return its decluttered output lines."""
    ConsoleReporter().handle(event)
    return visible_lines(capsys.readouterr().out)


def test_info_narration_lines(capsys: pytest.CaptureFixture[str]) -> None:
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


def test_version_mismatch_warns_with_the_changelog_block(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A mismatch warns and reproduces the multi-line version notice."""
    lines = emitted(capsys, VersionMismatch(source_version="5.2.3"))
    assert lines[0] == "WARNING: MTGJSON has been updated to v5.2.3"
    assert lines[1:] == ["WARNING: " + w for w in VERSION_WARNING.splitlines()]


def test_set_started_is_a_load_set_line(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """SetStarted renders the padded set code and the AllHighRes flag."""
    event = SetStarted(
        set_code="LEA", run_count=1, run_total=8, is_all_high_resolution=False
    )
    assert emitted(capsys, event) == [
        f"LOAD SET: (12.5%) {'LEA'.ljust(6)} AllHighRes: False"
    ]


def test_card_downloaded_and_upgraded_share_a_line(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Both card outcomes render the same line under different labels."""
    fields = {
        "set_code": "LEA",
        "run_count": 4,
        "run_total": 8,
        "set_count": 4,
        "set_total": 8,
        "display_label": "uuid | Black Lotus",
    }
    body = f"(50.0%) {'LEA'.ljust(6)} (50.0%)> uuid | Black Lotus"
    assert emitted(capsys, CardDownloaded(**fields)) == [f"NEW CARD: {body}"]
    assert emitted(capsys, CardUpgraded(**fields)) == [f"ENHANCED: {body}"]


def test_progress_label_reads_full_at_completion(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """At the last card of the last set, both progress labels read (100%)."""
    event = CardDownloaded(
        set_code="LEA",
        run_count=8,
        run_total=8,
        set_count=8,
        set_total=8,
        display_label="uuid | Black Lotus",
    )
    # Both the run-level and set-level labels collapse to the full marker.
    assert emitted(capsys, event)[0].count("(100%)") == 2


def test_run_finished_prints_summary_then_remaining(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """RunFinished prints the success line then the low-res set list."""
    event = RunFinished(low_resolution_set_codes=("LEA", "LEB"))
    assert emitted(capsys, event) == [
        "INFO: Finished successfully.",
        "INFO: Remaining sets with low res scans: LEA, LEB",
    ]


def test_interrupted_is_an_error_line(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Interrupted renders the interrupt message as an ERROR line."""
    assert emitted(capsys, Interrupted()) == [
        "ERROR: Interrupted (Ctrl-C), exiting. Progress is saved."
    ]


def test_silent_events_print_nothing(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Forward-looking events with no legacy line render nothing."""
    silent: tuple[Event, ...] = (
        RunStarted(),
        CardSkipped(set_code="LEA"),
    )
    for event in silent:
        assert emitted(capsys, event) == []


def test_set_skipped_is_a_skip_set_line(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """An omitted set renders a SKIP SET line naming the set."""
    assert emitted(capsys, SetSkipped(set_code="LEA")) == ["SKIP SET: LEA"]


def test_card_failed_is_an_error_line(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A failed card download renders an ERROR line naming its set."""
    assert emitted(capsys, CardFailed(set_code="LEA")) == [
        "ERROR: Failed to download a card in LEA"
    ]
