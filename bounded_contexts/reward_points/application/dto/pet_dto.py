"""Output DTO for the pet on a ledger (ADR-0061)."""

from __future__ import annotations

from dataclasses import dataclass

from bounded_contexts.reward_points.domain.entities.pet import STAGE_THRESHOLDS, AdoptedPet, PetGrowth, PetSpecies
from bounded_contexts.reward_points.domain.services.ledger_statement import LedgerStatement


@dataclass(frozen=True, kw_only=True)
class PetDTO:
    #: ``None`` until someone chooses
    species: PetSpecies | None
    #: 0 is the egg
    stage: int
    stage_count: int
    #: Points added since the egg was handed over (spending does not lower it). 0 before
    earned: int
    #: Earned total where the current stage began
    current_threshold: int
    #: Earned total for the next stage. ``None`` at the final stage
    next_threshold: int | None
    #: Whether the viewer may choose the species (parents, and the child for their own)
    can_choose: bool


def to_dto(pet: AdoptedPet | None, *, statement: LedgerStatement, can_choose: bool) -> PetDTO:
    """*pet* is ``None`` while the egg has not been handed over (nothing counts yet)."""
    earned = 0 if pet is None else statement.earned_points_since(pet.adopted_at)
    growth = PetGrowth(earned=earned)
    return PetDTO(
        species=None if pet is None else pet.species,
        stage=growth.stage,
        stage_count=len(STAGE_THRESHOLDS),
        earned=earned,
        current_threshold=growth.current_threshold,
        next_threshold=growth.next_threshold,
        can_choose=can_choose,
    )


__all__ = ["PetDTO", "to_dto"]
