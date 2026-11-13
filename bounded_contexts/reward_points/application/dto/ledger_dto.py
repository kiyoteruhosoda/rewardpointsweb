"""Output DTOs for ledgers and transactions."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from bounded_contexts.reward_points.application.dto.daily_bonus_dto import DailyBonusDTO
from bounded_contexts.reward_points.domain.entities.point_transaction import PointTransaction


@dataclass(frozen=True, kw_only=True)
class TransactionDTO:
    id: int
    amount: int
    reason: str
    occurred_at: datetime
    created_at: datetime
    # For a reversal record, the ID of the record it reverses
    reversal_of_id: int | None
    # For a correction record, the ID of the record it restates (ADR-0022)
    corrects_id: int | None
    # Whether this record has been reversed (the UI shows them as a pair)
    is_reversed: bool
    granted_by: str | None


@dataclass(frozen=True, kw_only=True)
class CorrectionDTO:
    """The two rows added to the ledger by one correction (ADR-0022)."""

    reversal: TransactionDTO
    correction: TransactionDTO


@dataclass(frozen=True, kw_only=True)
class LedgerDTO:
    ledger_id: int
    family_id: int
    membership_id: int
    display_name: str
    balance: int
    # The screen decides whether to show editing UI from this single value (no branching on role names)
    can_modify: bool
    transactions: tuple[TransactionDTO, ...]
    # Daily bonus setting (ADR-0024); ``None`` if not set
    daily_bonus: DailyBonusDTO | None


def just_written(transaction: PointTransaction, *, granted_by: str | None) -> TransactionDTO:
    """The row just written.

    Returned to whoever appended it, so ``is_reversed`` is always false (no row is
    reversed the moment it is written). Building rows when re-reading the ledger is
    done separately by ``ViewPointLedgerUseCase`` (which decides reversal from the
    whole ledger).
    """
    return TransactionDTO(
        id=transaction.id,
        amount=transaction.amount.value,
        reason=transaction.reason.value,
        occurred_at=transaction.occurred_at,
        created_at=transaction.created_at,
        reversal_of_id=transaction.reversal_of_id,
        corrects_id=transaction.corrects_id,
        is_reversed=False,
        granted_by=granted_by,
    )


__all__ = ["CorrectionDTO", "LedgerDTO", "TransactionDTO", "just_written"]
