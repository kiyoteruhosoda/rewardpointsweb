"""未使用かつ期限内の招待の一覧（owner のみ）。

平文のコードは保存していないので、この一覧には載らない。
"""

from __future__ import annotations

from bounded_contexts.reward_points.application.dto.family_dto import InvitationDTO
from bounded_contexts.reward_points.application.family_access_resolver import FamilyAccessResolver
from bounded_contexts.reward_points.domain.repositories.family_invitation_repository import (
    IFamilyInvitationRepository,
)
from bounded_contexts.reward_points.domain.repositories.family_membership_repository import (
    IFamilyMembershipRepository,
)
from shared.kernel.timestamps import utcnow


class ListInvitationsUseCase:
    def __init__(
        self,
        access: FamilyAccessResolver,
        invitations: IFamilyInvitationRepository,
        memberships: IFamilyMembershipRepository,
    ) -> None:
        self._access = access
        self._invitations = invitations
        self._memberships = memberships

    def execute(self, *, family_id: int, account_id: int) -> list[InvitationDTO]:
        self._access.require_owner(family_id=family_id, account_id=account_id)
        pending = self._invitations.list_pending(family_id, now=utcnow())
        names = {
            membership.id: membership.display_name_value
            for membership in self._memberships.list_by_ids(
                [i.target_membership_id for i in pending if i.target_membership_id is not None]
            )
        }
        return [
            InvitationDTO(
                id=invitation.id,
                role=invitation.role,
                target_membership_id=invitation.target_membership_id,
                target_display_name=names.get(invitation.target_membership_id or 0),
                expires_at=invitation.expires_at,
                code=None,
            )
            for invitation in pending
        ]


__all__ = ["ListInvitationsUseCase"]
