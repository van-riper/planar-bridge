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

LANGUAGE_MAP: dict[str, str] = {
    "ar": "Arabic",
    "de": "German",
    "en": "English",
    "es": "Spanish",
    "fr": "French",
    "grc": "Ancient Greek",
    "he": "Hebrew",
    "it": "Italian",
    "ja": "Japanese",
    "ko": "Korean",
    "la": "Latin",
    "ph": "Phyrexian",
    "pt": "Portuguese (Brazil)",
    "px": "Phyrexian",
    "qya": "Quenya",
    "ru": "Russian",
    "sa": "Sanskrit",
    "zhs": "Chinese Simplified",
    "zht": "Chinese Traditional",
}

DEFAULT_CONFIG: dict[str, bool | str | list[str]] = {
    "pull_reprints": False,
    "card_lang": "en",
    "pardoned_sets": [
        "30A",
    ],
    "continuous_sets": [
        "SLD",
        "SLU",
        "SLX",
    ],
    "exempt_sets": [
        "MB1",
        "PDRC",
        "PLIST",
        "PURL",
        "UPLIST",
    ],
    "exempt_promos": [
        "datestamped",
        "draftweekend",
        "gameday",
        "intropack",
        "jpwalker",
        "mediainsert",
        "planeswalkerstamped",
        "playerrewards",
        "premiereshop",
        "prerelease",
        "promopack",
        "release",
        "setpromo",
        "stamped",
        "themepack",
        "thick",
        "tourney",
        "wizardsplaynetwork",
    ],
    "exempt_types": [
        "alchemy",
        "funny",
        "memorabilia",
        "token",
    ],
}

VERS_WARNING: str = ("\n").join(
    (
        "Planar Bridge is only expected to work with v" + MTGJSON_VERS,
        "Make sure there are no conflicts before proceeding!",
        "MTGJSON changelog: https://mtgjson.com/changelogs/mtgjson-v5/",
    )
)
