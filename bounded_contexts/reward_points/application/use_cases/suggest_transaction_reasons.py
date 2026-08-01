"""その家族でよく使われている理由を返す。

同じ言い回しを毎回打ち直さずに済ませるための候補で、認可の単位は家族。
他家族の理由は混ざらない（リポジトリが ``family_id`` で絞る）。

親だけが呼ぶ。理由の文言は他の子の記録から来ることがあり、兄弟間の非公開
（ADR-0009）と噛み合わないため、子には返さない。
"""

from __future__ import annotations

from bounded_contexts.reward_points.application.family_access_resolver import FamilyAccessResolver
from bounded_contexts.reward_points.domain.repositories.point_transaction_repository import (
    IPointTransactionRepository,
)

MAX_SUGGESTIONS = 10


class SuggestTransactionReasonsUseCase:
    def __init__(self, access: FamilyAccessResolver, transactions: IPointTransactionRepository) -> None:
        self._access = access
        self._transactions = transactions

    def execute(self, *, family_id: int, account_id: int) -> list[str]:
        self._access.require_guardian(family_id=family_id, account_id=account_id)
        return self._transactions.frequent_reasons(family_id=family_id, limit=MAX_SUGGESTIONS)


__all__ = ["MAX_SUGGESTIONS", "SuggestTransactionReasonsUseCase"]
