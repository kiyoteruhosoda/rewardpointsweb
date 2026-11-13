"""Revoke an issued invitation.

Who may revoke is the same as who may issue (ADR-0020): a parent member for a child
invitation, the owner for a parent invitation. If the people who hand out codes could
not revoke them, a code given to the wrong person could not be stopped.
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
