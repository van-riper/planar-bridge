"""Per-set facts derived from MTGJSON set data.

Every function here is pure: it reads a set's MTGJSON dictionary (and, for
the omit decision, the resolved AppConfig) and returns a derived value.
Nothing in this module performs I/O.
"""

from dataclasses import dataclass

from ..aliases import CardData, SetData
from ..config.loader import AppConfig


@dataclass(frozen=True, kw_only=True)
class SetRecord:
    """Immutable per-set facts derived from one MTGJSON set entry.

    Attributes:
        set_code (str): MTGJSON set code.
        is_omitted (bool): True when the whole set should be skipped.
        card_entries (tuple[CardData, ...]): The set's cards followed by its
            tokens, in that order.
    """

    set_code: str
    is_omitted: bool
    card_entries: tuple[CardData, ...]


def set_is_omitted(set_data: SetData, config: AppConfig) -> bool:
    """Decide whether an entire set should be skipped.

    A set is omitted when its type is exempt, its code is exempt, or it is
    foreign-only or online-only. A pardoned set code overrides all of these
    and is never omitted.

    Args:
        set_data: One MTGJSON set entry.
        config: Resolved filtering configuration.

    Returns:
        True if the set should be skipped.
    """
    set_code: str = set_data["code"]

    if set_code in config.pardoned_sets:
        return False

    # TODO: all of these conditions should be configurable in the future

    is_type_exempt = str(set_data["type"]) in config.exempt_types
    is_set_exempt = set_code in config.exempt_sets

    is_foreign_only = bool(set_data.get("isForeignOnly"))
    is_online_only = bool(set_data.get("isOnlineOnly"))

    is_omitted_conditions = (
        is_type_exempt,
        is_set_exempt,
        is_foreign_only,
        is_online_only,
    )

    return any(is_omitted_conditions)


def merge_card_entries(set_data: SetData) -> list[CardData]:
    """Combine a set's cards and tokens into one ordered list.

    Args:
        set_data: One MTGJSON set entry.

    Returns:
        The set's cards followed by its tokens.
    """
    set_cards: list[CardData] = set_data["cards"]
    set_tokens: list[CardData] = set_data["tokens"]

    return set_cards + set_tokens


def build_set_record(set_data: SetData, config: AppConfig) -> SetRecord:
    """Assemble the derived SetRecord for one MTGJSON set entry.

    Args:
        set_data: One MTGJSON set entry.
        config: Resolved filtering configuration.

    Returns:
        The immutable derived facts for the set.
    """
    return SetRecord(
        set_code=set_data["code"],
        is_omitted=set_is_omitted(set_data, config),
        card_entries=tuple(merge_card_entries(set_data)),
    )
