"""Correct a record (reversal + rewrite with the correct content).

The ledger is append-only, so fixing an input mistake never rewrites the original row.
One request appends **two rows** (ADR-0022).

1. A row reversing the original (``reversal_of_id``) — the same as the existing reverse-only
   operation
2. A row with the correct content (``corrects_id``) — indicates which row it restates

The two rows are not sent separately so users never see a state where only one succeeded.
Both are written in one transaction; if either fails, neither remains.

A resend is rejected as "already reversed" (409). As with the reversal operation, failing
with a notice is preferred over taking effect twice.

The idempotency key is split per step for each of the two rows. The separator is reserved
for this split and never appears in client keys (rejected by the API). Even so, reusing
the same key to correct a different record would make the split keys collide, so right
after writing we check that the reversal row really points at our target.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from bounded_contexts.reward_points.application.dto.ledger_dto import CorrectionDTO, just_written
from bounded_contexts.reward_points.application.family_access_resolver import FamilyAccessResolver
from bounded_contexts.reward_points.domain.entities.point_transaction import PointTransaction
from bounded_contexts.reward_points.domain.exceptions import (
    IdempotencyKeyReusedError,
    TransactionAlreadyReversedError,
    TransactionNotFoundError,
)
from bounded_contexts.reward_points.domain.repositories.point_transaction_repository import (
    IPointTransactionRepository,
    NewTransaction,
)
from bounded_contexts.reward_points.domain.value_objects.idempotency_key import IdempotencyKey
from shared.kernel.timestamps import as_naive_utc, utcnow

# Distinguish the two rows one correction writes by idempotency key (with the same key the
# second row would be a replay of the first)
_REVERSAL_STEP = "reversal"
_CORRECTION_STEP = "correction"


@dataclass(frozen=True, kw_only=True)
class CorrectTransactionCommand:
    ledger_id: int
    transaction_id: int
    account_id: int
    amount: int
    reason: str
    # If omitted, inherit the original record's occurrence time (so merely fixing a mistyped
    # amount does not move the event to today)
    occurred_at: datetime | None
    idempotency_key: str


class CorrectPointTransactionUseCase:
    def __init__(self, access: FamilyAccessResolver, transactions: IPointTransactionRepository) -> None:
        self._access = access
        self._transactions = transactions

    def execute(self, command: CorrectTransactionCommand) -> CorrectionDTO:
        found = self._access.modifiable_ledger(ledger_id=command.ledger_id, account_id=command.account_id)
        original = self._original(command)
        # Plan this before the reversal, so that correcting a reversal row reports
        # "a reversal cannot be corrected" rather than "a reversal cannot be reversed"
        corrected = original.plan_correction(
            amount=command.amount,
            reason=command.reason,
            occurred_at=as_naive_utc(command.occurred_at) if command.occurred_at else None,
        )
        undo = original.plan_reversal()
        key = IdempotencyKey(command.idempotency_key)
        actor = found.membership.id
        reversal = self._transactions.append(
            NewTransaction(
                ledger_id=undo.ledger_id,
                amount=undo.amount.value,
                reason=undo.reason.value,
                granted_by_membership_id=actor,
                # The reversal happened "now" (the original row keeps the event's time)
                occurred_at=utcnow(),
                idempotency_key=key.for_step(_REVERSAL_STEP).value,
                reversal_of_id=undo.reversal_of_id,
            )
        )
        if reversal.reversal_of_id != undo.reversal_of_id:
            # An existing row came back for the split key = that key was used by another
            # correction. Continuing would append only the corrected row without a reversal,
            # and both it and the original would count toward the balance
            raise IdempotencyKeyReusedError
        correction = self._transactions.append(
            NewTransaction(
                ledger_id=corrected.ledger_id,
                amount=corrected.amount.value,
                reason=corrected.reason.value,
                granted_by_membership_id=actor,
                occurred_at=corrected.occurred_at,
                idempotency_key=key.for_step(_CORRECTION_STEP).value,
                corrects_id=corrected.corrects_id,
            )
        )
        name = found.membership.display_name_value
        return CorrectionDTO(
            reversal=just_written(reversal, granted_by=name),
            correction=just_written(correction, granted_by=name),
        )

    def _original(self, command: CorrectTransactionCommand) -> PointTransaction:
        original = self._transactions.find_in_ledger(ledger_id=command.ledger_id, transaction_id=command.transaction_id)
        if original is None:
            raise TransactionNotFoundError
        if self._transactions.find_reversal_of(original.id) is not None:
            # Adding to an already reversed row cannot restore the original content.
            # The correct content should be added as a new record
            raise TransactionAlreadyReversedError
        return original


__all__ = ["CorrectPointTransactionUseCase", "CorrectTransactionCommand"]
