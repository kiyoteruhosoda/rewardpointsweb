"""Family (aggregate root).

Sharing is expressed only by joining a family; there is no per-member sharing
(ADR-0009). The family is the explicit data-isolation boundary: every ledger,
member and invitation belongs to exactly one family.

The family also holds its agreed rules (``rules``): one per family, not per child,
and every member reads the same text (ADR-0027).
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
    #: The family's rules. ``None`` if not written yet (distinct from an empty string)
    rules: FamilyRules | None
    created_at: datetime

    @property
    def name_value(self) -> str:
        return self.name.value

    @property
    def rules_value(self) -> str | None:
        return self.rules.value if self.rules else None


__all__ = ["Family"]
