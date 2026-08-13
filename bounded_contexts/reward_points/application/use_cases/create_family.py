"""家族を作る。作った人がそのまま ``owner`` として参加する。

作れるのはどの家族にも所属していないアカウントだけ（ADR-0013）。すでに所属して
いる場合は、先に抜けて初期状態へ戻る。

入口の scope は ``family:manage``。親（member ロール）は最初から持っており、
子（guest ロール）は持たないので、子が家族を作る経路は scope で閉じる
（ADR-0018）。
"""

from __future__ import annotations

from dataclasses import dataclass

from bounded_contexts.reward_points.application.dto.family_dto import FamilyDetailDTO, MembershipDTO, detail_of
from bounded_contexts.reward_points.domain.exceptions import AlreadyBelongsToFamilyError
from bounded_contexts.reward_points.domain.repositories.family_membership_repository import (
    IFamilyMembershipRepository,
)
from bounded_contexts.reward_points.domain.repositories.family_repository import IFamilyRepository
from bounded_contexts.reward_points.domain.value_objects.family_role import FamilyRole


@dataclass(frozen=True, kw_only=True)
class CreateFamilyCommand:
    name: str
    account_id: int
    display_name: str


class CreateFamilyUseCase:
    def __init__(self, families: IFamilyRepository, memberships: IFamilyMembershipRepository) -> None:
        self._families = families
        self._memberships = memberships

    def execute(self, command: CreateFamilyCommand) -> FamilyDetailDTO:
        if self._memberships.list_for_account(command.account_id):
            raise AlreadyBelongsToFamilyError
        family = self._families.add(name=command.name)
        owner = self._memberships.add(
            family_id=family.id,
            account_id=command.account_id,
            role=FamilyRole.OWNER,
            display_name=command.display_name,
        )
        return detail_of(
            family,
            viewer=owner,
            memberships=(
                MembershipDTO(
                    id=owner.id,
                    display_name=owner.display_name_value,
                    role=owner.role,
                    is_linked=True,
                    is_me=True,
                    username=None,
                    ledger_id=None,
                    balance=None,
                ),
            ),
        )


__all__ = ["CreateFamilyCommand", "CreateFamilyUseCase"]
