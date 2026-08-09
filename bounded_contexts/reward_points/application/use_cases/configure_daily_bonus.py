"""毎日のボーナスを決める・やめる（ADR-0024）。

台帳を変更できる立場（親）だけが触れる。判定は台帳への記録と同じ
``modifiable_ledger`` に通す — 毎日 1 行足す約束を結ぶ操作なので、手で 1 行
足せる人と同じ範囲に置く。

「やめる」は設定を消すだけで、渡し終えたポイントには触れない（台帳は追記専用。
ADR-0010）。すでに設定が無いときも黙って成功させる — やめたいという求めは
すでに満たされている。
"""

from __future__ import annotations

from dataclasses import dataclass

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
        # 決めた日から渡し始める。遡って渡すと、設定した瞬間に身に覚えのない
        # 行が並ぶ（過去の分を足したいなら、手で 1 行書く方が意図が残る）
        bonus = self._bonuses.save(
            DailyBonusDraft(
                ledger_id=found.ledger.id,
                amount=command.amount,
                reason=command.reason,
                starts_on=self._boundary.day_of(utcnow()),
            )
        )
        return to_dto(bonus)


class StopDailyBonusUseCase:
    def __init__(self, access: FamilyAccessResolver, bonuses: IDailyBonusRepository) -> None:
        self._access = access
        self._bonuses = bonuses

    def execute(self, *, ledger_id: int, account_id: int) -> None:
        found = self._access.modifiable_ledger(ledger_id=ledger_id, account_id=account_id)
        self._bonuses.delete_by_ledger(found.ledger.id)


__all__ = ["ConfigureDailyBonusCommand", "ConfigureDailyBonusUseCase", "StopDailyBonusUseCase"]
