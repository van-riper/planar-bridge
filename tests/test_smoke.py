"""Smoke test confirming the package imports as an installed package."""

import planar_bridge


def test_package_exposes_version() -> None:
    """planar_bridge imports cleanly and exposes a version string."""
    assert isinstance(planar_bridge.__version__, str)
    assert planar_bridge.__version__
