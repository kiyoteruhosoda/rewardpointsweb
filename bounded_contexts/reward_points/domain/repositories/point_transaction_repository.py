"""Persistence interface for ledger transactions.

Append-only, so there are no entry points for updating or deleting individual rows
(ADR-0010). The sole exception is :meth:`IPointTransactionRepository.delete_by_ledger`,
which deletes a whole ledger when independence is established (ADR-0014).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime

from bounded_contexts.reward_points.domain.entities.point_transaction import PointTransaction


@dataclass(frozen=True, kw_only=True)
class NewTransaction:
    """A row not yet written to the ledger.

    Bundles the values needed for writing into a single argument (adding, spending,
    reversing and correcting pass the same things, so one write entry point suffices).
    """

    ledger_id: int
    amount: int
    reason: str
    # Daily bonuses (ADR-0024) are nobody's action, so they are written with ``None``.
    # The UI shows them with an empty recorder field
    granted_by_membership_id: int | None
    occurred_at: datetime
    idempotency_key: str
    reversal_of_id: int | None = None
    # For a corrected row, the ID of the row it restates (ADR-0022)
    corrects_id: int | None = None


class IPointTransactionRepository(ABC):
    @abstractmethod
    def list_by_ledger(self, ledger_id: int) -> list[PointTransaction]:
        """Newest occurrence time first."""

    @abstractmethod
    def list_by_ledgers(self, ledger_ids: Sequence[int]) -> Mapping[int, list[PointTransaction]]:
        """Ledger ID -> history. Lets list balance calculations avoid fetching one by one."""

    @abstractmethod
    def find_in_ledger(self, *, ledger_id: int, transaction_id: int) -> PointTransaction | None: ...

    @abstractmethod
    def find_reversal_of(self, transaction_id: int) -> PointTransaction | None:
        """Check whether it is already reversed (``reversal_of_id`` is UNIQUE)."""

    @abstractmethod
    def append(self, new_transaction: NewTransaction) -> PointTransaction:
        """Append one row.

        On a ``UNIQUE (ledger_id, idempotency_key)`` conflict, return the existing record
        instead of raising (ADR-0010).
        """

    @abstractmethod
    def count_by_ledger(self, ledger_id: int) -> int: ...

    @abstractmethod
    def delete_by_ledger(self, ledger_id: int) -> None:
        """Delete all records of the ledger.

        The sole exception to append-only (ADR-0010), called only when independence is
        established (ADR-0014). Per-row deletion will not be provided in the future either.
        """

    @abstractmethod
    def frequent_reasons(self, *, family_id: int, limit: int) -> list[str]:
        """Return reasons used in the family, most frequent first.

        These are suggestions to save typing, and authorization is scoped to the family.
        Other families' reasons are excluded (filtered by ``family_id``).
        """


__all__ = ["IPointTransactionRepository", "NewTransaction"]
