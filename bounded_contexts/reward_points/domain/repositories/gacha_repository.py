"""Persistence interfaces for gacha machines and draws (ADR-0060).

When a ledger goes away its machines and draws go too (family dissolved, member removed,
independence completed). Deleting a machine keeps its draws (they hold a snapshot).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime

from bounded_contexts.reward_points.domain.entities.gacha import Gacha, GachaDesign, GachaDraw


class IGachaRepository(ABC):
    @abstractmethod
    def list_by_ledger(self, ledger_id: int) -> list[Gacha]:
        """In creation order (oldest first)."""

    @abstractmethod
    def find_in_ledger(self, *, ledger_id: int, gacha_id: int) -> Gacha | None:
        """``None`` when the ID points at another ledger's machine."""

    @abstractmethod
    def add(self, *, ledger_id: int, design: GachaDesign) -> Gacha: ...

    @abstractmethod
    def replace_design(self, *, gacha_id: int, design: GachaDesign) -> None:
        """Replace name, price and all prizes. Past draws are untouched (they hold a snapshot)."""

    @abstractmethod
    def delete(self, gacha_id: int) -> None:
        """Delete the machine. Its draws stay, with no machine attached."""


@dataclass(frozen=True, kw_only=True)
class NewGachaDraw:
    ledger_id: int
    gacha_id: int
    gacha_name: str
    prize_name: str
    is_miss: bool
    price: int
    #: The key the client sent (not the derived ledger key)
    idempotency_key: str
    transaction_id: int
    drawn_by_membership_id: int
    drawn_at: datetime


class IGachaDrawRepository(ABC):
    @abstractmethod
    def lock_ledger_balance(self, ledger_id: int) -> int:
        """Lock the ledger against other draws until the transaction ends, and return its balance.

        The balance is read past any snapshot taken earlier in the transaction, so two draws
        arriving together cannot both spend the same points.
        """

    @abstractmethod
    def find_by_key(self, *, ledger_id: int, idempotency_key: str) -> GachaDraw | None:
        """The draw already made with this client key (a resend), read past any snapshot."""

    @abstractmethod
    def add(self, new_draw: NewGachaDraw) -> GachaDraw: ...

    @abstractmethod
    def list_recent(self, *, ledger_id: int, limit: int) -> list[GachaDraw]:
        """Newest first."""

    @abstractmethod
    def find_in_ledger(self, *, ledger_id: int, draw_id: int) -> GachaDraw | None:
        """``None`` when the ID points at another ledger's draw."""

    @abstractmethod
    def set_handed_over(self, *, draw_id: int, handed_over_at: datetime | None, by_membership_id: int | None) -> None:
        """Mark the prize as handed over (or clear the mark with ``None``)."""


__all__ = ["IGachaDrawRepository", "IGachaRepository", "NewGachaDraw"]
