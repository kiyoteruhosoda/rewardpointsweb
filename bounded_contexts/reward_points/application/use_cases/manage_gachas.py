"""View, create, edit and delete gacha machines (ADR-0060).

Anyone who can view the ledger can view its machines and draws (a child sees their own).
Creating, editing and deleting are only for those who can change the ledger (parents): the
price decides how many points a draw takes from the ledger.
"""

from __future__ import annotations

from dataclasses import dataclass

from bounded_contexts.reward_points.application.dto.gacha_dto import (
    GachaBoardDTO,
    GachaDTO,
    draw_to_dto,
    gacha_to_dto,
)
from bounded_contexts.reward_points.application.family_access_resolver import FamilyAccessResolver
from bounded_contexts.reward_points.domain.entities.gacha import Gacha, GachaDesign
from bounded_contexts.reward_points.domain.exceptions import GachaNotFoundError, MembershipNotFoundError
from bounded_contexts.reward_points.domain.repositories.family_membership_repository import (
    IFamilyMembershipRepository,
)
from bounded_contexts.reward_points.domain.repositories.gacha_repository import (
    IGachaDrawRepository,
    IGachaRepository,
)
from bounded_contexts.reward_points.domain.repositories.point_transaction_repository import (
    IPointTransactionRepository,
)
from bounded_contexts.reward_points.domain.services import family_access_policy
from bounded_contexts.reward_points.domain.services.ledger_statement import LedgerStatement

#: How many past draws the board returns. Enough to find prizes not handed over yet
RECENT_DRAWS_LIMIT = 100


@dataclass(frozen=True, kw_only=True)
class GachaRepositories:
    """The stores the board reads from, bundled to keep the constructor short."""

    gachas: IGachaRepository
    draws: IGachaDrawRepository
    transactions: IPointTransactionRepository
    memberships: IFamilyMembershipRepository


class ViewGachaBoardUseCase:
    def __init__(self, access: FamilyAccessResolver, stores: GachaRepositories) -> None:
        self._access = access
        self._stores = stores

    def execute(self, *, ledger_id: int, account_id: int) -> GachaBoardDTO:
        found = self._access.viewable_ledger(ledger_id=ledger_id, account_id=account_id)
        owner = self._stores.memberships.find_by_id(found.ledger.membership_id)
        if owner is None:
            raise MembershipNotFoundError
        statement = LedgerStatement(self._stores.transactions.list_by_ledger(found.ledger.id))
        return GachaBoardDTO(
            ledger_id=found.ledger.id,
            display_name=owner.display_name_value,
            balance=statement.balance.value,
            can_modify=family_access_policy.can_modify_ledger(found.membership, found.ledger),
            can_draw=family_access_policy.can_draw_gacha(found.membership, found.ledger),
            gachas=tuple(gacha_to_dto(gacha) for gacha in self._stores.gachas.list_by_ledger(found.ledger.id)),
            draws=tuple(
                draw_to_dto(draw)
                for draw in self._stores.draws.list_recent(ledger_id=found.ledger.id, limit=RECENT_DRAWS_LIMIT)
            ),
        )


@dataclass(frozen=True, kw_only=True)
class SaveGachaCommand:
    ledger_id: int
    account_id: int
    design: GachaDesign
    #: ``None`` creates a new machine; otherwise the machine to replace
    gacha_id: int | None = None


class SaveGachaUseCase:
    """Create a machine, or replace an existing machine's name, price and prizes."""

    def __init__(self, access: FamilyAccessResolver, gachas: IGachaRepository) -> None:
        self._access = access
        self._gachas = gachas

    def execute(self, command: SaveGachaCommand) -> GachaDTO:
        found = self._access.modifiable_ledger(ledger_id=command.ledger_id, account_id=command.account_id)
        if command.gacha_id is None:
            return gacha_to_dto(self._gachas.add(ledger_id=found.ledger.id, design=command.design))
        existing = _find(self._gachas, ledger_id=found.ledger.id, gacha_id=command.gacha_id)
        self._gachas.replace_design(gacha_id=existing.id, design=command.design)
        return gacha_to_dto(_find(self._gachas, ledger_id=found.ledger.id, gacha_id=existing.id))


class DeleteGachaUseCase:
    """Delete a machine. Draws and their ledger rows stay (the draws hold a snapshot).

    Succeeds even if the machine is already gone (the wish to delete it is satisfied).
    """

    def __init__(self, access: FamilyAccessResolver, gachas: IGachaRepository) -> None:
        self._access = access
        self._gachas = gachas

    def execute(self, *, ledger_id: int, gacha_id: int, account_id: int) -> None:
        found = self._access.modifiable_ledger(ledger_id=ledger_id, account_id=account_id)
        if self._gachas.find_in_ledger(ledger_id=found.ledger.id, gacha_id=gacha_id) is not None:
            self._gachas.delete(gacha_id)


def _find(gachas: IGachaRepository, *, ledger_id: int, gacha_id: int) -> Gacha:
    gacha = gachas.find_in_ledger(ledger_id=ledger_id, gacha_id=gacha_id)
    if gacha is None:
        raise GachaNotFoundError
    return gacha


__all__ = [
    "RECENT_DRAWS_LIMIT",
    "DeleteGachaUseCase",
    "GachaRepositories",
    "SaveGachaCommand",
    "SaveGachaUseCase",
    "ViewGachaBoardUseCase",
]
