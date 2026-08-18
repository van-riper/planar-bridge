"""Tests for the layout category sets in the domain layer."""

from planar_bridge.domain import layouts


def test_categories_are_frozensets() -> None:
    """Each layout category is an immutable frozenset."""
    assert isinstance(layouts.LAYOUT_COMBINED, frozenset)
    assert isinstance(layouts.LAYOUT_TWOSIDED, frozenset)
    assert isinstance(layouts.LAYOUT_TOKEN, frozenset)
    assert isinstance(layouts.LAYOUT_BAD, frozenset)


def test_categories_are_pairwise_disjoint() -> None:
    """A layout string belongs to at most one category."""
    categories = [
        layouts.LAYOUT_COMBINED,
        layouts.LAYOUT_TWOSIDED,
        layouts.LAYOUT_TOKEN,
        layouts.LAYOUT_BAD,
    ]

    for index, category in enumerate(categories):
        for other in categories[index + 1 :]:
            assert category.isdisjoint(other)


def test_known_members_are_categorized() -> None:
    """Representative layouts land in their expected categories."""
    assert "split" in layouts.LAYOUT_COMBINED
    assert "transform" in layouts.LAYOUT_TWOSIDED
    assert "token" in layouts.LAYOUT_TOKEN
    assert "art_series" in layouts.LAYOUT_BAD
