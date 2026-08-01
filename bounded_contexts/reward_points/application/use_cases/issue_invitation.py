"""招待コードを発行する（owner のみ）。

平文のコードはこの応答でだけ返す。保存されるのはハッシュだけなので、失くしたら
発行し直す。``role = child`` の招待では、親が先に作った参加者を必ず指す
（ADR-0009 / ADR-0011）。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from bounded_contexts.reward_points.application.dto.family_dto import InvitationDTO
from bounded_contexts.reward_points.application.family_access_resolver import FamilyAccessResolver
from bounded_contexts.reward_points.domain.entities.family_membership import FamilyMembership
from bounded_contexts.reward_points.domain.exceptions import (
    InvitationTargetUnavailableError,
    MembershipNotFoundError,
)
from bounded_contexts.reward_points.domain.repositories.family_invitation_repository import (
    IFamilyInvitationRepository,
)
from bounded_contexts.reward_points.domain.repositories.family_membership_repository import (
    IFamilyMembershipRepository,
)
from bounded_contexts.reward_points.domain.value_objects.family_role import FamilyRole
from shared.kernel.timestamps import utcnow


@dataclass(frozen=True, kw_only=True)
class IssueInvitationCommand:
    family_id: int
    account_id: int
    role: FamilyRole
    target_membership_id: int | None


class IssueInvitationUseCase:
    def __init__(
        self,
        access: FamilyAccessResolver,
        invitations: IFamilyInvitationRepository,
        memberships: IFamilyMembershipRepository,
        ttl: timedelta,
    ) -> None:
        self._access = access
        self._invitations = invitations
        self._memberships = memberships
        self._ttl = ttl

    def execute(self, command: IssueInvitationCommand) -> InvitationDTO:
        self._access.require_owner(family_id=command.family_id, account_id=command.account_id)
        target = self._require_target(command)
        issued = self._invitations.issue(
            family_id=command.family_id,
            role=command.role,
            target_membership_id=target.id if target else None,
            expires_at=utcnow() + self._ttl,
        )
        return InvitationDTO(
            id=issued.invitation.id,
            role=issued.invitation.role,
            target_membership_id=issued.invitation.target_membership_id,
            target_display_name=target.display_name_value if target else None,
            expires_at=issued.invitation.expires_at,
            code=issued.code,
        )

    def _require_target(self, command: IssueInvitationCommand) -> FamilyMembership | None:
        if command.target_membership_id is None:
            return None
        target = self._memberships.find_by_id(command.target_membership_id)
        if target is None or target.family_id != command.family_id:
            raise MembershipNotFoundError
        if target.is_linked:
            raise InvitationTargetUnavailableError
        return target


__all__ = ["IssueInvitationCommand", "IssueInvitationUseCase"]
