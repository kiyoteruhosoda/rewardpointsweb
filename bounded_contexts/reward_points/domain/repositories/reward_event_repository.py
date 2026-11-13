"""Persistence interface for reward events (ADR-0042).

When a ledger goes away its events go too (family dissolved, member removed, independence completed).
Ledger rows added on completion remain separately from the event — deleting an event does not touch the ledger.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date, datetime

from bounded_contexts.reward_points.domain.entities.reward_event import RewardEvent


@dataclass(frozen=True, kw_only=True)
class NewRewardEvent:
    """An event about to be created."""

    ledger_id: int
    title: str
    reward: int
    goal_count: int
    deadline: date | None = None


class IRewardEventRepository(ABC):
    @abstractmethod
    def list_by_ledger(self, ledger_id: int) -> list[RewardEvent]:
        """In creation order (oldest first)."""

    @abstractmethod
    def find_in_ledger(self, *, ledger_id: int, event_id: int) -> RewardEvent | None:
        """``None`` when the ID points at another ledger's event."""

    @abstractmethod
    def add(self, new_event: NewRewardEvent) -> RewardEvent: ...

    @abstractmethod
    def stick(self, *, event_id: int, number: int, stuck_at: datetime, stuck_by_membership_id: int) -> bool:
        """Place sticker number *number*.

        Returns false when the same number was placed concurrently (hit
        ``UNIQUE (event_id, number)``). The other side placed it, so it also handles completion.
        """

    @abstractmethod
    def peel(self, *, event_id: int, number: int) -> None:
        """Peel off sticker number *number*. Does nothing if it is not there."""

    @abstractmethod
    def mark_completed(self, *, event_id: int, completed_at: datetime, awarded_transaction_id: int) -> None:
        """Record that all slots are filled and *awarded_transaction_id* was added to the ledger."""

    @abstractmethod
    def change_deadline(self, *, event_id: int, deadline: date | None) -> None:
        """Reset the deadline (``None`` for no deadline)."""

    @abstractmethod
    def delete(self, event_id: int) -> None:
        """Delete the event. Does not touch the ledger history."""


__all__ = ["IRewardEventRepository", "NewRewardEvent"]
