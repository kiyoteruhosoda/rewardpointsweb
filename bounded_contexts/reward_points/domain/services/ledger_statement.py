"""台帳の読み取り結果（履歴と、そこから決まる残高）。

残高は保持せず ``SUM(amount)`` で導出する。有効期限・期間リセットが無いため
集計対象は常に台帳の全レコードで、スナップショットも失効ジョブも要らない
（ADR-0010）。

打ち消し済みの ID をここで一度だけ数え上げ、画面が「取り消された事実」を
1 行ずつ引き直さずに表示できるようにする。
"""

from __future__ import annotations

from collections.abc import Sequence

from bounded_contexts.reward_points.domain.entities.point_transaction import PointTransaction
from bounded_contexts.reward_points.domain.value_objects.point_balance import PointBalance


class LedgerStatement:
    def __init__(self, transactions: Sequence[PointTransaction]) -> None:
        self._transactions = tuple(transactions)

    @property
    def transactions(self) -> tuple[PointTransaction, ...]:
        """渡された順のまま返す（並び順の決定はリポジトリの責務）。"""
        return self._transactions

    @property
    def balance(self) -> PointBalance:
        return PointBalance(sum(transaction.signed_points for transaction in self._transactions))

    @property
    def reversed_transaction_ids(self) -> frozenset[int]:
        """打ち消された側の ID。UI は対で表示するためにこれを使う。"""
        return frozenset(
            transaction.reversal_of_id for transaction in self._transactions if transaction.reversal_of_id is not None
        )


__all__ = ["LedgerStatement"]
