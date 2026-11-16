"""Persistence interface for pets (ADR-0061).

Each pet raised on a ledger is one row: its species, when its egg was handed over, and its
generation (1, 2, ...). The current pet is the latest generation; the earlier ones are the
pets already raised. Growth is worked out from the ledger. A ledger without rows has an egg
with no species chosen. The rows go with the ledger.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from bounded_contexts.reward_points.domain.entities.pet import AdoptedPet, PetSpecies


class IPetRepository(ABC):
    @abstractmethod
    def current(self, ledger_id: int) -> AdoptedPet | None:
        """The pet being raised now (the latest generation). ``None`` until the first choice."""

    @abstractmethod
    def raised(self, ledger_id: int) -> list[AdoptedPet]:
        """The pets raised before the current one, oldest first."""

    @abstractmethod
    def adopt(self, *, ledger_id: int, species: PetSpecies, generation: int) -> AdoptedPet | None:
        """Hand over the egg of *generation*. ``None`` if that generation was adopted concurrently."""


__all__ = ["IPetRepository"]
