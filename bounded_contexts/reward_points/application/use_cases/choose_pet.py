"""Choose the pet to raise on a ledger (ADR-0061).

The child chooses their own; parents can choose for any child. Choosing hands the egg over,
and growth counts from then. The species is chosen once: while the pet is growing it cannot
be changed. When it reaches the final stage, the next pet can be chosen and starts from an
egg at 0; the earlier one stays as a raised pet.
"""

from __future__ import annotations

from dataclasses import dataclass

from bounded_contexts.reward_points.application.dto.pet_dto import PetDTO, PetPermissions, growth_of
from bounded_contexts.reward_points.application.family_access_resolver import FamilyAccessResolver
from bounded_contexts.reward_points.application.pet_reader import PetReader
from bounded_contexts.reward_points.domain.entities.pet import PetSpecies
from bounded_contexts.reward_points.domain.exceptions import PetAlreadyChosenError
from bounded_contexts.reward_points.domain.repositories.pet_repository import IPetRepository
from bounded_contexts.reward_points.domain.repositories.point_transaction_repository import (
    IPointTransactionRepository,
)
from bounded_contexts.reward_points.domain.services import family_access_policy
from bounded_contexts.reward_points.domain.services.ledger_statement import LedgerStatement
from shared.kernel.timestamps import utcnow


@dataclass(frozen=True, kw_only=True)
class ChoosePetCommand:
    ledger_id: int
    account_id: int
    species: PetSpecies


class ChoosePetUseCase:
    def __init__(
        self,
        access: FamilyAccessResolver,
        pets: IPetRepository,
        transactions: IPointTransactionRepository,
        *,
        reader: PetReader,
    ) -> None:
        self._access = access
        self._pets = pets
        self._transactions = transactions
        self._reader = reader

    def execute(self, command: ChoosePetCommand) -> PetDTO:
        found = self._access.pet_owner_ledger(ledger_id=command.ledger_id, account_id=command.account_id)
        statement = LedgerStatement(self._transactions.list_by_ledger(found.ledger.id))
        current = self._pets.current(found.ledger.id)
        # Still growing: its species stays. A resent choice also lands here (the egg it asked for exists)
        if current is not None and not growth_of(current, statement).is_final:
            raise PetAlreadyChosenError
        generation = 1 if current is None else current.generation + 1
        adopted = self._pets.adopt(ledger_id=found.ledger.id, species=command.species, generation=generation)
        if adopted is None:
            raise PetAlreadyChosenError
        permissions = PetPermissions(
            choose=True, care=family_access_policy.can_care_for_pet(found.membership, found.ledger)
        )
        return self._reader.describe(found.ledger.id, statement=statement, permissions=permissions, now=utcnow())


__all__ = ["ChoosePetCommand", "ChoosePetUseCase"]
