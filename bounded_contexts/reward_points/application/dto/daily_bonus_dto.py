"""毎日のボーナスの出力 DTO（ADR-0024）。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from bounded_contexts.reward_points.domain.entities.daily_bonus import DailyBonus


@dataclass(frozen=True, kw_only=True)
class DailyBonusDTO:
    ledger_id: int
    amount: int
    reason: str
    starts_on: date
    #: 渡し終えた最後の日。まだ 1 日も渡していなければ ``None``
    granted_through: date | None


def to_dto(bonus: DailyBonus) -> DailyBonusDTO:
    return DailyBonusDTO(
        ledger_id=bonus.ledger_id,
        amount=bonus.amount.value,
        reason=bonus.reason.value,
        starts_on=bonus.starts_on,
        granted_through=bonus.granted_through,
    )


__all__ = ["DailyBonusDTO", "to_dto"]
