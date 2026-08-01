"""発行済みの招待を取り消す。

取り消せる立場は発行と同じ（ADR-0020）。子ども宛は親メンバー、親宛は owner。
配れる人が取り消せないと、渡し間違えたコードを止められない。
"""

from __future__ import annotations

from bounded_contexts.reward_points.application.family_access_resolver import FamilyAccessResolver
from bounded_contexts.reward_points.domain.exceptions import (
    FamilyAccessDeniedError,
    InvitationNotFoundError,
)
from bounded_contexts.reward_points.domain.repositories.family_invitation_repository import (
    IFamilyInvitationRepository,
)
from bounded_contexts.reward_points.domain.services import family_access_policy


class RevokeInvitationUseCase:
    def __init__(self, access: FamilyAccessResolver, invitations: IFamilyInvitationRepository) -> None:
        self._access = access
        self._invitations = invitations

    def execute(self, *, family_id: int, invitation_id: int, account_id: int) -> None:
        actor = self._access.membership_in(family_id=family_id, account_id=account_id)
        invitation = self._invitations.find_in_family(family_id=family_id, invitation_id=invitation_id)
        if invitation is None:
            raise InvitationNotFoundError
        if not family_access_policy.can_invite(actor, invitation.role):
            raise FamilyAccessDeniedError
        self._invitations.delete(invitation.id)


__all__ = ["RevokeInvitationUseCase"]
