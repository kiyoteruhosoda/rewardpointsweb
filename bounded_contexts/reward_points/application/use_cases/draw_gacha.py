"""Draw a gacha, and mark won prizes as handed over (ADR-0060).

One draw does three things in one transaction: it spends the price from the ledger (one
append-only row; ADR-0010), picks a prize by weight on the server, and records the draw.

- **Who**: parents for any child, and the child on their own ledger
  (:func:`~...family_access_policy.can_draw_gacha`). Display devices never.
- **Balance**: a draw is refused when the balance does not cover the price. The ledger is
  locked first, so two draws arriving together cannot both spend the same points.
- **Once per press**: the client sends an idempotency key per press. A resend (double tap,
  network retry) returns the draw already made instead of drawing again.

Handing over is a parent's job: the prize is something real the parent gives.
"""

from __future__ import annotations

import secrets
from collections.abc import Callable
from dataclasses import dataclass

from bounded_contexts.reward_points.application.dto.gacha_dto import (
    GachaDrawDTO,
    GachaDrawResultDTO,
    GachaTrialDTO,
    draw_to_dto,
)
from bounded_contexts.reward_points.application.family_access_resolver import FamilyAccessResolver, LedgerAccess
from bounded_contexts.reward_points.domain.entities.gacha import (
    Gacha,
    GachaDraw,
    draw_ledger_key,
    ledger_reason,
)
from bounded_contexts.reward_points.domain.exceptions import (
    GachaDrawNotFoundError,
    GachaNotFoundError,
    IdempotencyKeyReusedError,
    InsufficientBalanceError,
    MissCannotBeHandedOverError,
)
from bounded_contexts.reward_points.domain.repositories.gacha_repository import (
    IGachaDrawRepository,
    IGachaRepository,
    NewGachaDraw,
)
from bounded_contexts.reward_points.domain.repositories.point_transaction_repository import (
    IPointTransactionRepository,
    NewTransaction,
)
from shared.kernel.timestamps import utcnow

#: Returns a uniform integer in ``0 .. bound - 1``. Swapped in tests to fix the outcome
Roll = Callable[[int], int]


@dataclass(frozen=True, kw_only=True)
class DrawGachaCommand:
    ledger_id: int
    gacha_id: int
    account_id: int
    #: One per press, carried over until the press succeeds
    idempotency_key: str


class DrawGachaUseCase:
    def __init__(
        self,
        *,
        access: FamilyAccessResolver,
        gachas: IGachaRepository,
        draws: IGachaDrawRepository,
        transactions: IPointTransactionRepository,
        roll: Roll = secrets.randbelow,
    ) -> None:
        self._access = access
        self._gachas = gachas
        self._draws = draws
        self._transactions = transactions
        self._roll = roll

    def execute(self, command: DrawGachaCommand) -> GachaDrawResultDTO:
        found = self._access.drawable_ledger(ledger_id=command.ledger_id, account_id=command.account_id)
        # Lock before looking for a resend: the other request with the same key may be
        # committing right now, and must be seen once it has
        balance = self._draws.lock_ledger_balance(found.ledger.id)
        existing = self._draws.find_by_key(ledger_id=found.ledger.id, idempotency_key=command.idempotency_key)
        if existing is not None:
            if existing.gacha_id != command.gacha_id:
                raise IdempotencyKeyReusedError
            return GachaDrawResultDTO(draw=draw_to_dto(existing), balance=balance)
        gacha = self._gachas.find_in_ledger(ledger_id=found.ledger.id, gacha_id=command.gacha_id)
        if gacha is None:
            raise GachaNotFoundError
        if balance < gacha.design.price:
            raise InsufficientBalanceError
        draw = self._draw(found, gacha, command.idempotency_key)
        return GachaDrawResultDTO(draw=draw_to_dto(draw), balance=balance - gacha.design.price)

    def _draw(self, found: LedgerAccess, gacha: Gacha, client_key: str) -> GachaDraw:
        design = gacha.design
        prize = design.pick(self._roll(design.total_weight))
        now = utcnow()
        spent = self._transactions.append(
            NewTransaction(
                ledger_id=found.ledger.id,
                amount=-design.price,
                reason=ledger_reason(gacha_name=design.name, prize_name=prize.name),
                granted_by_membership_id=found.membership.id,
                occurred_at=now,
                idempotency_key=draw_ledger_key(client_key),
            )
        )
        return self._draws.add(
            NewGachaDraw(
                ledger_id=found.ledger.id,
                gacha_id=gacha.id,
                gacha_name=design.name,
                prize_name=prize.name,
                is_miss=prize.is_miss,
                price=design.price,
                idempotency_key=client_key,
                transaction_id=spent.id,
                drawn_by_membership_id=found.membership.id,
                drawn_at=now,
            )
        )


class TryGachaUseCase:
    """A parent's trial draw: pick a prize the same way, but spend and record nothing.

    Lets a parent check the machine and its show before a child uses it. Only those who can
    change the ledger may try (a child would get free draws otherwise).
    """

    def __init__(self, access: FamilyAccessResolver, gachas: IGachaRepository, roll: Roll = secrets.randbelow) -> None:
        self._access = access
        self._gachas = gachas
        self._roll = roll

    def execute(self, *, ledger_id: int, gacha_id: int, account_id: int) -> GachaTrialDTO:
        found = self._access.modifiable_ledger(ledger_id=ledger_id, account_id=account_id)
        gacha = self._gachas.find_in_ledger(ledger_id=found.ledger.id, gacha_id=gacha_id)
        if gacha is None:
            raise GachaNotFoundError
        prize = gacha.design.pick(self._roll(gacha.design.total_weight))
        return GachaTrialDTO(gacha_name=gacha.design.name, prize_name=prize.name, is_miss=prize.is_miss)


@dataclass(frozen=True, kw_only=True)
class HandOverCommand:
    ledger_id: int
    draw_id: int
    account_id: int
    #: True marks it handed over; false takes the mark back (a mis-tap)
    handed_over: bool


class HandOverGachaPrizeUseCase:
    """Mark a won prize as handed over, or take the mark back. Repeating either is harmless."""

    def __init__(self, access: FamilyAccessResolver, draws: IGachaDrawRepository) -> None:
        self._access = access
        self._draws = draws

    def execute(self, command: HandOverCommand) -> GachaDrawDTO:
        found = self._access.modifiable_ledger(ledger_id=command.ledger_id, account_id=command.account_id)
        draw = self._find(found.ledger.id, command.draw_id)
        if draw.is_miss:
            raise MissCannotBeHandedOverError
        if command.handed_over != draw.is_handed_over:
            self._draws.set_handed_over(
                draw_id=draw.id,
                handed_over_at=utcnow() if command.handed_over else None,
                by_membership_id=found.membership.id if command.handed_over else None,
            )
            draw = self._find(found.ledger.id, draw.id)
        return draw_to_dto(draw)

    def _find(self, ledger_id: int, draw_id: int) -> GachaDraw:
        draw = self._draws.find_in_ledger(ledger_id=ledger_id, draw_id=draw_id)
        if draw is None:
            raise GachaDrawNotFoundError
        return draw


__all__ = [
    "DrawGachaCommand",
    "DrawGachaUseCase",
    "HandOverCommand",
    "HandOverGachaPrizeUseCase",
    "Roll",
    "TryGachaUseCase",
]
