"""SQLAlchemy implementation of ``IPetRepository`` (ADR-0061).

``UNIQUE (ledger_id, generation)`` keeps two concurrent choices from adopting two eggs: the
loser gets ``None`` back and is told the pet was already chosen.
"""

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

    def current(self, ledger_id: int) -> AdoptedPet | None:
        row = self._session.scalar(
            select(PetModel).where(PetModel.ledger_id == ledger_id).order_by(PetModel.generation.desc()).limit(1)
        )
        return _to_pet(row) if row is not None else None

    def raised(self, ledger_id: int) -> list[AdoptedPet]:
        rows = self._session.scalars(
            select(PetModel).where(PetModel.ledger_id == ledger_id).order_by(PetModel.generation)
        ).all()
        return [_to_pet(row) for row in rows[:-1]]

    def adopt(self, *, ledger_id: int, species: PetSpecies, generation: int) -> AdoptedPet | None:
        row = PetModel(ledger_id=ledger_id, species=species.value, generation=generation)
        try:
            with self._session.begin_nested():
                self._session.add(row)
        except IntegrityError:
            return None
        return _to_pet(row)


def _to_pet(row: PetModel) -> AdoptedPet:
    return AdoptedPet(species=PetSpecies(row.species), adopted_at=row.created_at, generation=row.generation)


__all__ = ["SqlPetRepository"]
