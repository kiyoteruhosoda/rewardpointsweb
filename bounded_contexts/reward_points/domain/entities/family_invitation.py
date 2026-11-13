"""An invitation to a family.

The code is stored hashed (the plaintext is returned only once, when issued;
the actual hashing is Infrastructure's job). A ``role = child`` invitation
points, via ``target_membership_id``, to the member a parent created
beforehand (ADR-0009 / ADR-0011).
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
