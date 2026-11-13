"""Reward events (ADR-0042).

"Effort cards", any number per child ledger. A goal (``title``), the points earned on
completion (``reward``) and the number of times to achieve it (``goal_count``) are set in
advance, and one sticker is stuck per achievement. When all slots are filled the goal is
complete, and one ``reward`` row is appended to the ledger.

Stickers are stuck **with numbers** (1st, 2nd, ...). The UI sends "the next number to
stick", so the same tap arriving twice never yields two stickers
(``UNIQUE (event_id, number)``). Only the last sticker can be peeled (to undo a mis-tap).
After completion nothing can be stuck or peeled — the points are already in the ledger.

The deadline (``deadline``) is an optional date. If the slots are not filled by the end of
that day the event is **expired** and no more stickers can be stuck (nor points earned).
Days are split by the family's day of living (:class:`~...day_boundary.DayBoundary`), and
the "today" used for the check is passed by the caller. If a parent extends the deadline,
stickers can be stuck again.

The completion row is written with **one idempotency key per event**
(``reward-event#<id>``). Even if two parents stick the last sticker at the same time, only
one row enters the ledger. ``#`` never appears in user-sent keys
(:func:`~...idempotency_key.is_derived`), so it cannot collide with hand-written rows.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

from bounded_contexts.reward_points.domain.exceptions import (
    RewardEventCompletedError,
    RewardEventExpiredError,
    StickerOutOfOrderError,
)
from bounded_contexts.reward_points.domain.value_objects.idempotency_key import STEP_SEPARATOR, IdempotencyKey
from bounded_contexts.reward_points.domain.value_objects.point_amount import PointAmount
from bounded_contexts.reward_points.domain.value_objects.transaction_reason import TransactionReason

#: Max goal length. Kept short enough to fit the card heading (shorter than the ledger reason limit)
TITLE_MAX_LENGTH = 100

#: Max goal count. Kept to what fits as slots on one card (the UI shows it on one screen)
MAX_GOAL_COUNT = 50

#: Base of the idempotency key for the completion row. Used as ``reward-event#<id>``
IDEMPOTENCY_BASE = "reward-event"


@dataclass(frozen=True, kw_only=True)
class EventSticker:
    """One stuck sticker. ``number`` is a sequence number starting at 1."""

    number: int
    stuck_at: datetime


@dataclass(frozen=True, kw_only=True)
class RewardEvent:
    id: int
    ledger_id: int
    title: TransactionReason
    reward: PointAmount
    goal_count: int
    #: In ascending number order
    stickers: tuple[EventSticker, ...]
    #: When the slots were filled. ``None`` if not yet
    completed_at: datetime | None
    created_at: datetime
    #: Completed if filled by the end of this day. ``None`` if unset (stickers can be stuck forever)
    deadline: date | None = None

    def __post_init__(self) -> None:
        # No event subtracts points on completion (spending is recorded by hand)
        if self.reward.value <= 0:
            raise ValueError("Reward event must add points")
        if len(self.title.value) > TITLE_MAX_LENGTH:
            raise ValueError(f"Reward event title cannot exceed {TITLE_MAX_LENGTH} characters")
        if not 1 <= self.goal_count <= MAX_GOAL_COUNT:
            raise ValueError(f"Goal count must be 1..{MAX_GOAL_COUNT}")

    @property
    def sticker_count(self) -> int:
        return len(self.stickers)

    @property
    def is_completed(self) -> bool:
        return self.completed_at is not None

    def is_expired(self, today: date) -> bool:
        """Whether the deadline day has passed without filling. A completed card never expires."""
        return not self.is_completed and self.deadline is not None and today > self.deadline

    @property
    def award_key(self) -> str:
        """Idempotency key of the completion row. Always the same value for the same event."""
        return IdempotencyKey(f"{IDEMPOTENCY_BASE}{STEP_SEPARATOR}{self.id}").value

    def should_stick(self, number: int, *, today: date) -> bool:
        """Whether sticker *number* **should be stuck now**.

        False if that number is already stuck (a resend of the same tap; return the current
        state without doing anything). A skipped number, out-of-range slot, completed or
        expired event raises — the UI is looking at a stale state.
        """
        if number <= self.sticker_count:
            return False
        if self.is_completed:
            raise RewardEventCompletedError
        if self.is_expired(today):
            raise RewardEventExpiredError
        if number != self.sticker_count + 1 or number > self.goal_count:
            raise StickerOutOfOrderError
        return True

    def completes_with(self, number: int) -> bool:
        """Whether sticker *number* fills the slots."""
        return number == self.goal_count

    def should_peel(self, number: int) -> bool:
        """Whether sticker *number* **should be peeled now**.

        False if that number is already gone (the request to peel is already satisfied).
        Only the last sticker can be peeled, and none after completion.
        """
        if self.is_completed:
            raise RewardEventCompletedError
        if number > self.sticker_count:
            return False
        if number != self.sticker_count:
            raise StickerOutOfOrderError
        return True


__all__ = ["IDEMPOTENCY_BASE", "MAX_GOAL_COUNT", "TITLE_MAX_LENGTH", "EventSticker", "RewardEvent"]
