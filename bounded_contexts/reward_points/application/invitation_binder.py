"""招待コードを 1 つの参加へ変える、共通の処理。

招待の受諾には 2 つの入口がある。

- すでにアカウントを持つ人が家族へ加わる（``accept``）
- 子が自分の端末でアカウントを作って加わる（``redeem``。ADR-0011）

違うのは「アカウントをどう用意するか」だけで、コードの検証・参加の作成・
使用済みの記録は同じ。両方から呼べるようにここへ切り出す。
"""

from __future__ import annotations

from bounded_contexts.reward_points.domain.entities.family_membership import FamilyMembership
from bounded_contexts.reward_points.domain.exceptions import (
    AccountAlreadyInFamilyError,
    AlreadyBelongsToFamilyError,
    DisplayNameRequiredError,
    InvitationNotFoundError,
    InvitationTargetUnavailableError,
)
from bounded_contexts.reward_points.domain.repositories.family_invitation_repository import (
    IFamilyInvitationRepository,
)
from bounded_contexts.reward_points.domain.repositories.family_membership_repository import (
    IFamilyMembershipRepository,
)
from bounded_contexts.reward_points.domain.repositories.point_ledger_repository import IPointLedgerRepository
from bounded_contexts.reward_points.domain.value_objects.family_role import FamilyRole
from shared.kernel.timestamps import utcnow


class InvitationBinder:
    def __init__(
        self,
        invitations: IFamilyInvitationRepository,
        memberships: IFamilyMembershipRepository,
        ledgers: IPointLedgerRepository,
    ) -> None:
        self._invitations = invitations
        self._memberships = memberships
        self._ledgers = ledgers

    def bind(self, *, code: str, account_id: int, display_name: str | None) -> FamilyMembership:
        # 参加を作る前に使用済みにする。同じコードで同時に 2 つ届いても、
        # ここを通れるのは 1 つだけ。以降で弾かれた場合はトランザクションごと
        # 巻き戻るので、使えるはずのコードが無駄に消えることもない。
        #
        # 「存在しない」「期限切れ」「使用済み」を区別しない（総当たりの手がかりを残さない）
        invitation = self._invitations.consume(code, now=utcnow())
        if invitation is None:
            raise InvitationNotFoundError
        # 所属できる家族は 1 つまで（ADR-0013）。同じ家族への二重参加と、別の
        # 家族に所属したままの参加を区別して断る（画面の案内が変わるため）。
        existing = self._memberships.list_for_account(account_id)
        if any(membership.family_id == invitation.family_id for membership in existing):
            raise AccountAlreadyInFamilyError
        if existing:
            raise AlreadyBelongsToFamilyError

        return (
            self._link_target(invitation.target_membership_id, family_id=invitation.family_id, account_id=account_id)
            if invitation.target_membership_id is not None
            else self._join_as_new(invitation.family_id, invitation.role, account_id, display_name)
        )

    def _link_target(self, membership_id: int, *, family_id: int, account_id: int) -> FamilyMembership:
        target = self._memberships.find_by_id(membership_id)
        if target is None or target.family_id != family_id:
            raise InvitationNotFoundError
        if target.is_linked:
            raise InvitationTargetUnavailableError
        return self._memberships.link_account(membership_id=target.id, account_id=account_id)

    def _join_as_new(
        self,
        family_id: int,
        role: FamilyRole,
        account_id: int,
        display_name: str | None,
    ) -> FamilyMembership:
        if not display_name:
            raise DisplayNameRequiredError
        membership = self._memberships.add(
            family_id=family_id,
            account_id=account_id,
            role=role,
            display_name=display_name,
        )
        if role.has_own_ledger:
            self._ledgers.add(family_id=family_id, membership_id=membership.id)
        return membership


__all__ = ["InvitationBinder"]
