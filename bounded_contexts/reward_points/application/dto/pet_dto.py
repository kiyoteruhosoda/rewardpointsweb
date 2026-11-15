"""Output DTO for the pet on a ledger (ADR-0061)."""

from __future__ import annotations

from dataclasses import dataclass

from bounded_contexts.reward_points.domain.entities.pet import STAGE_THRESHOLDS, PetGrowth, PetSpecies


@dataclass(frozen=True, kw_only=True)
class PetDTO:
    #: ``None`` until someone chooses
    species: PetSpecies | None
    #: 0 is the egg
    stage: int
    stage_count: int
    #: Points ever added (spending does not lower it)
    earned: int
    #: Earned total where the current stage began
    current_threshold: int
    #: Earned total for the next stage. ``None`` at the final stage
    next_threshold: int | None
    #: Whether the viewer may choose the species (parents, and the child for their own)
    can_choose: bool


def to_dto(*, species: PetSpecies | None, earned: int, can_choose: bool) -> PetDTO:
    growth = PetGrowth(earned=earned)
    return PetDTO(
        species=species,
        stage=growth.stage,
        stage_count=len(STAGE_THRESHOLDS),
        earned=earned,
        current_threshold=growth.current_threshold,
        next_threshold=growth.next_threshold,
        can_choose=can_choose,
    )


__all__ = ["PetDTO", "to_dto"]
