"""家族を作る。作った人がそのまま ``owner`` として参加する。

作れるのはどの家族にも所属していないアカウントだけ（ADR-0013）。すでに所属して
いる場合は、先に抜けて初期状態へ戻る。

所属の経路は「招待を受ける」か「自分で作る」の 2 つだけなので、作成は閲覧の
scope（``family:view``）で呼べる入口とし、成立した時点で作成者を親（メンバー）と
同じアプリケーションロールへ昇格する（ADR-0017）。昇格しないと、owner なのに
子の追加もポイントの記録もできない。
"""

from __future__ import annotations

from dataclasses import dataclass

from bounded_contexts.reward_points.application.dto.family_dto import FamilyDetailDTO, MembershipDTO
from bounded_contexts.reward_points.domain.exceptions import AlreadyBelongsToFamilyError
from bounded_contexts.reward_points.domain.repositories.account_directory import IAccountProvisioning
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
    def __init__(
        self,
        families: IFamilyRepository,
        memberships: IFamilyMembershipRepository,
        provisioning: IAccountProvisioning,
    ) -> None:
        self._families = families
        self._memberships = memberships
        self._provisioning = provisioning

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
        self._provisioning.grant_guardian_permissions(command.account_id)
        return FamilyDetailDTO(
            id=family.id,
            name=family.name_value,
            my_membership_id=owner.id,
            my_role=owner.role,
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
