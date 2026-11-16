"""Choose (or change) the species of the pet on a ledger (ADR-0061).

The child chooses their own; parents can choose for any child. The first choice hands the
egg over: growth counts from then. Changing the species later keeps that day, so the stage
does not change.
"""

from __future__ import annotations

from dataclasses import dataclass

from bounded_contexts.reward_points.application.dto.pet_dto import PetDTO, to_dto
from bounded_contexts.reward_points.application.family_access_resolver import FamilyAccessResolver
from bounded_contexts.reward_points.domain.entities.pet import PetSpecies
from bounded_contexts.reward_points.domain.repositories.pet_repository import IPetRepository
from bounded_contexts.reward_points.domain.repositories.point_transaction_repository import (
    IPointTransactionRepository,
)
from bounded_contexts.reward_points.domain.services.ledger_statement import LedgerStatement


@dataclass(frozen=True, kw_only=True)
class ChoosePetCommand:
    ledger_id: int
    account_id: int
    species: PetSpecies


class ChoosePetUseCase:
    def __init__(
        self, access: FamilyAccessResolver, pets: IPetRepository, transactions: IPointTransactionRepository
    ) -> None:
        self._access = access
        self._pets = pets
        self._transactions = transactions

    def execute(self, command: ChoosePetCommand) -> PetDTO:
        found = self._access.pet_owner_ledger(ledger_id=command.ledger_id, account_id=command.account_id)
        pet = self._pets.choose_species(ledger_id=found.ledger.id, species=command.species)
        statement = LedgerStatement(self._transactions.list_by_ledger(found.ledger.id))
        return to_dto(pet, statement=statement, can_choose=True)


__all__ = ["ChoosePetCommand", "ChoosePetUseCase"]
