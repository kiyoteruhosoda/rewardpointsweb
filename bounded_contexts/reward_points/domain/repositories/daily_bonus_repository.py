"""Persistence interface for the daily bonus (ADR-0024).

One per ledger (``UNIQUE (ledger_id)``). When the ledger goes away, so does the setting
(family dissolved, member deleted, independence completed).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date

from bounded_contexts.reward_points.domain.entities.daily_bonus import DailyBonus


@dataclass(frozen=True, kw_only=True)
class DailyBonusDraft:
    """A setting about to be saved."""

    ledger_id: int
    amount: int
    reason: str
    #: "First grant day" when creating a new setting. Not used for an existing one
    starts_on: date


class IDailyBonusRepository(ABC):
    @abstractmethod
    def find_by_ledger(self, ledger_id: int) -> DailyBonus | None: ...

    @abstractmethod
    def list_for_ledgers(self, ledger_ids: Sequence[int]) -> list[DailyBonus]:
        """Read the settings of several ledgers at once (for the family settings screen, ADR-0027).

        Settings are listed on the family settings screen, so fetching per member would add
        one round trip per family member.
        """

    @abstractmethod
    def save(self, draft: DailyBonusDraft) -> DailyBonus:
        """Create the ledger's setting, or update its amount and reason.

        ``starts_on`` and ``granted_through`` of an existing setting are left unchanged.
        Merely changing the amount must not undo the days already granted.
        """

    @abstractmethod
    def delete_by_ledger(self, ledger_id: int) -> None:
        """Delete the setting (= stop the daily bonus). The ledger history is not touched."""

    @abstractmethod
    def list_due(self, today: date) -> list[DailyBonus]:
        """Settings that still have ungranted days as of *today*.

        Returns results across families (granting runs from outside any family). This is
        not subject to authorization, so keep it callable only from the granting use case.
        """

    @abstractmethod
    def mark_granted_through(self, *, bonus_id: int, day: date) -> None:
        """Record that grants are done through *day*."""


__all__ = ["DailyBonusDraft", "IDailyBonusRepository"]
