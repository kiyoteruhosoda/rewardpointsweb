"""Output DTOs for events (ADR-0042)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

from bounded_contexts.reward_points.domain.entities.reward_event import RewardEvent


@dataclass(frozen=True, kw_only=True)
class StickerDTO:
    number: int
    stuck_at: datetime


@dataclass(frozen=True, kw_only=True)
class RewardEventDTO:
    id: int
    ledger_id: int
    title: str
    reward_points: int
    goal_count: int
    #: In ascending number order
    stickers: tuple[StickerDTO, ...]
    #: When all squares were filled; ``None`` if not yet
    completed_at: datetime | None
    created_at: datetime
    #: Achieved if filled by the end of this day; ``None`` if no deadline was set
    deadline: date | None
    #: Past the deadline and still not filled (judged by the family's day boundary)
    is_expired: bool


@dataclass(frozen=True, kw_only=True)
class RewardEventBoardDTO:
    """One child's events, returned with what the screen needs to decide what to show."""

    ledger_id: int
    display_name: str
    can_modify: bool
    events: tuple[RewardEventDTO, ...]


def to_dto(event: RewardEvent, *, today: date) -> RewardEventDTO:
    """*today* is today by the family's day boundary; used to judge expiry."""
    return RewardEventDTO(
        id=event.id,
        ledger_id=event.ledger_id,
        title=event.title.value,
        reward_points=event.reward.value,
        goal_count=event.goal_count,
        stickers=tuple(StickerDTO(number=s.number, stuck_at=s.stuck_at) for s in event.stickers),
        completed_at=event.completed_at,
        created_at=event.created_at,
        deadline=event.deadline,
        is_expired=event.is_expired(today),
    )


__all__ = ["RewardEventBoardDTO", "RewardEventDTO", "StickerDTO", "to_dto"]
