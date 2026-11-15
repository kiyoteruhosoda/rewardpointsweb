"""A pet that grows with the points a child has earned (ADR-0061).

One per child ledger. It starts as an egg and moves up through fixed stages as the points
**ever added** to the ledger grow (:attr:`~...ledger_statement.LedgerStatement.earned_points`).
Spending never shrinks it; reversing an addition does (that addition never happened).

The stage is not stored: it is worked out from the ledger on every read, so it can never
drift from the history. Only the species — what the child chose — is stored.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class PetSpecies(Enum):
    CAT = "cat"
    RABBIT = "rabbit"
    BIRD = "bird"
    DRAGON = "dragon"


#: Points earned to reach each stage, from the egg (0) up. Early stages come quickly so a
#: new pet hatches after a few chores; later ones take months
STAGE_THRESHOLDS: tuple[int, ...] = (0, 30, 100, 300, 700, 1500)


@dataclass(frozen=True, kw_only=True)
class PetGrowth:
    """Where a pet stands for *earned* points."""

    earned: int

    @property
    def stage(self) -> int:
        """0 is the egg; the last index is the final stage."""
        return max(index for index, threshold in enumerate(STAGE_THRESHOLDS) if self.earned >= threshold)

    @property
    def is_final(self) -> bool:
        return self.stage == len(STAGE_THRESHOLDS) - 1

    @property
    def current_threshold(self) -> int:
        return STAGE_THRESHOLDS[self.stage]

    @property
    def next_threshold(self) -> int | None:
        """Points needed for the next stage in total. ``None`` at the final stage."""
        return None if self.is_final else STAGE_THRESHOLDS[self.stage + 1]

    @property
    def points_to_next(self) -> int | None:
        next_threshold = self.next_threshold
        return None if next_threshold is None else next_threshold - self.earned


__all__ = ["STAGE_THRESHOLDS", "PetGrowth", "PetSpecies"]
