"""Output DTO for the pet on a ledger (ADR-0061)."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

from bounded_contexts.reward_points.domain.entities.pet import STAGE_THRESHOLDS, AdoptedPet, PetGrowth, PetSpecies
from bounded_contexts.reward_points.domain.entities.pet_care import PetCareKind, PetMoodLevel
from bounded_contexts.reward_points.domain.services.ledger_statement import LedgerStatement


@dataclass(frozen=True, kw_only=True)
class PetCareDTO:
    """How a hatched pet feels (task #1128). Care never touches growth."""

    #: 0..100, made of the recent cares
    mood: int
    mood_level: PetMoodLevel
    #: On how many days it was cared for
    days_cared: int
    #: The latest care, so a screen that did not give it (a display device) can react to it
    last_kind: PetCareKind | None
    last_cared_at: datetime | None


@dataclass(frozen=True, kw_only=True)
class PetPermissions:
    """What the viewer's role in the family allows on this pet (parents, and the child for their own)."""

    choose: bool
    care: bool


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
    #: Whether the viewer may choose a pet **now**: they are allowed (parents, and the child
    #: for their own) and there is an egg to receive — none chosen yet, or the current pet has
    #: reached the final stage and the next one can start
    can_choose: bool
    #: Species of the pets already raised, oldest first
    raised: tuple[PetSpecies, ...]
    #: How it feels. ``None`` until it hatches (an egg is not cared for)
    care: PetCareDTO | None
    #: Whether the viewer may care for it **now**: allowed, and it has hatched
    can_care: bool


def growth_of(pet: AdoptedPet | None, statement: LedgerStatement) -> PetGrowth:
    """Growth of *pet*; ``None`` (no egg handed over yet) counts nothing."""
    return PetGrowth(earned=0 if pet is None else statement.earned_points_since(pet.adopted_at))


def to_dto(
    pet: AdoptedPet | None,
    *,
    raised: Sequence[AdoptedPet],
    statement: LedgerStatement,
    permissions: PetPermissions,
    care: PetCareDTO | None,
) -> PetDTO:
    growth = growth_of(pet, statement)
    return PetDTO(
        species=None if pet is None else pet.species,
        stage=growth.stage,
        stage_count=len(STAGE_THRESHOLDS),
        earned=growth.earned,
        current_threshold=growth.current_threshold,
        next_threshold=growth.next_threshold,
        can_choose=permissions.choose and (pet is None or growth.is_final),
        raised=tuple(earlier.species for earlier in raised),
        care=care,
        can_care=permissions.care and care is not None,
    )


__all__ = ["PetCareDTO", "PetDTO", "PetPermissions", "growth_of", "to_dto"]
