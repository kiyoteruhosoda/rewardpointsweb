"""Set up or stop the daily bonus (ADR-0024).

Only those who can modify the ledger (parents) may do this. The check goes through
``modifiable_ledger``, the same as recording to the ledger — this sets up a commitment
to add one row every day, so it is limited to those who can add a row by hand.

"Stop" only deletes the setting and leaves already granted points alone (the ledger is
append-only, ADR-0010). If there is no setting, it still succeeds silently — the wish to
stop is already satisfied.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from bounded_contexts.reward_points.application.dto.daily_bonus_dto import DailyBonusDTO, to_dto
from bounded_contexts.reward_points.application.family_access_resolver import FamilyAccessResolver
from bounded_contexts.reward_points.domain.repositories.daily_bonus_repository import (
    DailyBonusDraft,
    IDailyBonusRepository,
)
from bounded_contexts.reward_points.domain.services.day_boundary import DayBoundary
from shared.kernel.timestamps import utcnow


@dataclass(frozen=True, kw_only=True)
class ConfigureDailyBonusCommand:
    ledger_id: int
    account_id: int
    amount: int
    reason: str


class ConfigureDailyBonusUseCase:
    def __init__(
        self,
        access: FamilyAccessResolver,
        bonuses: IDailyBonusRepository,
        boundary: DayBoundary,
    ) -> None:
        self._access = access
        self._bonuses = bonuses
        self._boundary = boundary

    def execute(self, command: ConfigureDailyBonusCommand) -> DailyBonusDTO:
        found = self._access.modifiable_ledger(ledger_id=command.ledger_id, account_id=command.account_id)
        bonus = self._bonuses.save(
            DailyBonusDraft(
                ledger_id=found.ledger.id,
                amount=command.amount,
                reason=command.reason,
                starts_on=self._next_day(),
            )
        )
        return to_dto(bonus)

    def _next_day(self) -> date:
        """First grant day = **the day after it is set up**.

        Granting from the same day would make the result depend on the time of setup:
        set it in the morning and that day's points arrive minutes later; set it at
        23:50 and two days' worth land within 10 minutes. A single rule of "starting
        from the next date change" behaves the same whenever it is set, and matches the
        on-screen text (`dailyBonus.hint`).

        To grant on the same day too, add a row by hand. That way the intent ("added
        today for this reason") stays in the history.
        """
        return self._boundary.day_of(utcnow()) + timedelta(days=1)


class StopDailyBonusUseCase:
    def __init__(self, access: FamilyAccessResolver, bonuses: IDailyBonusRepository) -> None:
        self._access = access
        self._bonuses = bonuses

    def execute(self, *, ledger_id: int, account_id: int) -> None:
        found = self._access.modifiable_ledger(ledger_id=ledger_id, account_id=account_id)
        self._bonuses.delete_by_ledger(found.ledger.id)


__all__ = ["ConfigureDailyBonusCommand", "ConfigureDailyBonusUseCase", "StopDailyBonusUseCase"]
