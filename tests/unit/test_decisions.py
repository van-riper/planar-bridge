"""Unit tests for the pure download-decision module."""

from planar_bridge.domain.decisions import DownloadDecision, decide_download


def test_placeholder_status_is_not_downloaded() -> None:
    """A placeholder image is never downloaded."""
    decision = decide_download(
        image_status="placeholder",
        local_is_high_resolution=None,
        image_exists=False,
    )

    assert decision == DownloadDecision(
        should_download=False, source_is_high_resolution=False
    )


def test_missing_status_is_not_downloaded() -> None:
    """A missing image is never downloaded."""
    decision = decide_download(
        image_status="missing",
        local_is_high_resolution=None,
        image_exists=False,
    )

    assert decision.should_download is False


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
