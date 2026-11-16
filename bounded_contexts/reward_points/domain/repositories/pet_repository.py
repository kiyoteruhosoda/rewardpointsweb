"""Persistence interface for pets (ADR-0061).

Only the chosen species and when the egg was handed over are stored; growth is worked out
from the ledger. A ledger without a row has an egg with no species chosen (nothing counts
yet). The row goes with the ledger.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from bounded_contexts.reward_points.domain.entities.pet import AdoptedPet, PetSpecies


class IPetRepository(ABC):
    @abstractmethod
    def find(self, ledger_id: int) -> AdoptedPet | None:
        """``None`` until someone chooses."""

    @abstractmethod
    def choose_species(self, *, ledger_id: int, species: PetSpecies) -> AdoptedPet:
        """Set or change the species (one pet per ledger). The first choice hands the egg over."""


__all__ = ["IPetRepository"]
