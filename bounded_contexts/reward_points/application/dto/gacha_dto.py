"""Output DTOs for gacha machines and draws (ADR-0060)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from bounded_contexts.reward_points.domain.entities.gacha import Gacha, GachaDraw


@dataclass(frozen=True, kw_only=True)
class GachaPrizeDTO:
    name: str
    weight: int
    is_miss: bool


@dataclass(frozen=True, kw_only=True)
class GachaDTO:
    id: int
    ledger_id: int
    name: str
    price: int
    #: In display order
    prizes: tuple[GachaPrizeDTO, ...]
    created_at: datetime


@dataclass(frozen=True, kw_only=True)
class GachaDrawDTO:
    id: int
    gacha_id: int | None
    gacha_name: str
    prize_name: str
    is_miss: bool
    price: int
    drawn_at: datetime
    handed_over_at: datetime | None


@dataclass(frozen=True, kw_only=True)
class GachaDrawResultDTO:
    """A draw and the ledger balance right after it."""

    draw: GachaDrawDTO
    balance: int


@dataclass(frozen=True, kw_only=True)
class GachaBoardDTO:
    """One child's machines and recent draws, with what the screen needs to decide what to show."""

    ledger_id: int
    display_name: str
    balance: int
    can_modify: bool
    can_draw: bool
    gachas: tuple[GachaDTO, ...]
    #: Newest first
    draws: tuple[GachaDrawDTO, ...]


def gacha_to_dto(gacha: Gacha) -> GachaDTO:
    return GachaDTO(
        id=gacha.id,
        ledger_id=gacha.ledger_id,
        name=gacha.design.name,
        price=gacha.design.price,
        prizes=tuple(
            GachaPrizeDTO(name=prize.name, weight=prize.weight, is_miss=prize.is_miss) for prize in gacha.design.prizes
        ),
        created_at=gacha.created_at,
    )


def draw_to_dto(draw: GachaDraw) -> GachaDrawDTO:
    return GachaDrawDTO(
        id=draw.id,
        gacha_id=draw.gacha_id,
        gacha_name=draw.gacha_name,
        prize_name=draw.prize_name,
        is_miss=draw.is_miss,
        price=draw.price,
        drawn_at=draw.drawn_at,
        handed_over_at=draw.handed_over_at,
    )


__all__ = [
    "GachaBoardDTO",
    "GachaDTO",
    "GachaDrawDTO",
    "GachaDrawResultDTO",
    "GachaPrizeDTO",
    "draw_to_dto",
    "gacha_to_dto",
]
