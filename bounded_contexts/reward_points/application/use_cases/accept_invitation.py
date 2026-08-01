"""すでにアカウントを持つ人が、招待コードで家族へ加わる。

受諾（accept）で加われるのは親（parent）としてだけ（ADR-0018）。

- 親の招待を使えるのは、保護者になれるアカウント（member ロール）だけ。
  子（guest）が使うと「名ばかりの保護者」になってしまうため断る。
  子の大人化は独立（ADR-0014）か管理者のロール変更で行う。
- 子の招待はアカウントの新規作成（redeem — ADR-0011）でだけ使える。既存の
  アカウントを子として結び付けると、除名の後始末（アカウント削除）が独立に
  存在するアカウントを巻き込んでしまう。
"""

from __future__ import annotations

from dataclasses import dataclass

from bounded_contexts.reward_points.application.dto.family_dto import RedeemedInvitationDTO
from bounded_contexts.reward_points.application.invitation_binder import InvitationBinder
from bounded_contexts.reward_points.domain.exceptions import (
    ChildInvitationRequiresSignupError,
    FamilyNotFoundError,
    GuardianAccountRequiredError,
)
from bounded_contexts.reward_points.domain.repositories.family_repository import IFamilyRepository


@dataclass(frozen=True, kw_only=True)
class AcceptInvitationCommand:
    code: str
    account_id: int
    username: str
    display_name: str | None
    # 呼び出し元が保護者の scope（family:manage）を持つか（Presentation 層で検証済み）
    can_guard: bool


class AcceptInvitationUseCase:
    def __init__(self, binder: InvitationBinder, families: IFamilyRepository) -> None:
        self._binder = binder
        self._families = families

    def execute(self, command: AcceptInvitationCommand) -> RedeemedInvitationDTO:
        membership = self._binder.bind(
            code=command.code,
            account_id=command.account_id,
            display_name=command.display_name,
        )
        # ここで弾くとトランザクションごと巻き戻るので、招待コードは消費されない
        if membership.role.has_own_ledger:
            raise ChildInvitationRequiresSignupError
        if membership.role.is_guardian and not command.can_guard:
            raise GuardianAccountRequiredError
        family = self._families.find_by_id(membership.family_id)
        if family is None:
            raise FamilyNotFoundError
        return RedeemedInvitationDTO(
            family_id=family.id,
            family_name=family.name_value,
            membership_id=membership.id,
            role=membership.role,
            username=command.username,
        )


__all__ = ["AcceptInvitationCommand", "AcceptInvitationUseCase"]
