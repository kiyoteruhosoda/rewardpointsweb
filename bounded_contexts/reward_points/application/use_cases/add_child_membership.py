"""子の参加を作る（owner / parent）。

この時点ではアカウントが無い。台帳だけ先に用意し、子が招待コードで自分の
アカウントを作った時点で結び付く（ADR-0009 / ADR-0011）。
"""

from __future__ import annotations

from dataclasses import dataclass

from bounded_contexts.reward_points.application.dto.family_dto import MembershipDTO
from bounded_contexts.reward_points.application.family_access_resolver import FamilyAccessResolver
from bounded_contexts.reward_points.domain.repositories.family_membership_repository import (
    IFamilyMembershipRepository,
)
from bounded_contexts.reward_points.domain.repositories.point_ledger_repository import IPointLedgerRepository
from bounded_contexts.reward_points.domain.value_objects.family_role import FamilyRole


@dataclass(frozen=True, kw_only=True)
class AddChildMembershipCommand:
    family_id: int
    account_id: int
    display_name: str


class AddChildMembershipUseCase:
    def __init__(
        self,
        access: FamilyAccessResolver,
        memberships: IFamilyMembershipRepository,
        ledgers: IPointLedgerRepository,
    ) -> None:
        self._access = access
        self._memberships = memberships
        self._ledgers = ledgers

    def execute(self, command: AddChildMembershipCommand) -> MembershipDTO:
        self._access.require_guardian(family_id=command.family_id, account_id=command.account_id)
        child = self._memberships.add(
            family_id=command.family_id,
            account_id=None,
            role=FamilyRole.CHILD,
            display_name=command.display_name,
        )
        ledger = self._ledgers.add(family_id=command.family_id, membership_id=child.id)
        return MembershipDTO(
            id=child.id,
            display_name=child.display_name_value,
            role=child.role,
            is_linked=False,
            is_me=False,
            username=None,
            ledger_id=ledger.id,
            balance=0,
        )


__all__ = ["AddChildMembershipCommand", "AddChildMembershipUseCase"]
