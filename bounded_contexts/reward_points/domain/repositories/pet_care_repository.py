"""Persistence interface for the cares given to a pet (ADR-0061, task #1128).

One row per recorded care, hung off the pet (one generation on a ledger). The rows go with
the pet, and the pet with the ledger.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date, datetime

from bounded_contexts.reward_points.domain.entities.pet_care import PetCare, PetCareKind


@dataclass(frozen=True, kw_only=True)
class NewPetCare:
    pet_id: int
    kind: PetCareKind
    cared_at: datetime
    #: The day it falls on under the family's day boundary (friendship counts days)
    care_day: date
    #: Who cared (the child or a parent). Kept for the history only
    cared_by_membership_id: int


class IPetCareRepository(ABC):
    @abstractmethod
    def record(self, care: NewPetCare) -> None:
        """Add one care."""

    @abstractmethod
    def cared_since(self, pet_id: int, since: datetime) -> list[PetCare]:
        """Cares at or after *since*, oldest first."""

    @abstractmethod
    def last(self, pet_id: int) -> PetCare | None:
        """The latest care of any kind. ``None`` if never cared for."""

    @abstractmethod
    def last_of_kind(self, pet_id: int, kind: PetCareKind) -> datetime | None:
        """When *kind* was last given. ``None`` if never."""

    @abstractmethod
    def days_cared(self, pet_id: int) -> int:
        """On how many days the pet was cared for."""


__all__ = ["IPetCareRepository", "NewPetCare"]
