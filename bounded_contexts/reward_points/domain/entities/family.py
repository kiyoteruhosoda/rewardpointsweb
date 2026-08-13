"""家族（集約ルート）。

共有は家族への参加によってのみ表現する。メンバー単位の個別共有は持たない
（ADR-0009）。家族はデータ分離の明示的な境界で、台帳・参加者・招待はすべて
どれか 1 つの家族に属する。

家族で決めた約束ごと（``rules``）も家族が持つ。子ども一人ひとりではなく家族に
1 つで、参加している全員が同じ文面を読む（ADR-0027）。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from bounded_contexts.reward_points.domain.value_objects.family_name import FamilyName
from bounded_contexts.reward_points.domain.value_objects.family_rules import FamilyRules


@dataclass(frozen=True, kw_only=True)
class Family:
    id: int
    name: FamilyName
    #: 家族のルール。まだ書いていなければ ``None``（空文字とは区別する）
    rules: FamilyRules | None
    created_at: datetime

    @property
    def name_value(self) -> str:
        return self.name.value

    @property
    def rules_value(self) -> str | None:
        return self.rules.value if self.rules else None


__all__ = ["Family"]
