"""One ledger row (append-only).

Never UPDATEd or DELETEd. A correction is expressed by appending a row with the
opposite sign (ADR-0010). Building a reversal is confined to
:meth:`PointTransaction.plan_reversal`, so sign flipping and the "a reversal
cannot be reversed" rule are not scattered across callers.

To fix an input mistake, write the correct content again after the reversal
(ADR-0022). That second row is built by :meth:`PointTransaction.plan_correction`,
and ``corrects_id`` tells which row it restates.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from bounded_contexts.reward_points.domain.exceptions import (
    CorrectionOfReversalError,
    ReversalOfReversalError,
)
from bounded_contexts.reward_points.domain.value_objects.point_amount import PointAmount
from bounded_contexts.reward_points.domain.value_objects.transaction_reason import TransactionReason


@dataclass(frozen=True, kw_only=True)
class ReversalDraft:
    """A reversal row not yet written to the ledger."""

    ledger_id: int
    amount: PointAmount
    reason: TransactionReason
    reversal_of_id: int


@dataclass(frozen=True, kw_only=True)
class CorrectionDraft:
    """A corrected row not yet written to the ledger."""

    ledger_id: int
    amount: PointAmount
    reason: TransactionReason
    occurred_at: datetime
    corrects_id: int


@dataclass(frozen=True, kw_only=True)
class PointTransaction:
    id: int
    ledger_id: int
    amount: PointAmount
    reason: TransactionReason
    # The member who performed the operation. The record stays even if they leave the family
    granted_by_membership_id: int | None
    # When the event happened (can be backdated) differs from when the record was created
    occurred_at: datetime
    created_at: datetime
    reversal_of_id: int | None
    # For a corrected row, the ID of the row it restates (ADR-0022)
    corrects_id: int | None

    @property
    def is_reversal(self) -> bool:
        return self.reversal_of_id is not None

    @property
    def is_correction(self) -> bool:
        return self.corrects_id is not None

    @property
    def signed_points(self) -> int:
        return self.amount.value

    def plan_reversal(self) -> ReversalDraft:
        """Content of the row that reverses this one. The reason is carried over from the original."""
        if self.is_reversal:
            raise ReversalOfReversalError
        return ReversalDraft(
            ledger_id=self.ledger_id,
            amount=self.amount.negated,
            reason=self.reason,
            reversal_of_id=self.id,
        )

    def plan_correction(self, *, amount: int, reason: str, occurred_at: datetime | None = None) -> CorrectionDraft:
        """Content of the row that restates this one. The reversal row is built separately by :meth:`plan_reversal`.

        Without ``occurred_at``, the original row's occurrence time is carried over,
        so merely fixing a typo in the amount or reason does not move the event
        itself to today.
        """
        if self.is_reversal:
            raise CorrectionOfReversalError
        return CorrectionDraft(
            ledger_id=self.ledger_id,
            amount=PointAmount(amount),
            reason=TransactionReason(reason),
            occurred_at=occurred_at or self.occurred_at,
            corrects_id=self.id,
        )


__all__ = ["CorrectionDraft", "PointTransaction", "ReversalDraft"]
