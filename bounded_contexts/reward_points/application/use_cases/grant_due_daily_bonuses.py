"""Write bonuses for days not yet granted into the ledger (ADR-0024).

The only use case that runs across families, and only the scheduled job calls it
(no user request reaches it). That is why it skips authorization — it acts on no
one's behalf, just keeps an agreed promise — and writes ``granted_by_membership_id``
as ``NULL``.

Writing the same day twice still yields one ledger row (the idempotency key carries
the date; :mod:`~bounded_contexts.reward_points.domain.entities.daily_bonus`). With
several workers, or after a crash and restart, nothing is granted twice.
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
    """Result of one pass.

    ``skipped`` is the number of days not granted because they exceeded the catch-up
    limit. When non-zero the caller logs it — dropping them silently would leave only
    the false assumption that bonuses are granted every day.
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
            # Not anyone's action, so there is no recorder; the screen shows "—"
            granted_by_membership_id=None,
            occurred_at=self._boundary.starts_at(day),
            idempotency_key=idempotency_key_for(day),
        )


__all__ = ["GrantDueDailyBonusesUseCase", "GrantedDailyBonuses"]
