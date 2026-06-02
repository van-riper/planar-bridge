"""Unit tests for the pure metadata module."""

from planar_bridge.domain.metadata import (
    MetadataInfo,
    compare_metadata,
    normalize_version,
)


def make_info(**overrides: str) -> MetadataInfo:
    """Build a MetadataInfo with permissive defaults."""

    fields: dict[str, str] = {"date": "2024-01-01", "version": "5.2.2"}
    fields.update(overrides)
    return MetadataInfo(**fields)


def test_normalize_version_strips_build_suffix() -> None:
    """A +build suffix is stripped from the version string."""

    assert normalize_version("5.2.2+20240101") == "5.2.2"


def test_normalize_version_leaves_plain_version_unchanged() -> None:
    """A version with no build suffix is returned unchanged."""

    assert normalize_version("5.2.2") == "5.2.2"


def test_compare_metadata_no_local_data() -> None:
    """With no local data the verdict is outdated and version-clean."""

    source = make_info()

    result = compare_metadata(None, source, "5.2.2")

    assert result.has_local_data is False
    assert result.is_outdated is True
    assert result.version_matches_pinned is True


def test_compare_metadata_matching_dates_not_outdated() -> None:
    """Equal local and source dates are not outdated."""

    local = make_info(date="2024-01-01")
    source = make_info(date="2024-01-01")

    result = compare_metadata(local, source, "5.2.2")

    assert result.is_outdated is False


def test_compare_metadata_differing_dates_is_outdated() -> None:
    """Differing local and source dates are outdated."""

    local = make_info(date="2024-01-01")
    source = make_info(date="2024-02-02")

    result = compare_metadata(local, source, "5.2.2")

    assert result.is_outdated is True


def test_compare_metadata_version_mismatch_flagged() -> None:
    """A local version unequal to the pinned version is flagged."""

    local = make_info(version="5.2.1")
    source = make_info()

    result = compare_metadata(local, source, "5.2.2")

    assert result.version_matches_pinned is False


def test_compare_metadata_version_match_not_flagged() -> None:
    """A local version equal to the pinned version is not flagged."""

    local = make_info(version="5.2.2")
    source = make_info()

    result = compare_metadata(local, source, "5.2.2")

    assert result.version_matches_pinned is True
