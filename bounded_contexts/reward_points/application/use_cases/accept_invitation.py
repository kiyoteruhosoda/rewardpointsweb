"""すでにアカウントを持つ人が、招待コードで家族へ加わる。

親（parent）として加わったら、アプリケーションロールも親（メンバー）と同じへ
昇格する（ADR-0017）。子の閲覧専用ロールのままだと、家族の中では親なのに
ポイントを記録できない。
"""

from __future__ import annotations

from dataclasses import dataclass

from bounded_contexts.reward_points.application.dto.family_dto import RedeemedInvitationDTO
from bounded_contexts.reward_points.application.invitation_binder import InvitationBinder
from bounded_contexts.reward_points.domain.exceptions import FamilyNotFoundError
from bounded_contexts.reward_points.domain.repositories.account_directory import IAccountProvisioning
from bounded_contexts.reward_points.domain.repositories.family_repository import IFamilyRepository


@dataclass(frozen=True, kw_only=True)
class AcceptInvitationCommand:
    code: str
    account_id: int
    username: str
    display_name: str | None


class AcceptInvitationUseCase:
    def __init__(
        self, binder: InvitationBinder, families: IFamilyRepository, provisioning: IAccountProvisioning
    ) -> None:
        self._binder = binder
        self._families = families
        self._provisioning = provisioning

    def execute(self, command: AcceptInvitationCommand) -> RedeemedInvitationDTO:
        membership = self._binder.bind(
            code=command.code,
            account_id=command.account_id,
            display_name=command.display_name,
        )
        family = self._families.find_by_id(membership.family_id)
        if family is None:
            raise FamilyNotFoundError
        if membership.role.is_guardian:
            self._provisioning.grant_guardian_permissions(command.account_id)
        return RedeemedInvitationDTO(
            family_id=family.id,
            family_name=family.name_value,
            membership_id=membership.id,
            role=membership.role,
            username=command.username,
        )


__all__ = ["AcceptInvitationCommand", "AcceptInvitationUseCase"]
