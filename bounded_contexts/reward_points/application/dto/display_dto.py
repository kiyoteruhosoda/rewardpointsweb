"""表示端末（ADR-0047）の出力 DTO。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, kw_only=True)
class DisplayDTO:
    """家族を映している表示端末 1 台。1 端末 = 1 アカウント = 1 参加。"""

    account_id: int
    membership_id: int
    family_id: int
    family_name: str
    #: 端末の名前（例「リビング」）。家族の参加者一覧にもこの名前で並ぶ
    name: str
    created_at: datetime


@dataclass(frozen=True, kw_only=True)
class DisplayableFamilyDTO:
    """運用管理者が映す先として選べる家族。名前だけで、台帳は載せない。"""

    id: int
    name: str


__all__ = ["DisplayDTO", "DisplayableFamilyDTO"]
