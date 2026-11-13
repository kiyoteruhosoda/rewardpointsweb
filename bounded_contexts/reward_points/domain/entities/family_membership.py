"""Membership in a family (who belongs, and in which role).

``account_id`` may be ``None``: a parent creates the child's membership first, and it is
linked when the child creates an account with an invitation code (ADR-0011). Within one
family, one account has one membership (``UNIQUE (family_id, account_id)``).
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
    # When a parent member proposed independence (ADR-0014). Always None unless role = child
    independence_proposed_at: datetime | None = None
    # Sort order within the family. Smaller comes first; ties fall back to creation order (ID)
    display_order: int = 0

    @property
    def display_name_value(self) -> str:
        return self.display_name.value

    @property
    def is_linked(self) -> bool:
        """Whether linked to an account (the member cannot sign in until linked)."""
        return self.account_id is not None

    @property
    def independence_proposed(self) -> bool:
        """Whether independence was proposed and awaits the child's own approval (ADR-0014)."""
        return self.independence_proposed_at is not None

    def is_held_by(self, account_id: int) -> bool:
        return self.account_id is not None and self.account_id == account_id


__all__ = ["FamilyMembership"]
