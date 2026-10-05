"""招待コードでアカウントを作り、そのまま家族へ加わる（未認証で呼べる）。

子アカウントの作り方はこの 1 本だけ。子ども自身では作れず、親が参加を作って
招待コードを渡した場合にのみ成立する（ADR-0011）。メールアドレスは受け取らない。

作成後はログインしていない。呼び出し側（画面）は、設定した ``username`` と
パスワードで通常どおりログインする。

⚠ **IdP（SSO）があるとき、親の招待はここで使えない**（ADR-0048）。大人の口座は
IdP で入ったときに作る 1 つだけにし、親はログインしてから受諾（accept）で加わる。
ここで作るとメールアドレスを持たない別の口座になり、IdP の口座と結び付ける手掛かりが
無いので、初めて SSO で入ったときに同じ人の口座が 2 つになる。
"""

from __future__ import annotations

from dataclasses import dataclass

from bounded_contexts.reward_points.application.dto.family_dto import RedeemedInvitationDTO
from bounded_contexts.reward_points.application.invitation_binder import InvitationBinder
from bounded_contexts.reward_points.domain.exceptions import (
    FamilyNotFoundError,
    GuardianInvitationRequiresSignInError,
    InvitationNotFoundError,
    UsernameAlreadyTakenError,
)
from bounded_contexts.reward_points.domain.repositories.account_directory import IAccountProvisioning
from bounded_contexts.reward_points.domain.repositories.family_invitation_repository import (
    IFamilyInvitationRepository,
)
from bounded_contexts.reward_points.domain.repositories.family_repository import IFamilyRepository
from shared.kernel.timestamps import utcnow


@dataclass(frozen=True, kw_only=True)
class RedeemInvitationCommand:
    code: str
    username: str
    password: str
    display_name: str | None


class RedeemInvitationUseCase:
    def __init__(
        self,
        *,
        binder: InvitationBinder,
        invitations: IFamilyInvitationRepository,
        families: IFamilyRepository,
        provisioning: IAccountProvisioning,
        adults_sign_in_through_idp: bool,
    ) -> None:
        self._binder = binder
        self._invitations = invitations
        self._families = families
        self._provisioning = provisioning
        self._adults_sign_in_through_idp = adults_sign_in_through_idp

    def execute(self, command: RedeemInvitationCommand) -> RedeemedInvitationDTO:
        invitation = self._invitations.find_by_code(command.code)
        # アカウントを作る前にコードを確かめる。作ってから弾くと、無効なコードでも
        # ログイン ID を消費できてしまう
        if invitation is None or not invitation.is_usable_at(utcnow()):
            raise InvitationNotFoundError
        if invitation.role.is_guardian and self._adults_sign_in_through_idp:
            raise GuardianInvitationRequiresSignInError
        if self._provisioning.is_username_taken(command.username):
            raise UsernameAlreadyTakenError

        account = self._provisioning.create_account(
            username=command.username,
            password=command.password,
            role=invitation.role,
            # 本人が名乗った名前をアカウントの表示名にもする。参加が用意済みの
            # 招待では家族の中での呼び名は親が決めた値のままなので、ここで使わないと
            # 入力した名前がどこにも残らない
            display_name=command.display_name,
        )
        membership = self._binder.bind(
            code=command.code,
            account_id=account.account_id,
            display_name=command.display_name,
        )
        family = self._families.find_by_id(membership.family_id)
        if family is None:
            raise FamilyNotFoundError
        return RedeemedInvitationDTO(
            family_id=family.id,
            family_name=family.name_value,
            membership_id=membership.id,
            role=membership.role,
            username=account.username,
        )


__all__ = ["RedeemInvitationCommand", "RedeemInvitationUseCase"]
