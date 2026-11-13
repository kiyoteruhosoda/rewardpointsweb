"""Pydantic schemas of the reward_points context.

Lengths and limits use the constants of the domain value objects (never copy the numbers).
``role`` uses the domain enum as-is; its values (``"owner"`` etc.) appear in the JSON.
It also appears as an enum in OpenAPI.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Annotated

from pydantic import AfterValidator, BaseModel, Field, model_validator

from bounded_contexts.reward_points.domain.entities.reward_event import (
    MAX_GOAL_COUNT as EVENT_GOAL_COUNT_MAX,
)
from bounded_contexts.reward_points.domain.entities.reward_event import (
    TITLE_MAX_LENGTH as EVENT_TITLE_MAX_LENGTH,
)
from bounded_contexts.reward_points.domain.value_objects.display_name import (
    MAX_LENGTH as DISPLAY_NAME_MAX_LENGTH,
)
from bounded_contexts.reward_points.domain.value_objects.family_name import MAX_LENGTH as FAMILY_NAME_MAX_LENGTH
from bounded_contexts.reward_points.domain.value_objects.family_role import FamilyRole
from bounded_contexts.reward_points.domain.value_objects.family_rules import (
    MAX_LENGTH as FAMILY_RULES_MAX_LENGTH,
)
from bounded_contexts.reward_points.domain.value_objects.idempotency_key import (
    MAX_BASE_LENGTH as IDEMPOTENCY_KEY_MAX_BASE_LENGTH,
)
from bounded_contexts.reward_points.domain.value_objects.idempotency_key import (
    MAX_LENGTH as IDEMPOTENCY_KEY_MAX_LENGTH,
)
from bounded_contexts.reward_points.domain.value_objects.idempotency_key import (
    STEP_SEPARATOR,
    is_derived,
)
from bounded_contexts.reward_points.domain.value_objects.point_amount import MAX_MAGNITUDE as AMOUNT_MAX
from bounded_contexts.reward_points.domain.value_objects.transaction_reason import (
    MAX_LENGTH as REASON_MAX_LENGTH,
)
from presentation.fastapi.schemas.types import UtcDatetime
from shared.domain.auth.password_policy import MAX_LENGTH as PASSWORD_MAX_LENGTH
from shared.domain.auth.password_policy import MIN_LENGTH as PASSWORD_MIN_LENGTH
from shared.domain.auth.username import MAX_LENGTH as USERNAME_MAX_LENGTH


def _non_blank(value: str) -> str:
    """Strip surrounding whitespace and reject whitespace-only input.

    ``min_length=1`` lets a single space through, so the length is checked after stripping
    what would be displayed.
    """
    stripped = value.strip()
    if not stripped:
        raise ValueError("must not be blank")
    return stripped


def _non_zero(value: int) -> int:
    """0 is meaningless in a ledger (``CHECK (amount <> 0)``; ADR-0010)."""
    if value == 0:
        raise ValueError("must not be zero")
    return value


def _not_a_step_key(value: str) -> str:
    """Reject keys in the per-step split form (``<key>#reversal``).

    A ledger has only one key space (``UNIQUE (ledger_id, idempotency_key)``). If clients
    could send keys of the same form a correction builds internally, an unrelated record
    could be mistaken for "a resend of the same operation", leaving a reversal that was
    meant to be written unwritten.
    """
    if is_derived(value):
        raise ValueError(f"must not contain {STEP_SEPARATOR!r}")
    return value


NonBlankStr = Annotated[str, AfterValidator(_non_blank)]
IdempotencyKeyStr = Annotated[
    NonBlankStr, AfterValidator(_not_a_step_key), Field(max_length=IDEMPOTENCY_KEY_MAX_LENGTH)
]
# A correction writes two rows at once, splitting the key per step. Limit to a length that
# still fits the column after splitting
CorrectionKeyStr = Annotated[
    NonBlankStr, AfterValidator(_not_a_step_key), Field(max_length=IDEMPOTENCY_KEY_MAX_BASE_LENGTH)
]
DisplayNameStr = Annotated[NonBlankStr, Field(max_length=DISPLAY_NAME_MAX_LENGTH)]
CodeStr = Annotated[NonBlankStr, Field(max_length=64)]


# --- Daily bonus (ADR-0024) --------------------------------------------------
#
# Included in both family responses (per member) and ledger responses, so it comes before family.


class DailyBonusRequest(BaseModel):
    """How much to add each day. Additions only, so no sign (positive numbers only)."""

    amount: Annotated[int, Field(ge=1, le=AMOUNT_MAX)]
    reason: Annotated[NonBlankStr, Field(max_length=REASON_MAX_LENGTH)]


class DailyBonusResponse(BaseModel):
    ledger_id: int
    amount: int
    reason: str
    # First day to grant (the day after it was set)
    starts_on: date
    # Last day granted. null if not a single day has been granted yet
    granted_through: date | None


# --- Reward events (ADR-0042) ------------------------------------------------


class RewardEventCreateRequest(BaseModel):
    """Goal, points earned on completion, and number of achievements (= number of slots)."""

    title: Annotated[NonBlankStr, Field(max_length=EVENT_TITLE_MAX_LENGTH)]
    reward_points: Annotated[int, Field(ge=1, le=AMOUNT_MAX)]
    goal_count: Annotated[int, Field(ge=1, le=EVENT_GOAL_COUNT_MAX)]
    # Completed if filled by the end of this day (family's day boundary). Omit for no deadline
    deadline: date | None = None


class RewardEventDeadlineRequest(BaseModel):
    """Reset the deadline. null for no deadline."""

    deadline: date | None


class StickerResponse(BaseModel):
    number: int
    stuck_at: UtcDatetime


class RewardEventResponse(BaseModel):
    id: int
    ledger_id: int
    title: str
    reward_points: int
    goal_count: int
    # In ascending number order
    stickers: list[StickerResponse]
    # When the slots were filled. null if not yet
    completed_at: UtcDatetime | None
    created_at: UtcDatetime
    # Completed if filled by the end of this day. null if unset
    deadline: date | None
    # Past the deadline without being filled (the server judges by the family's day boundary)
    is_expired: bool


class RewardEventBoardResponse(BaseModel):
    ledger_id: int
    display_name: str
    can_modify: bool
    events: list[RewardEventResponse]


# --- Family ------------------------------------------------------------------


class FamilyCreateRequest(BaseModel):
    name: Annotated[NonBlankStr, Field(max_length=FAMILY_NAME_MAX_LENGTH)]
    # The name you go by in the family. Defaults to the account's display name if omitted
    display_name: DisplayNameStr | None = None


class MembershipResponse(BaseModel):
    id: int
    display_name: str
    role: FamilyRole
    is_linked: bool
    is_me: bool
    username: str | None
    ledger_id: int | None
    balance: int | None
    # Daily bonus settings (ADR-0024). null if unset. They are decided on the family settings
    # screen, so they are included here per member (ADR-0027)
    daily_bonus: DailyBonusResponse | None = None
    # Whether independence was requested and awaits the child's own approval (ADR-0014)
    independence_proposed: bool
    # Operations the viewer may perform on this member. The UI shows operations based on these
    can_reset_password: bool
    can_propose_independence: bool
    can_remove: bool


class FamilySummaryResponse(BaseModel):
    id: int
    name: str
    my_membership_id: int
    my_role: FamilyRole
    member_count: int


class FamilyDetailResponse(BaseModel):
    id: int
    name: str
    # Rules agreed in the family (ADR-0027). null if not written yet
    rules: str | None
    my_membership_id: int
    my_role: FamilyRole
    memberships: list[MembershipResponse]


class FamilyRenameRequest(BaseModel):
    name: Annotated[NonBlankStr, Field(max_length=FAMILY_NAME_MAX_LENGTH)]


class FamilyRulesRequest(BaseModel):
    """Rules agreed in the family (ADR-0027).

    Empty or whitespace-only input is treated as "clear", so ``NonBlankStr`` is not used
    (clearing what was written does not get a separate entry point).
    """

    rules: Annotated[str, Field(max_length=FAMILY_RULES_MAX_LENGTH)] | None = None


class ChildCreateRequest(BaseModel):
    display_name: DisplayNameStr


class MemberOrderRequest(BaseModel):
    """Member IDs in the desired order. Lists each child of the family exactly once."""

    membership_ids: list[int]


# --- Invitations -------------------------------------------------------------


class InvitationCreateRequest(BaseModel):
    role: FamilyRole
    # A role = child invitation always points at the member a parent created beforehand (ADR-0011)
    target_membership_id: int | None = None


class InvitationResponse(BaseModel):
    id: int
    role: FamilyRole
    target_membership_id: int | None
    target_display_name: str | None
    expires_at: UtcDatetime
    # The plaintext code is only included in the issuing response (only the hash is stored)
    code: str | None


class InvitationAcceptRequest(BaseModel):
    code: CodeStr
    # Required only for invitations not pointing at a member (joining as a parent)
    display_name: DisplayNameStr | None = None


class InvitationRedeemRequest(BaseModel):
    """Called unauthenticated. Creates an account in exchange for an invitation code (ADR-0011)."""

    code: CodeStr
    username: Annotated[str, Field(min_length=1, max_length=USERNAME_MAX_LENGTH)]
    password: Annotated[str, Field(min_length=PASSWORD_MIN_LENGTH, max_length=PASSWORD_MAX_LENGTH)]
    display_name: DisplayNameStr | None = None


class RedeemedInvitationResponse(BaseModel):
    family_id: int
    family_name: str
    membership_id: int
    role: FamilyRole
    username: str


class TemporaryPasswordResponse(BaseModel):
    membership_id: int
    username: str
    password: str
    expires_at: UtcDatetime


# --- Ledger ------------------------------------------------------------------


class TransactionCreateRequest(BaseModel):
    # The sign expresses addition (positive) and spending (negative)
    amount: Annotated[int, Field(ge=-AMOUNT_MAX, le=AMOUNT_MAX), AfterValidator(_non_zero)]
    reason: Annotated[NonBlankStr, Field(max_length=REASON_MAX_LENGTH)]
    idempotency_key: IdempotencyKeyStr
    # If omitted, the time it was received (UTC)
    occurred_at: datetime | None = None


class ReversalCreateRequest(BaseModel):
    idempotency_key: IdempotencyKeyStr


class CorrectionCreateRequest(BaseModel):
    """The corrected content (ADR-0022). Not an overwrite; the correct content is written anew."""

    amount: Annotated[int, Field(ge=-AMOUNT_MAX, le=AMOUNT_MAX), AfterValidator(_non_zero)]
    reason: Annotated[NonBlankStr, Field(max_length=REASON_MAX_LENGTH)]
    idempotency_key: CorrectionKeyStr
    # If omitted, inherits the original record's occurrence time
    occurred_at: datetime | None = None


class TransactionResponse(BaseModel):
    id: int
    amount: int
    reason: str
    occurred_at: UtcDatetime
    created_at: UtcDatetime
    reversal_of_id: int | None
    # For a corrected record, the ID of the record it restates (ADR-0022)
    corrects_id: int | None
    is_reversed: bool
    granted_by: str | None


class CorrectionResponse(BaseModel):
    """The two rows added by one correction. The original record stays in the history."""

    reversal: TransactionResponse
    correction: TransactionResponse


class LedgerResponse(BaseModel):
    ledger_id: int
    family_id: int
    membership_id: int
    display_name: str
    balance: int
    can_modify: bool
    transactions: list[TransactionResponse]
    # Daily bonus settings (ADR-0024). null if unset
    daily_bonus: DailyBonusResponse | None


# --- Archives (backup; ADR-0026) ---------------------------------------------

#: Upper limits on members and records in one archive.
#:
#: Unrealistically large for a family; not meant to narrow which archives pass, but a cap so
#: an import cannot write without bound in one request. The record limit applies to the
#: **whole archive** — applying it per ledger would multiply it by the number of members.
MAX_ARCHIVED_MEMBERS = 100
MAX_ARCHIVED_TRANSACTIONS = 20_000

#: A name meaningful only inside the file. DB IDs are not included (they differ at the restore destination)
ArchiveRefStr = Annotated[str, Field(min_length=1, max_length=32, pattern=r"^[A-Za-z0-9_-]+$")]


class ArchivedTransactionDocument(BaseModel):
    ref: ArchiveRefStr
    amount: Annotated[int, Field(ge=-AMOUNT_MAX, le=AMOUNT_MAX), AfterValidator(_non_zero)]
    reason: Annotated[NonBlankStr, Field(max_length=REASON_MAX_LENGTH)]
    occurred_at: UtcDatetime
    # Ref of the recording member. null for daily bonuses and rows by people who left the family
    granted_by: ArchiveRefStr | None = None
    reverses: ArchiveRefStr | None = None
    corrects: ArchiveRefStr | None = None


class ArchivedDailyBonusDocument(BaseModel):
    amount: Annotated[int, Field(ge=1, le=AMOUNT_MAX)]
    reason: Annotated[NonBlankStr, Field(max_length=REASON_MAX_LENGTH)]
    starts_on: date
    granted_through: date | None = None


class ArchivedLedgerDocument(BaseModel):
    # In writing order (oldest first). Reversals/corrections always come after their target
    transactions: Annotated[list[ArchivedTransactionDocument], Field(max_length=MAX_ARCHIVED_TRANSACTIONS)]
    daily_bonus: ArchivedDailyBonusDocument | None = None


class ArchivedMemberDocument(BaseModel):
    ref: ArchiveRefStr
    display_name: DisplayNameStr
    role: FamilyRole
    # Only role = child has a ledger
    ledger: ArchivedLedgerDocument | None = None


class FamilyArchiveDocument(BaseModel):
    """A whole-family archive. Both the export response and the import body.

    The same shape is used in both directions, so sending back the exported JSON as-is
    restores it.
    """

    # A marker to notice when another app's JSON is passed by mistake
    format: str
    version: int
    exported_at: UtcDatetime
    family_name: Annotated[NonBlankStr, Field(max_length=FAMILY_NAME_MAX_LENGTH)]
    # Rules agreed in the family (ADR-0027). Absent in version 1 archives, so defaults to None
    family_rules: Annotated[str, Field(max_length=FAMILY_RULES_MAX_LENGTH)] | None = None
    members: Annotated[list[ArchivedMemberDocument], Field(max_length=MAX_ARCHIVED_MEMBERS)]

    @model_validator(mode="after")
    def _within_the_transaction_cap(self) -> FamilyArchiveDocument:
        """The record limit is checked across the whole archive.

        Applied per ledger, merely listing members would multiply the limit (100 people ×
        20,000 rows). An import writes row by row within one request, so whatever passes
        occupies the DB and a worker accordingly.
        """
        written = sum(len(member.ledger.transactions) for member in self.members if member.ledger)
        if written > MAX_ARCHIVED_TRANSACTIONS:
            raise ValueError(f"cannot hold more than {MAX_ARCHIVED_TRANSACTIONS} transactions in total")
        return self


class ImportedFamilyResponse(BaseModel):
    """Import result. Counts are returned so a person can check how much was restored."""

    family_id: int
    name: str
    member_count: int
    transaction_count: int


__all__ = [
    "MAX_ARCHIVED_MEMBERS",
    "MAX_ARCHIVED_TRANSACTIONS",
    "ArchivedDailyBonusDocument",
    "ArchivedLedgerDocument",
    "ArchivedMemberDocument",
    "ArchivedTransactionDocument",
    "ChildCreateRequest",
    "CorrectionCreateRequest",
    "CorrectionResponse",
    "DailyBonusRequest",
    "DailyBonusResponse",
    "FamilyArchiveDocument",
    "FamilyCreateRequest",
    "FamilyDetailResponse",
    "FamilyRenameRequest",
    "FamilyRulesRequest",
    "FamilySummaryResponse",
    "ImportedFamilyResponse",
    "InvitationAcceptRequest",
    "InvitationCreateRequest",
    "InvitationRedeemRequest",
    "InvitationResponse",
    "LedgerResponse",
    "MemberOrderRequest",
    "MembershipResponse",
    "NonBlankStr",
    "RedeemedInvitationResponse",
    "ReversalCreateRequest",
    "RewardEventBoardResponse",
    "RewardEventCreateRequest",
    "RewardEventDeadlineRequest",
    "RewardEventResponse",
    "StickerResponse",
    "TemporaryPasswordResponse",
    "TransactionCreateRequest",
    "TransactionResponse",
]
