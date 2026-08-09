"""台帳・トランザクションの出力 DTO。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from bounded_contexts.reward_points.application.dto.daily_bonus_dto import DailyBonusDTO
from bounded_contexts.reward_points.domain.entities.point_transaction import PointTransaction


@dataclass(frozen=True, kw_only=True)
class TransactionDTO:
    id: int
    amount: int
    reason: str
    occurred_at: datetime
    created_at: datetime
    # 打ち消しレコードなら、打ち消した相手の ID
    reversal_of_id: int | None
    # 訂正後のレコードなら、言い直した相手の ID（ADR-0022）
    corrects_id: int | None
    # このレコードが打ち消されているか（UI は対で表示する）
    is_reversed: bool
    granted_by: str | None


@dataclass(frozen=True, kw_only=True)
class CorrectionDTO:
    """1 回の訂正で台帳に足された 2 行（ADR-0022）。"""

    reversal: TransactionDTO
    correction: TransactionDTO


@dataclass(frozen=True, kw_only=True)
class LedgerDTO:
    ledger_id: int
    family_id: int
    membership_id: int
    display_name: str
    balance: int
    # 画面が変更 UI を出すかはこの 1 つの値で決める（role 名で分岐しない）
    can_modify: bool
    transactions: tuple[TransactionDTO, ...]
    # 毎日のボーナスの設定（ADR-0024）。決めていなければ ``None``
    daily_bonus: DailyBonusDTO | None


def just_written(transaction: PointTransaction, *, granted_by: str | None) -> TransactionDTO:
    """書き込んだ直後の 1 行。

    追記した本人へ返すためのもので、``is_reversed`` は常に偽になる（書いた
    そばから打ち消されている行は無い）。台帳を読み直すときの組み立ては
    ``ViewPointLedgerUseCase`` が別に行う（そちらは打ち消し済みかを台帳全体から
    決める）。
    """
    return TransactionDTO(
        id=transaction.id,
        amount=transaction.amount.value,
        reason=transaction.reason.value,
        occurred_at=transaction.occurred_at,
        created_at=transaction.created_at,
        reversal_of_id=transaction.reversal_of_id,
        corrects_id=transaction.corrects_id,
        is_reversed=False,
        granted_by=granted_by,
    )


__all__ = ["CorrectionDTO", "LedgerDTO", "TransactionDTO", "just_written"]
