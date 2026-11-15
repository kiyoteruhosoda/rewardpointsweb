"""SQLAlchemy implementation of ``IPetRepository`` (ADR-0061)."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from bounded_contexts.reward_points.domain.entities.pet import PetSpecies
from bounded_contexts.reward_points.domain.repositories.pet_repository import IPetRepository
from bounded_contexts.reward_points.infrastructure.reward_points_models import PetModel


class SqlPetRepository(IPetRepository):
    def __init__(self, session: Session) -> None:
        self._session = session

    def species_of(self, ledger_id: int) -> PetSpecies | None:
        value = self._session.scalar(select(PetModel.species).where(PetModel.ledger_id == ledger_id))
        return PetSpecies(value) if value is not None else None

    def choose_species(self, *, ledger_id: int, species: PetSpecies) -> None:
        row = self._session.scalar(select(PetModel).where(PetModel.ledger_id == ledger_id))
        if row is not None:
            row.species = species.value
            self._session.flush()
            return
        try:
            # Two first choices at once: the loser hits UNIQUE (ledger_id) and updates instead
            with self._session.begin_nested():
                self._session.add(PetModel(ledger_id=ledger_id, species=species.value))
        except IntegrityError:
            existing = self._session.scalar(select(PetModel).where(PetModel.ledger_id == ledger_id))
            if existing is None:
                raise
            existing.species = species.value
            self._session.flush()


__all__ = ["SqlPetRepository"]
