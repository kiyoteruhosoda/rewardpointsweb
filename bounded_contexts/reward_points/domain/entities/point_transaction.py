"""台帳への 1 行（追記専用）。

UPDATE も DELETE も行わない。訂正は逆符号の行を追加して表す（ADR-0010）。
打ち消しの組み立ては :meth:`PointTransaction.plan_reversal` に閉じ込め、符号の
反転と「打ち消しは打ち消せない」規則を呼び出し側へ散らさない。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from bounded_contexts.reward_points.domain.exceptions import ReversalOfReversalError
from bounded_contexts.reward_points.domain.value_objects.point_amount import PointAmount
from bounded_contexts.reward_points.domain.value_objects.transaction_reason import TransactionReason


@dataclass(frozen=True, kw_only=True)
class ReversalDraft:
    """まだ台帳へ書かれていない打ち消し行。"""

    ledger_id: int
    amount: PointAmount
    reason: TransactionReason
    reversal_of_id: int


@dataclass(frozen=True, kw_only=True)
class PointTransaction:
    id: int
    ledger_id: int
    amount: PointAmount
    reason: TransactionReason
    # 操作を行った参加者。参加者が家族を離れても記録は残す
    granted_by_membership_id: int | None
    # 出来事の発生日時（遡って入力できる）と、レコードの作成日時は別物
    occurred_at: datetime
    created_at: datetime
    reversal_of_id: int | None

    @property
    def is_reversal(self) -> bool:
        return self.reversal_of_id is not None

    @property
    def signed_points(self) -> int:
        return self.amount.value

    def plan_reversal(self) -> ReversalDraft:
        """この行を打ち消す行の内容。理由は元の行から引き継ぐ。"""
        if self.is_reversal:
            raise ReversalOfReversalError
        return ReversalDraft(
            ledger_id=self.ledger_id,
            amount=self.amount.negated,
            reason=self.reason,
            reversal_of_id=self.id,
        )


__all__ = ["PointTransaction", "ReversalDraft"]
