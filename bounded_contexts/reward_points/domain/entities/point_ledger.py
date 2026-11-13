"""Point ledger.

Exists one-to-one for each membership with ``role = child`` (ADR-0009). It holds no
balance; the balance is derived as the sum of transactions (ADR-0010, :class:`LedgerStatement`).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, kw_only=True)
class PointLedger:
    id: int
    family_id: int
    membership_id: int
    created_at: datetime

    def belongs_to_family(self, family_id: int) -> bool:
        return self.family_id == family_id


__all__ = ["PointLedger"]
