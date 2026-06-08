"""Pinned versions and tunables shared across the pull pipeline."""

MTGJSON_VERS: str = "5.2.2"

TIMEOUT: float = 0.33

# Held under Scryfall's ~10 requests-per-second limit (Terms of Use). The
# shared RateLimiter enforces this across all in-flight requests; load-bearing,
# do not raise above 10.
MAX_REQUESTS_PER_SECOND: float = 9.0

# How many card requests may be in flight at once within a set. The rate limiter
# still caps total throughput; this bounds open sockets and memory.
MAX_CONCURRENT_DOWNLOADS: int = 8

# Scryfall requires an accurate User-Agent and an Accept header on every request
# to api.scryfall.com, and refuses the default HTTP-library User-Agent. Bump the
# User-Agent version alongside the project version.
HTTP_HEADERS: dict[str, str] = {
    "User-Agent": "planar-bridge/0.1.0",
    "Accept": "application/json;q=0.9,*/*;q=0.8",
}

VERS_WARNING: str = ("\n").join(
    (
        "Planar Bridge is only expected to work with v" + MTGJSON_VERS,
        "Make sure there are no conflicts before proceeding!",
        "MTGJSON changelog: https://mtgjson.com/changelogs/mtgjson-v5/",
    )
)
