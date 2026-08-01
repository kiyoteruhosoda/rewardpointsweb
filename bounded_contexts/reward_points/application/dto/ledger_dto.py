"""台帳・トランザクションの出力 DTO。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, kw_only=True)
class TransactionDTO:
    id: int
    amount: int
    reason: str
    occurred_at: datetime
    created_at: datetime
    # 打ち消しレコードなら、打ち消した相手の ID
    reversal_of_id: int | None
    # このレコードが打ち消されているか（UI は対で表示する）
    is_reversed: bool
    granted_by: str | None


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


__all__ = ["LedgerDTO", "TransactionDTO"]
