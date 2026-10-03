"""イベントの出力 DTO（ADR-0042）。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

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
    #: 番号の小さい順
    stickers: tuple[StickerDTO, ...]
    #: マスが埋まった日時。まだなら ``None``
    completed_at: datetime | None
    created_at: datetime


@dataclass(frozen=True, kw_only=True)
class RewardEventBoardDTO:
    """1 人の子のイベント一覧。画面の出し分けに要るものを一緒に返す。"""

    ledger_id: int
    display_name: str
    can_modify: bool
    events: tuple[RewardEventDTO, ...]


def to_dto(event: RewardEvent) -> RewardEventDTO:
    return RewardEventDTO(
        id=event.id,
        ledger_id=event.ledger_id,
        title=event.title.value,
        reward_points=event.reward.value,
        goal_count=event.goal_count,
        stickers=tuple(StickerDTO(number=s.number, stuck_at=s.stuck_at) for s in event.stickers),
        completed_at=event.completed_at,
        created_at=event.created_at,
    )


__all__ = ["RewardEventBoardDTO", "RewardEventDTO", "StickerDTO", "to_dto"]
