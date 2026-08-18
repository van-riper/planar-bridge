"""Unit tests for the pure download-decision module."""

import pytest

from planar_bridge.domain.decisions import (
    PLACEHOLDER_STATUSES,
    DownloadDecision,
    decide_download,
)


@pytest.mark.parametrize("image_status", sorted(PLACEHOLDER_STATUSES))
def test_placeholder_statuses_are_not_downloaded(image_status: str) -> None:
    """A placeholder or missing image is never downloaded."""
    decision = decide_download(
        image_status=image_status,
        local_is_high_resolution=None,
        image_exists=False,
    )

    assert decision == DownloadDecision(
        should_download=False, source_is_high_resolution=False
    )


def test_new_high_resolution_card_is_downloaded() -> None:
    """A high-res source with no local record is downloaded."""
    decision = decide_download(
        image_status="highres_scan",
        local_is_high_resolution=None,
        image_exists=False,
    )

    assert decision == DownloadDecision(
        should_download=True, source_is_high_resolution=True
    )


def test_new_low_resolution_card_is_downloaded() -> None:
    """A low-res source with no local record is downloaded as low-res."""
    decision = decide_download(
        image_status="lowres_scan",
        local_is_high_resolution=None,
        image_exists=False,
    )

    assert decision == DownloadDecision(
        should_download=True, source_is_high_resolution=False
    )


def test_matching_resolution_with_file_present_is_skipped() -> None:
    """A source matching the stored resolution with the file present skips."""
    decision = decide_download(
        image_status="lowres_scan",
        local_is_high_resolution=False,
        image_exists=True,
    )

    assert decision.should_download is False


def test_high_resolution_upgrade_is_downloaded() -> None:
    """A high-res source over a stored low-res scan triggers an upgrade."""
    decision = decide_download(
        image_status="highres_scan",
        local_is_high_resolution=False,
        image_exists=True,
    )

    assert decision == DownloadDecision(
        should_download=True, source_is_high_resolution=True
    )


def test_matching_resolution_with_file_missing_is_downloaded() -> None:
    """A matching resolution but absent file is re-downloaded."""
    decision = decide_download(
        image_status="highres_scan",
        local_is_high_resolution=True,
        image_exists=False,
    )

    assert decision.should_download is True
