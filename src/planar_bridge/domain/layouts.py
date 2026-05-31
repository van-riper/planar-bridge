"""MTGJSON card layout categories.

Each frozenset groups the layout strings that share a download behavior.
The categories are pairwise disjoint: a layout belongs to at most one.
"""

LAYOUT_COMBINED: frozenset[str] = frozenset(
    {
        "adventure",
        "aftermath",
        "flip",
        "split",
    }
)

LAYOUT_TWOSIDED: frozenset[str] = frozenset(
    {
        "modal_dfc",
        "reversible_card",
        "transform",
    }
)

LAYOUT_TOKEN: frozenset[str] = frozenset(
    {
        "double_faced_token",
        "token",
    }
)

LAYOUT_BAD: frozenset[str] = frozenset(
    {
        "art_series",
        "augment",
        "host",
    }
)
