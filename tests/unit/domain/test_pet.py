"""How a pet grows with points ever earned (ADR-0061)."""

from __future__ import annotations

import pytest

from bounded_contexts.reward_points.domain.entities.pet import STAGE_THRESHOLDS, PetGrowth


def test_a_new_pet_is_an_egg() -> None:
    growth = PetGrowth(earned=0)

    assert growth.stage == 0
    assert growth.next_threshold == STAGE_THRESHOLDS[1]
    assert growth.points_to_next == STAGE_THRESHOLDS[1]


@pytest.mark.parametrize("stage", range(len(STAGE_THRESHOLDS)))
def test_a_pet_reaches_each_stage_exactly_at_its_threshold(stage: int) -> None:
    threshold = STAGE_THRESHOLDS[stage]

    assert PetGrowth(earned=threshold).stage == stage
    if stage > 0:
        assert PetGrowth(earned=threshold - 1).stage == stage - 1


def test_the_final_stage_has_nothing_further() -> None:
    growth = PetGrowth(earned=STAGE_THRESHOLDS[-1] * 10)

    assert growth.is_final
    assert growth.next_threshold is None
    assert growth.points_to_next is None


def test_points_to_the_next_stage_count_down_from_the_earned_total() -> None:
    growth = PetGrowth(earned=STAGE_THRESHOLDS[1] + 5)

    assert growth.current_threshold == STAGE_THRESHOLDS[1]
    assert growth.points_to_next == STAGE_THRESHOLDS[2] - STAGE_THRESHOLDS[1] - 5
