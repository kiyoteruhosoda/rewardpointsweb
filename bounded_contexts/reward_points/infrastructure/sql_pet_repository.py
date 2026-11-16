"""SQLAlchemy implementation of ``IPetRepository`` (ADR-0061)."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from bounded_contexts.reward_points.domain.entities.pet import AdoptedPet, PetSpecies
from bounded_contexts.reward_points.domain.repositories.pet_repository import IPetRepository
from bounded_contexts.reward_points.infrastructure.reward_points_models import PetModel


class SqlPetRepository(IPetRepository):
    def __init__(self, session: Session) -> None:
        self._session = session

    def find(self, ledger_id: int) -> AdoptedPet | None:
        row = self._session.scalar(select(PetModel).where(PetModel.ledger_id == ledger_id))
        return _to_pet(row) if row is not None else None

    def choose_species(self, *, ledger_id: int, species: PetSpecies) -> AdoptedPet:
        row = self._session.scalar(select(PetModel).where(PetModel.ledger_id == ledger_id))
        if row is None:
            try:
                # Two first choices at once: the loser hits UNIQUE (ledger_id) and updates instead
                with self._session.begin_nested():
                    row = PetModel(ledger_id=ledger_id, species=species.value)
                    self._session.add(row)
                return _to_pet(row)
            except IntegrityError:
                row = self._session.scalar(select(PetModel).where(PetModel.ledger_id == ledger_id))
                if row is None:
                    raise
        # Changing the species keeps the day the egg was handed over (``created_at``)
        row.species = species.value
        self._session.flush()
        return _to_pet(row)


def _to_pet(row: PetModel) -> AdoptedPet:
    return AdoptedPet(species=PetSpecies(row.species), adopted_at=row.created_at)


__all__ = ["SqlPetRepository"]
