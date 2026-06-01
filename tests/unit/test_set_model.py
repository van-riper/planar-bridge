"""Tests for the pure per-set derivations in domain/set_model.py."""

from typing import Any

from planar_bridge.config.loader import AppConfig
from planar_bridge.domain import set_model


def make_config(**overrides: Any) -> AppConfig:
    """An AppConfig with permissive defaults, overridable per test."""

    base: dict[str, Any] = {
        "pull_reprints": False,
        "card_language": "English",
        "pardoned_sets": frozenset(),
        "exempt_sets": frozenset(),
        "exempt_promos": frozenset(),
        "exempt_types": frozenset(),
    }
    base.update(overrides)
    return AppConfig(**base)


def make_set(**overrides: Any) -> dict[str, Any]:
    """A minimal, non-omitted MTGJSON set entry, overridable per test."""

    base: dict[str, Any] = {
        "code": "XLN",
        "type": "expansion",
        "cards": [],
        "tokens": [],
    }
    base.update(overrides)
    return base


# --- set_is_omitted ------------------------------------------------------


def test_clean_set_is_not_omitted() -> None:
    """A default expansion set is kept rather than omitted."""

    assert set_model.set_is_omitted(make_set(), make_config()) is False


def test_exempt_type_is_omitted() -> None:
    """A set whose type is exempt is omitted."""

    set_data = make_set(type="funny")
    config = make_config(exempt_types=frozenset({"funny"}))
    assert set_model.set_is_omitted(set_data, config) is True


def test_exempt_set_code_is_omitted() -> None:
    """A set whose code is exempt is omitted."""

    set_data = make_set(code="MB1")
    config = make_config(exempt_sets=frozenset({"MB1"}))
    assert set_model.set_is_omitted(set_data, config) is True


def test_foreign_only_is_omitted() -> None:
    """A foreign-only set is omitted."""

    set_data = make_set(isForeignOnly=True)
    assert set_model.set_is_omitted(set_data, make_config()) is True


def test_online_only_is_omitted() -> None:
    """An online-only set is omitted."""

    set_data = make_set(isOnlineOnly=True)
    assert set_model.set_is_omitted(set_data, make_config()) is True


def test_pardoned_set_overrides_exemption() -> None:
    """A pardoned set is kept even when its type is exempt."""

    set_data = make_set(code="30A", type="funny")
    config = make_config(
        exempt_types=frozenset({"funny"}),
        pardoned_sets=frozenset({"30A"}),
    )
    assert set_model.set_is_omitted(set_data, config) is False


# --- merge_card_entries --------------------------------------------------


def test_merges_cards_then_tokens_in_order() -> None:
    """Merging yields cards first, then tokens, preserving order."""

    set_data = make_set(
        cards=[{"uuid": "c1"}, {"uuid": "c2"}],
        tokens=[{"uuid": "t1"}],
    )
    merged = set_model.merge_card_entries(set_data)
    assert [entry["uuid"] for entry in merged] == ["c1", "c2", "t1"]


def test_merges_with_no_tokens() -> None:
    """Merging a set with no tokens returns just its cards."""

    set_data = make_set(cards=[{"uuid": "c1"}], tokens=[])
    merged = set_model.merge_card_entries(set_data)
    assert [entry["uuid"] for entry in merged] == ["c1"]


# --- build_set_record ----------------------------------------------------


def test_build_set_record_assembles_derived_facts() -> None:
    """build_set_record collects every derived per-set fact."""

    set_data = make_set(
        code="XLN",
        type="expansion",
        cards=[{"uuid": "c1"}],
        tokens=[{"uuid": "t1"}],
    )

    record = set_model.build_set_record(set_data, make_config())

    assert record.set_code == "XLN"
    assert record.is_omitted is False
    assert record.card_entries == ({"uuid": "c1"}, {"uuid": "t1"})
