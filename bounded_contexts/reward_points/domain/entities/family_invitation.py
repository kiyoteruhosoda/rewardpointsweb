"""家族への招待。

コードはハッシュ化して保存する（平文は発行時に 1 度だけ返す。実際のハッシュ化は
Infrastructure の責務）。``role = child`` の招待では、親が先に作った参加者を
``target_membership_id`` で指す（ADR-0009 / ADR-0011）。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from bounded_contexts.reward_points.domain.value_objects.family_role import FamilyRole


@dataclass(frozen=True, kw_only=True)
class FamilyInvitation:
    id: int
    family_id: int
    role: FamilyRole
    target_membership_id: int | None
    expires_at: datetime
    used_at: datetime | None
    created_at: datetime

    def is_usable_at(self, moment: datetime) -> bool:
        return self.used_at is None and moment < self.expires_at


__all__ = ["FamilyInvitation"]
