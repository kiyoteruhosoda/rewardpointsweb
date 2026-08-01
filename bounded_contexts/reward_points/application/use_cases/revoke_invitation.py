"""発行済みの招待を取り消す（owner のみ）。"""

from __future__ import annotations

from bounded_contexts.reward_points.application.family_access_resolver import FamilyAccessResolver
from bounded_contexts.reward_points.domain.exceptions import InvitationNotFoundError
from bounded_contexts.reward_points.domain.repositories.family_invitation_repository import (
    IFamilyInvitationRepository,
)


class RevokeInvitationUseCase:
    def __init__(self, access: FamilyAccessResolver, invitations: IFamilyInvitationRepository) -> None:
        self._access = access
        self._invitations = invitations

    def execute(self, *, family_id: int, invitation_id: int, account_id: int) -> None:
        self._access.require_owner(family_id=family_id, account_id=account_id)
        invitation = self._invitations.find_in_family(family_id=family_id, invitation_id=invitation_id)
        if invitation is None:
            raise InvitationNotFoundError
        self._invitations.delete(invitation.id)


__all__ = ["RevokeInvitationUseCase"]
