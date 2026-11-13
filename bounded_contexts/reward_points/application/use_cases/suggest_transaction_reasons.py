"""Return the reasons frequently used in the family.

These are suggestions so the same wording need not be retyped every time; authorization
is per family. Reasons from other families never mix in (the repository filters by ``family_id``).

Only parents call this. Reason texts may come from other children's records, which would
conflict with privacy between siblings (ADR-0009), so they are not returned to children.
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
