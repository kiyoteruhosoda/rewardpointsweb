"""Care for the hatched pet on a ledger (ADR-0061, task #1128).

The child cares for their own; parents can for any child. Display devices only look. Care is
free and never touches growth or the ledger: it lifts the mood, and the day it was given counts
towards friendship. The same kind of care again within the cooldown is answered but not
recorded, so the screen still plays it.
"""

from __future__ import annotations

from dataclasses import dataclass

from bounded_contexts.reward_points.application.dto.pet_dto import PetDTO, PetPermissions, growth_of
from bounded_contexts.reward_points.application.family_access_resolver import FamilyAccessResolver
from bounded_contexts.reward_points.application.pet_reader import PetReader
from bounded_contexts.reward_points.domain.entities.pet_care import PetCareKind, is_recorded_again
from bounded_contexts.reward_points.domain.exceptions import PetNotHatchedError
from bounded_contexts.reward_points.domain.repositories.pet_care_repository import IPetCareRepository, NewPetCare
from bounded_contexts.reward_points.domain.repositories.pet_repository import IPetRepository
from bounded_contexts.reward_points.domain.repositories.point_transaction_repository import (
    IPointTransactionRepository,
)
from bounded_contexts.reward_points.domain.services import family_access_policy
from bounded_contexts.reward_points.domain.services.day_boundary import DayBoundary
from bounded_contexts.reward_points.domain.services.ledger_statement import LedgerStatement
from shared.kernel.timestamps import utcnow


@dataclass(frozen=True, kw_only=True)
class CareForPetCommand:
    ledger_id: int
    account_id: int
    kind: PetCareKind


@dataclass(frozen=True, kw_only=True)
class PetCareSources:
    """Where the pet, its cares and the ledger it grows on are read from."""

    pets: IPetRepository
    cares: IPetCareRepository
    transactions: IPointTransactionRepository


class CareForPetUseCase:
    def __init__(
        self, access: FamilyAccessResolver, sources: PetCareSources, *, boundary: DayBoundary, reader: PetReader
    ) -> None:
        self._access = access
        self._sources = sources
        self._boundary = boundary
        self._reader = reader

    def execute(self, command: CareForPetCommand) -> PetDTO:
        found = self._access.pet_carer_ledger(ledger_id=command.ledger_id, account_id=command.account_id)
        statement = LedgerStatement(self._sources.transactions.list_by_ledger(found.ledger.id))
        pet = self._sources.pets.current(found.ledger.id)
        if pet is None or not growth_of(pet, statement).has_hatched:
            raise PetNotHatchedError
        now = utcnow()
        if is_recorded_again(self._sources.cares.last_of_kind(pet.id, command.kind), now):
            self._sources.cares.record(
                NewPetCare(
                    pet_id=pet.id,
                    kind=command.kind,
                    cared_at=now,
                    care_day=self._boundary.day_of(now),
                    cared_by_membership_id=found.membership.id,
                )
            )
        permissions = PetPermissions(
            choose=family_access_policy.can_choose_pet(found.membership, found.ledger), care=True
        )
        return self._reader.describe(found.ledger.id, statement=statement, permissions=permissions, now=now)


__all__ = ["CareForPetCommand", "CareForPetUseCase", "PetCareSources"]
