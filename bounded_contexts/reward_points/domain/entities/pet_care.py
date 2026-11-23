"""Caring for a hatched pet (ADR-0061, task #1128).

Care is free and never touches growth: growth still comes only from the points earned. What
care changes is how the pet feels:

- **Mood** (0..100) is made of the recent cares. Each care adds :data:`CARE_GAIN`, and its share
  fades in a straight line to nothing over :data:`CARE_FADES_OVER`. The sum is capped at
  :data:`MOOD_MAX`. A pet left alone for a while looks lonely — that is all. It never weakens,
  shrinks or leaves (no penalty).
- **Friendship** is the number of days on which the pet was cared for. It only goes up.

A pet that has never been cared for is calm rather than lonely: it has not yet learnt to miss
anyone. The same kind of care within :data:`CARE_COOLDOWN` of the last one is not recorded again
(the screen still plays it), so tapping a button over and over neither fills the mood at once
nor fills the table.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum


class PetCareKind(Enum):
    FEED = "feed"
    PAT = "pat"
    PLAY = "play"
    BATH = "bath"


class PetMoodLevel(Enum):
    LONELY = "lonely"
    CALM = "calm"
    HAPPY = "happy"


#: What one care adds to the mood when it has just happened
CARE_GAIN = 25
MOOD_MAX = 100
#: A care's share of the mood fades to nothing over this long. Cared for once a day, the pet
#: stays calm or better; a day and a half without care makes it lonely
CARE_FADES_OVER = timedelta(hours=48)
#: Below this the pet looks lonely
LONELY_BELOW = 20
#: From this up the pet looks happy
HAPPY_FROM = 70
#: The same kind of care is recorded at most once in this span
CARE_COOLDOWN = timedelta(minutes=30)


@dataclass(frozen=True, kw_only=True)
class PetCare:
    """One recorded care."""

    kind: PetCareKind
    cared_at: datetime


@dataclass(frozen=True, kw_only=True)
class PetMood:
    value: int
    level: PetMoodLevel


def mood_at(now: datetime, recent: Sequence[PetCare], *, ever_cared: bool) -> PetMood:
    """The mood at *now* from the cares in the last :data:`CARE_FADES_OVER` (*recent*).

    Cares older than that may be passed too; they add nothing.
    """
    total = sum(_share_of(care, now) for care in recent)
    value = min(MOOD_MAX, round(total))
    return PetMood(value=value, level=_level_of(value, ever_cared=ever_cared))


def is_recorded_again(last_of_kind: datetime | None, now: datetime) -> bool:
    """Whether a care of a kind last given at *last_of_kind* is recorded at *now*."""
    return last_of_kind is None or now - last_of_kind >= CARE_COOLDOWN


def _share_of(care: PetCare, now: datetime) -> float:
    age = max(timedelta(0), now - care.cared_at)
    remaining = 1 - age / CARE_FADES_OVER
    return CARE_GAIN * max(0.0, remaining)


def _level_of(value: int, *, ever_cared: bool) -> PetMoodLevel:
    if value >= HAPPY_FROM:
        return PetMoodLevel.HAPPY
    if value < LONELY_BELOW and ever_cared:
        return PetMoodLevel.LONELY
    return PetMoodLevel.CALM


__all__ = [
    "CARE_COOLDOWN",
    "CARE_FADES_OVER",
    "CARE_GAIN",
    "HAPPY_FROM",
    "LONELY_BELOW",
    "MOOD_MAX",
    "PetCare",
    "PetCareKind",
    "PetMood",
    "PetMoodLevel",
    "is_recorded_again",
    "mood_at",
]
