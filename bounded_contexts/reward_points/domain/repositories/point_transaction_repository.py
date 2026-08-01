"""台帳トランザクションの永続化インターフェース。

追記専用のため、更新・削除の口は用意しない（ADR-0010）。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime

from bounded_contexts.reward_points.domain.entities.point_transaction import PointTransaction


@dataclass(frozen=True, kw_only=True)
class NewTransaction:
    """まだ台帳へ書かれていない 1 行。

    書き込みに必要な値をまとめて 1 つの引数にする（加算・消費・打ち消しで
    渡すものが同じなので、書き込み口も 1 つで足りる）。
    """

    ledger_id: int
    amount: int
    reason: str
    granted_by_membership_id: int
    occurred_at: datetime
    idempotency_key: str
    reversal_of_id: int | None = None


class IPointTransactionRepository(ABC):
    @abstractmethod
    def list_by_ledger(self, ledger_id: int) -> list[PointTransaction]:
        """発生日時の新しい順。"""

    @abstractmethod
    def list_by_ledgers(self, ledger_ids: Sequence[int]) -> Mapping[int, list[PointTransaction]]:
        """台帳 ID -> 履歴。一覧の残高計算で 1 件ずつ引かないための入口。"""

    @abstractmethod
    def find_in_ledger(self, *, ledger_id: int, transaction_id: int) -> PointTransaction | None: ...

    @abstractmethod
    def find_reversal_of(self, transaction_id: int) -> PointTransaction | None:
        """すでに打ち消されているかを調べる（``reversal_of_id`` は UNIQUE）。"""

    @abstractmethod
    def append(self, new_transaction: NewTransaction) -> PointTransaction:
        """1 行追記する。

        ``UNIQUE (ledger_id, idempotency_key)`` に抵触した場合はエラーとせず、
        既存のレコードを返す（ADR-0010）。
        """

    @abstractmethod
    def count_by_ledger(self, ledger_id: int) -> int: ...


__all__ = ["IPointTransactionRepository", "NewTransaction"]
