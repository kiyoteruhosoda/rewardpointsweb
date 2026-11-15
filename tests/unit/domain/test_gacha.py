"""Gacha machines (ADR-0060): what a parent may set up, and how a roll picks a prize."""

from __future__ import annotations

import pytest

from bounded_contexts.reward_points.domain.entities.gacha import (
    MAX_PRIZES,
    MAX_WEIGHT,
    NAME_MAX_LENGTH,
    GachaDesign,
    GachaPrize,
    draw_ledger_key,
    ledger_reason,
)
from bounded_contexts.reward_points.domain.exceptions import GachaNeedsAPrizeError
from bounded_contexts.reward_points.domain.value_objects.idempotency_key import is_derived


def _design(*prizes: GachaPrize, price: int = 30) -> GachaDesign:
    return GachaDesign(name="おかしガチャ", price=price, prizes=prizes)


def test_a_roll_lands_on_prizes_in_ranges_as_wide_as_their_weight() -> None:
    design = _design(
        GachaPrize(name="チョコ", weight=1),
        GachaPrize(name="グミ", weight=3),
        GachaPrize(name="はずれ", weight=2, is_miss=True),
    )

    assert design.total_weight == 6
    assert [design.pick(roll).name for roll in range(6)] == ["チョコ", "グミ", "グミ", "グミ", "はずれ", "はずれ"]


@pytest.mark.parametrize("roll", [-1, 6])
def test_a_roll_outside_the_total_weight_is_refused(roll: int) -> None:
    design = _design(GachaPrize(name="チョコ", weight=1), GachaPrize(name="グミ", weight=5))

    with pytest.raises(ValueError, match="Roll"):
        design.pick(roll)


def test_a_machine_of_only_misses_is_refused() -> None:
    with pytest.raises(GachaNeedsAPrizeError):
        _design(GachaPrize(name="はずれ", weight=1, is_miss=True))


@pytest.mark.parametrize("price", [0, -10])
def test_a_machine_must_cost_something(price: int) -> None:
    with pytest.raises(ValueError, match="price"):
        _design(GachaPrize(name="チョコ", weight=1), price=price)


def test_a_machine_holds_one_to_max_prizes() -> None:
    with pytest.raises(ValueError, match="prizes"):
        _design()
    with pytest.raises(ValueError, match="prizes"):
        _design(*(GachaPrize(name=f"p{i}", weight=1) for i in range(MAX_PRIZES + 1)))


@pytest.mark.parametrize("weight", [0, MAX_WEIGHT + 1])
def test_a_prize_weight_stays_in_range(weight: int) -> None:
    with pytest.raises(ValueError, match="weight"):
        GachaPrize(name="チョコ", weight=weight)


@pytest.mark.parametrize("name", [" ", "あ" * (NAME_MAX_LENGTH + 1)])
def test_a_prize_needs_a_short_name(name: str) -> None:
    with pytest.raises(ValueError, match="Prize name"):
        GachaPrize(name=name, weight=1)


def test_the_ledger_row_names_the_machine_and_the_prize() -> None:
    assert ledger_reason(gacha_name="おかしガチャ", prize_name="チョコ") == "おかしガチャ: チョコ"


def test_the_ledger_key_of_a_draw_is_derived_so_it_cannot_collide_with_hand_written_rows() -> None:
    key = draw_ledger_key("press-1")

    assert key == "press-1#gacha"
    assert is_derived(key)
