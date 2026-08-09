"""まだ渡していない日のボーナスを台帳へ書く（ADR-0024）。

家族を跨いで回る唯一のユースケースで、呼ぶのは定期実行だけ（利用者の要求から
呼ばれる口は無い）。認可を通さないのはそのため — 誰の代理でもなく、決まった
約束を果たしているだけなので、``granted_by_membership_id`` も ``NULL`` で書く。

同じ日を 2 度書こうとしても台帳には 1 行しか入らない（冪等キーが日付を持つ。
:mod:`~bounded_contexts.reward_points.domain.entities.daily_bonus`）。ワーカーが
複数あっても、途中で落ちて再開しても、二重に渡ることは無い。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

from bounded_contexts.reward_points.domain.entities.daily_bonus import DailyBonus, idempotency_key_for
from bounded_contexts.reward_points.domain.repositories.daily_bonus_repository import IDailyBonusRepository
from bounded_contexts.reward_points.domain.repositories.point_transaction_repository import (
    IPointTransactionRepository,
    NewTransaction,
)
from bounded_contexts.reward_points.domain.services.day_boundary import DayBoundary


@dataclass(frozen=True, kw_only=True)
class GrantedDailyBonuses:
    """1 周分の結果。

    ``skipped`` は遡る上限を超えて渡さなかった日数。0 でないときは呼び出し側が
    ログへ残す — 黙って切り捨てると「毎日渡している」という前提だけが残る。
    """

    granted: int
    skipped: int


class GrantDueDailyBonusesUseCase:
    def __init__(
        self,
        *,
        bonuses: IDailyBonusRepository,
        transactions: IPointTransactionRepository,
        boundary: DayBoundary,
        max_catch_up_days: int,
    ) -> None:
        self._bonuses = bonuses
        self._transactions = transactions
        self._boundary = boundary
        self._max_catch_up_days = max_catch_up_days

    def execute(self, *, now: datetime) -> GrantedDailyBonuses:
        today = self._boundary.day_of(now)
        granted = 0
        skipped = 0
        for bonus in self._bonuses.list_due(today):
            due = bonus.due_days(today=today, limit=self._max_catch_up_days)
            skipped += due.skipped
            if not due.days:
                continue
            for day in due.days:
                self._transactions.append(self._entry_for(bonus, day))
                granted += 1
            self._bonuses.mark_granted_through(bonus_id=bonus.id, day=due.days[-1])
        return GrantedDailyBonuses(granted=granted, skipped=skipped)

    def _entry_for(self, bonus: DailyBonus, day: date) -> NewTransaction:
        return NewTransaction(
            ledger_id=bonus.ledger_id,
            amount=bonus.amount.value,
            reason=bonus.reason.value,
            # 誰かの操作ではないので記録者を持たない。画面では「—」で出る
            granted_by_membership_id=None,
            occurred_at=self._boundary.starts_at(day),
            idempotency_key=idempotency_key_for(day),
        )


__all__ = ["GrantDueDailyBonusesUseCase", "GrantedDailyBonuses"]
