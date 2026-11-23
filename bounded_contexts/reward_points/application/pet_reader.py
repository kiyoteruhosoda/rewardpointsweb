"""Describes the pet on a ledger: its growth and how it feels (ADR-0061, task #1128).

Growth comes from the ledger; the mood and the friendship come from the care records. Viewing
the ledger, choosing a pet and giving a care all answer through here, so they agree.
"""

from __future__ import annotations

from datetime import datetime

from bounded_contexts.reward_points.application.dto.pet_dto import (
    PetCareDTO,
    PetDTO,
    PetPermissions,
    growth_of,
    to_dto,
)
from bounded_contexts.reward_points.domain.entities.pet import AdoptedPet, PetGrowth
from bounded_contexts.reward_points.domain.entities.pet_care import CARE_FADES_OVER, mood_at
from bounded_contexts.reward_points.domain.repositories.pet_care_repository import IPetCareRepository
from bounded_contexts.reward_points.domain.repositories.pet_repository import IPetRepository
from bounded_contexts.reward_points.domain.services.ledger_statement import LedgerStatement


class PetReader:
    def __init__(self, pets: IPetRepository, cares: IPetCareRepository) -> None:
        self._pets = pets
        self._cares = cares

    def describe(
        self, ledger_id: int, *, statement: LedgerStatement, permissions: PetPermissions, now: datetime
    ) -> PetDTO:
        pet = self._pets.current(ledger_id)
        return to_dto(
            pet,
            raised=self._pets.raised(ledger_id),
            statement=statement,
            permissions=permissions,
            care=self._care_of(pet, growth_of(pet, statement), now=now),
        )

    def _care_of(self, pet: AdoptedPet | None, growth: PetGrowth, *, now: datetime) -> PetCareDTO | None:
        """How *pet* feels at *now*. ``None`` while there is no hatched pet."""
        if pet is None or not growth.has_hatched:
            return None
        days_cared = self._cares.days_cared(pet.id)
        mood = mood_at(now, self._cares.cared_since(pet.id, now - CARE_FADES_OVER), ever_cared=days_cared > 0)
        last = self._cares.last(pet.id)
        return PetCareDTO(
            mood=mood.value,
            mood_level=mood.level,
            days_cared=days_cared,
            last_kind=None if last is None else last.kind,
            last_cared_at=None if last is None else last.cared_at,
        )


__all__ = ["PetReader"]
