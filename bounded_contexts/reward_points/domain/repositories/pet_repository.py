"""Persistence interface for pets (ADR-0061).

Only the chosen species is stored; growth is worked out from the ledger. A ledger without a
row has a pet that is still an egg with no species chosen. The row goes with the ledger.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from bounded_contexts.reward_points.domain.entities.pet import PetSpecies


class IPetRepository(ABC):
    @abstractmethod
    def species_of(self, ledger_id: int) -> PetSpecies | None:
        """``None`` until someone chooses."""

    @abstractmethod
    def choose_species(self, *, ledger_id: int, species: PetSpecies) -> None:
        """Set or change the species (one pet per ledger)."""


__all__ = ["IPetRepository"]
