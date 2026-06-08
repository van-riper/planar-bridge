"""Unit tests for the pure metadata module."""

from planar_bridge.domain.metadata import (
    MetadataInfo,
    normalize_version,
    version_matches_pin,
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


def test_version_matches_pin_true_without_local_data() -> None:
    """With no local data the version is vacuously matched."""

    assert version_matches_pin(None, "5.2.2") is True


def test_version_matches_pin_true_when_local_equals_pin() -> None:
    """A local version equal to the pinned version matches."""

    assert version_matches_pin(make_info(version="5.2.2"), "5.2.2") is True


def test_version_matches_pin_false_when_local_differs() -> None:
    """A local version unequal to the pinned version does not match."""

    assert version_matches_pin(make_info(version="5.2.1"), "5.2.2") is False
