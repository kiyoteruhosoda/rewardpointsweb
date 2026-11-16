"""Pydantic schemas of the gacha API (ADR-0060).

Lengths and limits use the constants of the domain entity (never copy the numbers).
"""

from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, Field

from bounded_contexts.reward_points.domain.entities.gacha import MAX_PRIZES, MAX_WEIGHT, NAME_MAX_LENGTH
from bounded_contexts.reward_points.domain.value_objects.point_amount import MAX_MAGNITUDE as AMOUNT_MAX
from bounded_contexts.reward_points.presentation.schemas import CorrectionKeyStr, NonBlankStr
from presentation.fastapi.schemas.types import UtcDatetime

GachaNameStr = Annotated[NonBlankStr, Field(max_length=NAME_MAX_LENGTH)]


class GachaPrizeRequest(BaseModel):
    name: GachaNameStr
    # Relative to the other prizes' weights (2 is twice as likely as 1)
    weight: Annotated[int, Field(ge=1, le=MAX_WEIGHT)]
    is_miss: bool = False


class GachaSaveRequest(BaseModel):
    """The whole machine. Editing replaces all prizes (past draws keep what they won)."""

    name: GachaNameStr
    price: Annotated[int, Field(ge=1, le=AMOUNT_MAX)]
    # In display order. At least one must not be a miss
    prizes: Annotated[list[GachaPrizeRequest], Field(min_length=1, max_length=MAX_PRIZES)]


class GachaDrawRequest(BaseModel):
    # One per press, resent unchanged on retry. The ledger row uses it split by step, so it
    # is limited to a length that still fits after splitting
    idempotency_key: CorrectionKeyStr


class GachaPrizeResponse(BaseModel):
    name: str
    weight: int
    is_miss: bool


class GachaResponse(BaseModel):
    id: int
    ledger_id: int
    name: str
    price: int
    prizes: list[GachaPrizeResponse]
    created_at: UtcDatetime


class GachaDrawResponse(BaseModel):
    id: int
    # null once the machine is deleted
    gacha_id: int | None
    gacha_name: str
    prize_name: str
    is_miss: bool
    price: int
    drawn_at: UtcDatetime
    # When a parent handed the prize over. null if not yet (always null for a miss)
    handed_over_at: UtcDatetime | None
    # The free extra draw of a bundle (10 paid + 1 free)
    is_bonus: bool


class GachaDrawResultResponse(BaseModel):
    draw: GachaDrawResponse
    # Ledger balance right after the draw
    balance: int


class GachaBundleResultResponse(BaseModel):
    """Eleven draws in the order drawn (the last one free), and the balance right after."""

    draws: list[GachaDrawResponse]
    balance: int


class GachaTrialResponse(BaseModel):
    """What a parent's trial draw won. Nothing was spent or recorded."""

    gacha_name: str
    prize_name: str
    is_miss: bool


class GachaBoardResponse(BaseModel):
    ledger_id: int
    display_name: str
    balance: int
    # Whether to show create, edit, delete and "handed over"
    can_modify: bool
    # Whether to show the draw button (parents, and the child on their own ledger)
    can_draw: bool
    gachas: list[GachaResponse]
    # Newest first, up to 100
    draws: list[GachaDrawResponse]


__all__ = [
    "GachaBoardResponse",
    "GachaBundleResultResponse",
    "GachaDrawRequest",
    "GachaDrawResponse",
    "GachaDrawResultResponse",
    "GachaPrizeRequest",
    "GachaPrizeResponse",
    "GachaResponse",
    "GachaSaveRequest",
    "GachaTrialResponse",
]
