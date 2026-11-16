"""Gacha (capsule toy machine) on a child's ledger (ADR-0060).

A parent sets up a machine per child ledger: a name, the price of one draw, and the prizes
with their weights (how likely each one is). "Miss" prizes are allowed, but a machine made
only of misses is refused — it would take points and never give anything.

One draw spends ``price`` from the ledger in the same transaction and picks one prize by
weight. The draw keeps a **snapshot** of the machine's name, the prize and the price, so
editing or deleting the machine later never rewrites what a child already won.

The ledger row of a draw uses the client's idempotency key split by the step ``gacha``
(``<key>#gacha``). ``#`` never appears in user-sent keys
(:func:`~...idempotency_key.is_derived`), so it cannot collide with hand-written rows.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from bounded_contexts.reward_points.domain.exceptions import GachaNeedsAPrizeError
from bounded_contexts.reward_points.domain.value_objects.idempotency_key import IdempotencyKey
from bounded_contexts.reward_points.domain.value_objects.point_amount import MAX_MAGNITUDE

#: Max length of a machine name and of a prize name. Short enough to sit on a capsule label
NAME_MAX_LENGTH = 50

#: Max prizes per machine. Kept to what fits in one list on a phone
MAX_PRIZES = 20

#: Max weight of one prize. Weights are relative, so a small range is enough
MAX_WEIGHT = 1000

#: Step of the idempotency key for the ledger row of a draw
IDEMPOTENCY_STEP = "gacha"

#: A bundle: pay for this many draws at once...
BUNDLE_PAID_DRAWS = 10
#: ...and get this many more for free (task #1047)
BUNDLE_BONUS_DRAWS = 1


def _check_name(value: str, *, what: str) -> None:
    if not value.strip():
        raise ValueError(f"{what} cannot be empty")
    if len(value) > NAME_MAX_LENGTH:
        raise ValueError(f"{what} cannot exceed {NAME_MAX_LENGTH} characters")


@dataclass(frozen=True, kw_only=True)
class GachaPrize:
    """One prize in a machine. ``weight`` is relative to the other prizes' weights."""

    name: str
    weight: int
    is_miss: bool = False

    def __post_init__(self) -> None:
        _check_name(self.name, what="Prize name")
        if not 1 <= self.weight <= MAX_WEIGHT:
            raise ValueError(f"Prize weight must be 1..{MAX_WEIGHT}")


@dataclass(frozen=True, kw_only=True)
class GachaDesign:
    """What a parent decides about a machine: name, price and prizes (in display order)."""

    name: str
    price: int
    prizes: tuple[GachaPrize, ...]

    def __post_init__(self) -> None:
        _check_name(self.name, what="Gacha name")
        if not 1 <= self.price <= MAX_MAGNITUDE:
            raise ValueError(f"Gacha price must be 1..{MAX_MAGNITUDE}")
        if not 1 <= len(self.prizes) <= MAX_PRIZES:
            raise ValueError(f"A gacha holds 1..{MAX_PRIZES} prizes")
        if all(prize.is_miss for prize in self.prizes):
            raise GachaNeedsAPrizeError

    @property
    def total_weight(self) -> int:
        return sum(prize.weight for prize in self.prizes)

    def pick(self, roll: int) -> GachaPrize:
        """The prize that *roll* lands on. *roll* is uniform in ``0 .. total_weight - 1``.

        Prizes take up consecutive ranges as wide as their weight, in display order.
        """
        if not 0 <= roll < self.total_weight:
            raise ValueError("Roll must be within the total weight")
        for prize in self.prizes:
            if roll < prize.weight:
                return prize
            roll -= prize.weight
        raise AssertionError("unreachable: roll is below the total weight")


@dataclass(frozen=True, kw_only=True)
class Gacha:
    id: int
    ledger_id: int
    design: GachaDesign
    created_at: datetime


@dataclass(frozen=True, kw_only=True)
class GachaDraw:
    """One draw and what it won. Names and price are copied from the machine at draw time."""

    id: int
    ledger_id: int
    #: ``None`` once the machine is deleted (the draw stays)
    gacha_id: int | None
    gacha_name: str
    prize_name: str
    is_miss: bool
    price: int
    drawn_at: datetime
    #: When a parent handed the real prize over. ``None`` if not yet (always ``None`` for a miss)
    handed_over_at: datetime | None = None
    #: The free extra draw of a bundle (nothing was paid for it)
    is_bonus: bool = False

    @property
    def is_handed_over(self) -> bool:
        return self.handed_over_at is not None


def ledger_reason(*, gacha_name: str, prize_name: str) -> str:
    """Reason of the ledger row of a draw, e.g. ``おかしガチャ: チョコ``.

    Both names are language-neutral data typed by the parent, so the history reads the same
    in every UI language.
    """
    return f"{gacha_name}: {prize_name}"


def draw_ledger_key(client_key: str) -> str:
    """Idempotency key of the ledger row for the draw sent with *client_key*."""
    return IdempotencyKey(client_key).for_step(IDEMPOTENCY_STEP).value


def bundle_draw_key(client_key: str, number: int) -> str:
    """Key of draw *number* (1..) of the bundle sent with *client_key*, e.g. ``<key>#3``.

    ``#`` never appears in client keys, so these never collide with a single draw's key.
    """
    return IdempotencyKey(client_key).for_step(str(number)).value


def bundle_ledger_key(client_key: str, number: int) -> str:
    """Idempotency key of the ledger row paying for draw *number* of a bundle (``<key>#g3``)."""
    return IdempotencyKey(client_key).for_step(f"g{number}").value


__all__ = [
    "BUNDLE_BONUS_DRAWS",
    "BUNDLE_PAID_DRAWS",
    "IDEMPOTENCY_STEP",
    "MAX_PRIZES",
    "MAX_WEIGHT",
    "NAME_MAX_LENGTH",
    "Gacha",
    "GachaDesign",
    "GachaDraw",
    "GachaPrize",
    "bundle_draw_key",
    "bundle_ledger_key",
    "draw_ledger_key",
    "ledger_reason",
]
