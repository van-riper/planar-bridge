"""Per-card facts derived from MTGJSON card data.

Every function here is pure: it reads a card's MTGJSON dictionary (and, for
filtering, the resolved AppConfig) and returns a derived value. Nothing in
this module performs I/O.
"""

from dataclasses import dataclass

from planar_bridge.aliases import CardData, Face
from planar_bridge.config.loader import AppConfig
from planar_bridge.domain import layouts


@dataclass(frozen=True, kw_only=True)
class CardFields:
    """Immutable per-card facts derived from one MTGJSON card entry.

    Attributes:
        uuid: MTGJSON card UUID.
        scryfall_id: Scryfall identifier used to build image URLs.
        layout: MTGJSON layout string (e.g. "normal", "transform").
        face: "front"/"back" for two-sided cards, else None.
        display_label: Human-readable "uuid | name" log label.
        filename: Stem of the stored image file (no extension).
        is_bad: True when the card should not be downloaded.
    """

    uuid: str
    scryfall_id: str
    layout: str
    face: Face | None
    display_label: str
    filename: str
    is_bad: bool


def card_face(layout: str, side: str | None) -> Face | None:
    """Resolve which face of a two-sided card this entry represents.

    Args:
        layout: MTGJSON layout string.
        side: MTGJSON "side" value. For a two-sided layout it must be "a"
            or "b"; None is expected only for other layouts.

    Returns:
        "front" for side "a" and "back" for side "b" on two-sided layouts,
        or None for any other layout.

    Raises:
        ValueError: If a two-sided layout's side is neither "a" nor "b".
    """
    if layout not in layouts.LAYOUT_TWOSIDED:
        return None
    if side not in {"a", "b"}:
        message = f"unexpected side {side!r} for two-sided layout {layout!r}"
        raise ValueError(message)

    return "front" if side == "a" else "back"


def card_filename(uuid: str, layout: str, related_uuids: list[str]) -> str:
    """Build the image filename stem for a card.

    Combined-layout cards (split, flip, adventure, aftermath) share a single
    image across their faces, so their stem joins every face UUID with "_" in
    sorted order. All other cards use their own UUID.

    Args:
        uuid: The card's own MTGJSON UUID.
        layout: MTGJSON layout string.
        related_uuids: UUIDs of the card's other faces. Must be non-empty
            for a combined layout; ignored for any other layout. The list
            is not mutated.

    Returns:
        The filename stem (no extension).

    Raises:
        ValueError: If a combined layout has no related UUIDs.
    """
    if layout not in layouts.LAYOUT_COMBINED:
        return uuid
    if not related_uuids:
        message = f"combined layout {layout!r} has no related UUIDs"
        raise ValueError(message)

    combined_uuids = [uuid, *related_uuids]
    combined_uuids.sort()

    return ("_").join(map(str, combined_uuids))


def card_is_bad(card_data: CardData, config: AppConfig, layout: str) -> bool:
    """Decide whether a card should be skipped entirely.

    A card is "bad" when any disqualifying condition holds: it is a reprint
    while reprints are disabled; its language is neither the configured
    language nor an always-allowed oracle language (Phyrexian, Quenya); it is
    a checklist/double-faced placeholder; it is online-only; its layout is
    unsupported; it is a funny card; or it carries an exempt promo type.

    Args:
        card_data: One MTGJSON card entry.
        config: Resolved filtering configuration.
        layout: MTGJSON layout string, checked against the unsupported
            layout set.

    Returns:
        True if the card should be skipped.
    """
    # TODO: all of these conditions should be configurable in the future
    is_reprint = card_data.get("isReprint") and not config.pull_reprints
    # TODO: needs a better implementation of supporting oracle languages
    is_language_bad = card_data["language"] not in {
        config.card_language,
        "Phyrexian",
        "Quenya",
        "Dwarvish",
        "Klingon",
    }
    is_name_bad = card_data["name"] in {"Checklist", "Double-Faced"}
    is_layout_bad = layout in layouts.LAYOUT_BAD
    is_online_only = bool(card_data.get("isOnlineOnly"))
    is_funny = bool(card_data.get("isFunny"))
    # TODO: promo_crosscheck needs to be isolated in its own public function
    promos: list[str] = card_data.get("promoTypes", [])
    promos_crosscheck: set[str] = set(config.exempt_promos) & set(promos)
    is_promo_bad = len(promos_crosscheck) > 0

    bad_conditions = (
        is_reprint,
        is_language_bad,
        is_name_bad,
        is_layout_bad,
        is_online_only,
        is_funny,
        is_promo_bad,
    )

    return any(bad_conditions)


def build_card_fields(card_data: CardData, config: AppConfig) -> CardFields:
    """Assemble the derived CardFields for one MTGJSON card entry.

    Args:
        card_data: One MTGJSON card entry.
        config: Resolved filtering configuration.

    Returns:
        The immutable derived facts for the card.
    """
    uuid: str = card_data["uuid"]
    scryfall_id: str = card_data["identifiers"]["scryfallId"]
    layout: str = card_data["layout"]
    side: str | None = card_data.get("side")
    face = card_face(layout, side)
    name: str = card_data["name"]
    display_label = f"{uuid} | {name}"
    related_uuids: list[str] = card_data.get("otherFaceIds", [])
    filename = card_filename(uuid, layout, related_uuids)
    is_bad = card_is_bad(card_data, config, layout)

    return CardFields(
        uuid=uuid,
        scryfall_id=scryfall_id,
        layout=layout,
        face=face,
        display_label=display_label,
        filename=filename,
        is_bad=is_bad,
    )
