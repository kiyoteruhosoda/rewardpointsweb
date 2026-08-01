"""家族（集約ルート）。

共有は家族への参加によってのみ表現する。メンバー単位の個別共有は持たない
（ADR-0009）。家族はデータ分離の明示的な境界で、台帳・参加者・招待はすべて
どれか 1 つの家族に属する。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from bounded_contexts.reward_points.domain.value_objects.family_name import FamilyName


@dataclass(frozen=True, kw_only=True)
class Family:
    id: int
    name: FamilyName
    created_at: datetime

    @property
    def name_value(self) -> str:
        return self.name.value


__all__ = ["Family"]
