"""Tests for the pure per-card derivations in domain/card.py."""

from typing import Any

from pytest import raises

from planar_bridge.config.loader import AppConfig
from planar_bridge.domain import card


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
    assert card.card_is_bad(make_card(), make_config(), "normal") is False


def test_reprint_is_bad_when_reprints_disabled() -> None:
    card_data = make_card(isReprint=True)
    config = make_config(pull_reprints=False)
    assert card.card_is_bad(card_data, config, "normal") is True


def test_reprint_is_not_bad_when_reprints_enabled() -> None:
    card_data = make_card(isReprint=True)
    config = make_config(pull_reprints=True)
    assert card.card_is_bad(card_data, config, "normal") is False


def test_wrong_language_is_bad() -> None:
    card_data = make_card(language="Japanese")
    assert card.card_is_bad(card_data, make_config(), "normal") is True


def test_phyrexian_language_is_never_bad() -> None:
    card_data = make_card(language="Phyrexian")
    assert card.card_is_bad(card_data, make_config(), "normal") is False


def test_quenya_language_is_never_bad() -> None:
    card_data = make_card(language="Quenya")
    assert card.card_is_bad(card_data, make_config(), "normal") is False


def test_checklist_name_is_bad() -> None:
    card_data = make_card(name="Checklist")
    assert card.card_is_bad(card_data, make_config(), "normal") is True


def test_online_only_is_bad() -> None:
    card_data = make_card(isOnlineOnly=True)
    assert card.card_is_bad(card_data, make_config(), "normal") is True


def test_bad_layout_is_bad() -> None:
    assert card.card_is_bad(make_card(), make_config(), "art_series") is True


def test_funny_card_is_bad() -> None:
    card_data = make_card(isFunny=True)
    assert card.card_is_bad(card_data, make_config(), "normal") is True


def test_exempt_promo_type_is_bad() -> None:
    card_data = make_card(promoTypes=["prerelease", "boosterfun"])
    assert card.card_is_bad(card_data, make_config(), "normal") is True


def test_non_exempt_promo_type_is_not_bad() -> None:
    card_data = make_card(promoTypes=["boosterfun"])
    assert card.card_is_bad(card_data, make_config(), "normal") is False


# --- card_filename -------------------------------------------------------


def test_filename_is_uuid_for_simple_layout() -> None:
    assert card.card_filename("u2", "normal", []) == "u2"


def test_filename_joins_sorted_faces_for_combined_layout() -> None:
    assert card.card_filename("u2", "split", ["u1", "u3"]) == "u1_u2_u3"


def test_filename_requires_related_uuids_for_combined_layout() -> None:
    with raises(AssertionError):
        card.card_filename("u2", "split", [])


def test_filename_does_not_mutate_related_uuids() -> None:
    related_uuids = ["u1", "u3"]
    card.card_filename("u2", "split", related_uuids)
    assert related_uuids == ["u1", "u3"]


# --- card_face -----------------------------------------------------------


def test_face_is_none_for_non_twosided_layout() -> None:
    assert card.card_face("normal", "a") is None


def test_face_is_front_for_side_a() -> None:
    assert card.card_face("transform", "a") == "front"


def test_face_is_back_for_side_b() -> None:
    assert card.card_face("transform", "b") == "back"


# --- build_card_fields ---------------------------------------------------


def test_build_card_fields_assembles_derived_facts() -> None:
    card_data = make_card(
        uuid="abc",
        layout="transform",
        identifiers={"scryfallId": "scry-1"},
        name="Delver of Secrets",
        side="a",
        otherFaceIds=["xyz"],
    )

    fields = card.build_card_fields(card_data, make_config())

    assert fields.uuid == "abc"
    assert fields.scryfall_id == "scry-1"
    assert fields.layout == "transform"
    assert fields.face == "front"
    assert fields.display_label == "abc | Delver of Secrets"
    assert fields.filename == "abc"
    assert fields.is_bad is False
