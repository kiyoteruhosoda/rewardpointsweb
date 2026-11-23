"""How a pet feels about the care it gets (ADR-0061, task #1128).

Pure rules: the cares and the moment are passed in directly.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from bounded_contexts.reward_points.domain.entities.pet import STAGE_THRESHOLDS, PetGrowth
from bounded_contexts.reward_points.domain.entities.pet_care import (
    CARE_COOLDOWN,
    CARE_FADES_OVER,
    CARE_GAIN,
    MOOD_MAX,
    PetCare,
    PetCareKind,
    PetMoodLevel,
    is_recorded_again,
    mood_at,
)

NOW = datetime(2026, 11, 23, 12, 0, 0)


def _care(hours_ago: float, kind: PetCareKind = PetCareKind.FEED) -> PetCare:
    return PetCare(kind=kind, cared_at=NOW - timedelta(hours=hours_ago))


def test_a_pet_never_cared_for_is_calm_not_lonely() -> None:
    mood = mood_at(NOW, [], ever_cared=False)

    assert (mood.value, mood.level) == (0, PetMoodLevel.CALM)


def test_a_care_just_given_adds_its_full_gain() -> None:
    assert mood_at(NOW, [_care(0)], ever_cared=True).value == CARE_GAIN


def test_a_care_fades_in_a_straight_line() -> None:
    half_way = CARE_FADES_OVER / 2

    mood = mood_at(NOW, [PetCare(kind=PetCareKind.PAT, cared_at=NOW - half_way)], ever_cared=True)

    assert mood.value == round(CARE_GAIN / 2)


def test_a_care_older_than_the_fade_adds_nothing() -> None:
    old = PetCare(kind=PetCareKind.PLAY, cared_at=NOW - CARE_FADES_OVER - timedelta(minutes=1))

    assert mood_at(NOW, [old], ever_cared=True).value == 0


def test_every_kind_at_once_makes_a_happy_pet_capped_at_the_maximum() -> None:
    cares = [_care(0, kind) for kind in PetCareKind] * 2

    mood = mood_at(NOW, cares, ever_cared=True)

    assert (mood.value, mood.level) == (MOOD_MAX, PetMoodLevel.HAPPY)


def test_a_pet_left_alone_for_a_day_and_a_half_looks_lonely() -> None:
    cares = [_care(40, kind) for kind in PetCareKind]

    assert mood_at(NOW, cares, ever_cared=True).level == PetMoodLevel.LONELY


def test_a_pet_cared_for_every_day_never_looks_lonely() -> None:
    cares = [_care(24, kind) for kind in PetCareKind]

    assert mood_at(NOW, cares, ever_cared=True).level == PetMoodLevel.CALM


def test_the_same_kind_is_recorded_again_only_after_the_cooldown() -> None:
    assert is_recorded_again(None, NOW)
    assert not is_recorded_again(NOW - CARE_COOLDOWN + timedelta(seconds=1), NOW)
    assert is_recorded_again(NOW - CARE_COOLDOWN, NOW)


def test_only_a_hatched_pet_counts_as_hatched() -> None:
    assert not PetGrowth(earned=0).has_hatched
    assert PetGrowth(earned=STAGE_THRESHOLDS[1]).has_hatched
