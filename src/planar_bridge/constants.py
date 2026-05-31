MTGJSON_VERS: str = "5.2.2"

TIMEOUT: float = 0.33

VERS_WARNING: str = ("\n").join(
    (
        "Planar Bridge is only expected to work with v" + MTGJSON_VERS,
        "Make sure there are no conflicts before proceeding!",
        "MTGJSON changelog: https://mtgjson.com/changelogs/mtgjson-v5/",
    )
)
