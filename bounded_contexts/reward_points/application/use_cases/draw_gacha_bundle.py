"""Draw a gacha ten times at once and get one more free (task #1047, ADR-0060).

The bundle is eleven ordinary draws, not one: the server picks a prize by weight for each,
in order. The first ten each spend the price (one ledger row each, like a single draw); the
eleventh is free (no ledger row) and marked as the bonus.

The balance must cover all ten paid draws, checked under the same ledger lock as a single
draw. The client sends one key per press; each draw's key is derived from it (``<key>#1``
.. ``<key>#11``), so a resent press returns the bundle already drawn.
"""

from __future__ import annotations

import secrets

from bounded_contexts.reward_points.application.dto.gacha_dto import GachaBundleResultDTO, draw_to_dto
from bounded_contexts.reward_points.application.family_access_resolver import FamilyAccessResolver
from bounded_contexts.reward_points.application.use_cases.draw_gacha import (
    DrawGachaCommand,
    GachaDrawWriter,
    OneDraw,
    Roll,
)
from bounded_contexts.reward_points.domain.entities.gacha import (
    BUNDLE_BONUS_DRAWS,
    BUNDLE_PAID_DRAWS,
    bundle_draw_key,
    bundle_ledger_key,
)
from bounded_contexts.reward_points.domain.exceptions import (
    GachaNotFoundError,
    IdempotencyKeyReusedError,
    InsufficientBalanceError,
)
from bounded_contexts.reward_points.domain.repositories.gacha_repository import (
    IGachaDrawRepository,
    IGachaRepository,
)
from bounded_contexts.reward_points.domain.repositories.point_transaction_repository import (
    IPointTransactionRepository,
)

_DRAWS = BUNDLE_PAID_DRAWS + BUNDLE_BONUS_DRAWS


class DrawGachaBundleUseCase:
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
        self._writer = GachaDrawWriter(transactions=transactions, draws=draws, roll=roll)

    def execute(self, command: DrawGachaCommand) -> GachaBundleResultDTO:
        found = self._access.drawable_ledger(ledger_id=command.ledger_id, account_id=command.account_id)
        balance = self._draws.lock_ledger_balance(found.ledger.id)
        keys = [bundle_draw_key(command.idempotency_key, number) for number in range(1, _DRAWS + 1)]
        existing = self._draws.find_by_keys(ledger_id=found.ledger.id, idempotency_keys=keys)
        if existing:
            if any(draw.gacha_id != command.gacha_id for draw in existing):
                raise IdempotencyKeyReusedError
            return GachaBundleResultDTO(draws=tuple(draw_to_dto(draw) for draw in existing), balance=balance)
        gacha = self._gachas.find_in_ledger(ledger_id=found.ledger.id, gacha_id=command.gacha_id)
        if gacha is None:
            raise GachaNotFoundError
        cost = gacha.design.price * BUNDLE_PAID_DRAWS
        if balance < cost:
            raise InsufficientBalanceError
        drawn = [
            self._writer.draw(
                found,
                gacha,
                OneDraw(
                    draw_key=key,
                    ledger_key=bundle_ledger_key(command.idempotency_key, number)
                    if number <= BUNDLE_PAID_DRAWS
                    else None,
                    is_bonus=number > BUNDLE_PAID_DRAWS,
                ),
            )
            for number, key in enumerate(keys, start=1)
        ]
        return GachaBundleResultDTO(draws=tuple(draw_to_dto(draw) for draw in drawn), balance=balance - cost)


__all__ = ["DrawGachaBundleUseCase"]
