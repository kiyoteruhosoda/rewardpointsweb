"""Persistence interface for families."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence

from bounded_contexts.reward_points.domain.entities.family import Family


class IFamilyRepository(ABC):
    @abstractmethod
    def add(self, *, name: str, rules: str | None = None) -> Family:
        """Create a family. ``rules`` is passed only when restoring from an archive (ADR-0026)."""

    @abstractmethod
    def find_by_id(self, family_id: int) -> Family | None: ...

    @abstractmethod
    def list_by_ids(self, family_ids: Sequence[int]) -> list[Family]:
        """Read in bulk for list views (not one at a time)."""

    @abstractmethod
    def list_all(self) -> list[Family]:
        """All families (by name). Used only when the operator picks a family to display (ADR-0047)."""

    @abstractmethod
    def count_owned_by(self, account_id: int) -> int:
        """Number of families in which *account_id* is a member as owner.

        Used to decide whether the account may be deleted.
        """

    @abstractmethod
    def update_name(self, *, family_id: int, name: str) -> Family:
        """Change the family name (only the owner can rename; ADR-0013)."""

    @abstractmethod
    def update_rules(self, *, family_id: int, rules: str | None) -> Family:
        """Rewrite the family rules (``None`` clears them; ADR-0027)."""

    @abstractmethod
    def delete(self, family_id: int) -> None:
        """Delete a family (dissolve). Memberships and invitations go with it."""


__all__ = ["IFamilyRepository"]
