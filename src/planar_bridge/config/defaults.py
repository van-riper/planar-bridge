"""Built-in configuration defaults and the language code map.

`load_config` layers a user's planar-bridge.toml over these values.
"""

DEFAULT_PULL_REPRINTS: bool = False

DEFAULT_LANGUAGE_CODE: str = "en"

DEFAULT_FILTER_LISTS: dict[str, list[str]] = {
    "pardoned_sets": [
        "30A",
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
