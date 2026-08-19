"""Tests for the pure per-card derivations in domain/card_model.py."""

from typing import Any

import pytest

from planar_bridge.config.loader import AppConfig
from planar_bridge.domain import card_model


def make_config(**overrides: Any) -> AppConfig:
    """An AppConfig with permissive defaults, overridable per test."""
    base: dict[str, Any] = {
        "pull_reprints": False,
        "card_language": "English",
        "pardoned_sets": frozenset(),
        "exempt_sets": frozenset(),
        "exempt_promos": frozenset({"prerelease"}),
        "exempt_types": frozenset(),
    }
    base.update(overrides)
    return AppConfig(**base)


def make_card(**overrides: Any) -> dict[str, Any]:
    """A minimal, non-bad MTGJSON card entry, overridable per test."""
    base: dict[str, Any] = {
        "language": "English",
        "name": "Llanowar Elves",
    }
    base.update(overrides)
    return base


# --- card_is_bad ---------------------------------------------------------


def test_clean_card_is_not_bad() -> None:
    """A default card with no disqualifying traits passes the filter."""
    assert card_model.card_is_bad(make_card(), make_config(), "normal") is False


def test_reprint_is_bad_when_reprints_disabled() -> None:
    """A reprint is rejected when pull_reprints is off."""
    card_data = make_card(isReprint=True)
    config = make_config(pull_reprints=False)
    assert card_model.card_is_bad(card_data, config, "normal") is True


def test_reprint_is_not_bad_when_reprints_enabled() -> None:
    """A reprint is accepted when pull_reprints is on."""
    card_data = make_card(isReprint=True)
    config = make_config(pull_reprints=True)
    assert card_model.card_is_bad(card_data, config, "normal") is False


def test_wrong_language_is_bad() -> None:
    """A card not in the configured language is rejected."""
    card_data = make_card(language="Japanese")
    assert card_model.card_is_bad(card_data, make_config(), "normal") is True


def test_phyrexian_language_is_never_bad() -> None:
    """Phyrexian cards pass the language filter regardless of config."""
    card_data = make_card(language="Phyrexian")
    assert card_model.card_is_bad(card_data, make_config(), "normal") is False


def test_quenya_language_is_never_bad() -> None:
    """Quenya cards pass the language filter regardless of config."""
    card_data = make_card(language="Quenya")
    assert card_model.card_is_bad(card_data, make_config(), "normal") is False


def test_checklist_name_is_bad() -> None:
    """A card named Checklist is rejected."""
    card_data = make_card(name="Checklist")
    assert card_model.card_is_bad(card_data, make_config(), "normal") is True


def test_online_only_is_bad() -> None:
    """An online-only card is rejected."""
    card_data = make_card(isOnlineOnly=True)
    assert card_model.card_is_bad(card_data, make_config(), "normal") is True


def test_bad_layout_is_bad() -> None:
    """A card with a blacklisted layout is rejected."""
    assert (
        card_model.card_is_bad(make_card(), make_config(), "art_series") is True
    )


def test_funny_card_is_bad() -> None:
    """A funny (un-set) card is rejected."""
    card_data = make_card(isFunny=True)
    assert card_model.card_is_bad(card_data, make_config(), "normal") is True


def test_exempt_promo_type_is_bad() -> None:
    """A card carrying an exempt promo type is rejected."""
    card_data = make_card(promoTypes=["prerelease", "boosterfun"])
    assert card_model.card_is_bad(card_data, make_config(), "normal") is True


def test_non_exempt_promo_type_is_not_bad() -> None:
    """A card whose promo types are all non-exempt is accepted."""
    card_data = make_card(promoTypes=["boosterfun"])
    assert card_model.card_is_bad(card_data, make_config(), "normal") is False


# --- card_filename -------------------------------------------------------


def test_filename_is_uuid_for_simple_layout() -> None:
    """A non-combined layout uses the card's own UUID as filename."""
    assert card_model.card_filename("u2", "normal", []) == "u2"


def test_filename_joins_sorted_faces_for_combined_layout() -> None:
    """A combined layout joins all face UUIDs in sorted order."""
    assert card_model.card_filename("u2", "split", ["u1", "u3"]) == "u1_u2_u3"


def test_filename_requires_related_uuids_for_combined_layout() -> None:
    """A combined layout with no related UUIDs is a programming error."""
    with pytest.raises(ValueError, match="has no related UUIDs"):
        card_model.card_filename("u2", "split", [])


def test_filename_does_not_mutate_related_uuids() -> None:
    """Building a filename leaves the caller's UUID list untouched."""
    related_uuids = ["u1", "u3"]
    card_model.card_filename("u2", "split", related_uuids)
    assert related_uuids == ["u1", "u3"]


# --- card_face -----------------------------------------------------------


def test_face_is_none_for_non_twosided_layout() -> None:
    """A single-faced layout has no face designation."""
    assert card_model.card_face("normal", "a") is None


def test_face_is_front_for_side_a() -> None:
    """Side a of a two-sided layout maps to the front face."""
    assert card_model.card_face("transform", "a") == "front"


def test_face_is_back_for_side_b() -> None:
    """Side b of a two-sided layout maps to the back face."""
    assert card_model.card_face("transform", "b") == "back"


# --- build_card_fields ---------------------------------------------------


def test_build_card_fields_assembles_derived_facts() -> None:
    """build_card_fields collects every derived per-card fact."""
    card_data = make_card(
        uuid="abc",
        layout="transform",
        identifiers={"scryfallId": "scry-1"},
        name="Delver of Secrets",
        side="a",
        otherFaceIds=["xyz"],
    )

    fields = card_model.build_card_fields(card_data, make_config())

    assert fields.uuid == "abc"
    assert fields.scryfall_id == "scry-1"
    assert fields.layout == "transform"
    assert fields.face == "front"
    assert fields.display_label == "abc | Delver of Secrets"
    assert fields.filename == "abc"
    assert fields.is_bad is False
