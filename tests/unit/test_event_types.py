"""Unit tests for the event taxonomy.

These pin the event dataclasses' fields and their immutability. The engine
emits these events as plain facts; reporters subscribe and decide how to
render them.
"""

from dataclasses import FrozenInstanceError

from pytest import raises

from planar_bridge.events import (
    BulkDataLoaded,
    BulkDownloadStarted,
    CardDownloaded,
    CardEvent,
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


def test_marker_events_take_no_fields() -> None:
    """Signal-only events construct with no arguments and are Events."""

    for marker in (
        RunStarted(),
        MetadataCheckStarted(),
        BulkDownloadStarted(),
        Interrupted(),
    ):
        assert isinstance(marker, Event)


def test_events_are_immutable() -> None:
    """A frozen event rejects attribute assignment after construction."""

    event = VersionMismatch(source_version="5.2.1")
    with raises(FrozenInstanceError):
        event.source_version = "9.9.9"  # type: ignore


def test_metadata_checked_carries_the_comparison_verdict() -> None:
    """MetadataChecked records the outdated and version-match flags."""

    checked = MetadataChecked(
        is_outdated=True,
        version_matches_pinned=False,
        source_version="5.2.1",
    )
    assert checked.is_outdated is True
    assert checked.version_matches_pinned is False
    assert checked.source_version == "5.2.1"


def test_card_events_share_a_common_base() -> None:
    """CardDownloaded and CardUpgraded subclass CardEvent (and Event)."""

    fields = {
        "set_code": "LEA",
        "run_progress": "(12.3%)",
        "set_progress": "(50.0%)>",
        "display_label": "uuid | Black Lotus",
    }
    downloaded = CardDownloaded(**fields)
    upgraded = CardUpgraded(**fields)
    assert isinstance(downloaded, CardEvent)
    assert isinstance(upgraded, CardEvent)
    assert downloaded.display_label == upgraded.display_label


def test_lifecycle_events_carry_their_payloads() -> None:
    """Set, bulk, skip, fail, and finish events expose their fields."""

    assert BulkDataLoaded(date="2026-06-01").date == "2026-06-01"
    assert (
        SetStarted(
            set_code="LEA",
            progress="(12.3%)",
            is_all_high_resolution=False,
        ).is_all_high_resolution
        is False
    )
    assert SetSkipped(set_code="CMB1").set_code == "CMB1"
    assert CardSkipped(set_code="LEA").set_code == "LEA"
    assert CardFailed(set_code="LEA").set_code == "LEA"
    assert RunFinished(
        low_resolution_set_codes=("LEA", "LEB"),
    ).low_resolution_set_codes == ("LEA", "LEB")
