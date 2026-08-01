"""家族への参加（誰が、どの立場で入っているか）。

``account_id`` は ``None`` を取りうる。親が子の参加を先に作り、子が招待コードで
アカウントを作った時点で結び付くため（ADR-0011）。同一家族では 1 アカウント
1 参加（``UNIQUE (family_id, account_id)``）。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from bounded_contexts.reward_points.domain.value_objects.display_name import DisplayName
from bounded_contexts.reward_points.domain.value_objects.family_role import FamilyRole


@dataclass(frozen=True, kw_only=True)
class FamilyMembership:
    id: int
    family_id: int
    account_id: int | None
    role: FamilyRole
    display_name: DisplayName
    created_at: datetime
    # 親メンバーが独立を指示した日時（ADR-0014）。role = child 以外では常に None
    independence_proposed_at: datetime | None = None
    # 家族の中での並び順。小さいほど先に出す。同じ値なら作られた順（ID）に落ちる
    display_order: int = 0

    @property
    def display_name_value(self) -> str:
        return self.display_name.value

    @property
    def is_linked(self) -> bool:
        """アカウントと結び付いているか（結び付くまで本人はログインできない）。"""
        return self.account_id is not None

    @property
    def independence_proposed(self) -> bool:
        """独立が指示され、子本人の承認を待っているか（ADR-0014）。"""
        return self.independence_proposed_at is not None

    def is_held_by(self, account_id: int) -> bool:
        return self.account_id is not None and self.account_id == account_id


__all__ = ["FamilyMembership"]
