MTGJSON_VERS: str = "5.2.2"

TIMEOUT: float = 0.33

LAYOUT_COMBINED: list[str] = [
    "adventure",
    "aftermath",
    "flip",
    "split",
]

LAYOUT_TWOSIDED: list[str] = [
    "modal_dfc",
    "reversible_card",
    "transform",
]

LAYOUT_TOKEN: list[str] = [
    "double_faced_token",
    "token",
]

LAYOUT_BAD: list[str] = [
    "art_series",
    "augment",
    "host",
]

VERS_WARNING: str = ("\n").join(
    (
        "Planar Bridge is only expected to work with v" + MTGJSON_VERS,
        "Make sure there are no conflicts before proceeding!",
        "MTGJSON changelog: https://mtgjson.com/changelogs/mtgjson-v5/",
    )
)
