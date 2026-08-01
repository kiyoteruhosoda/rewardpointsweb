"""ポイント台帳。

``role = child`` の参加者に対して 1 対 1 で存在する（ADR-0009）。残高は持たず、
トランザクションの合計として導出する（ADR-0010、:class:`LedgerStatement`）。
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
