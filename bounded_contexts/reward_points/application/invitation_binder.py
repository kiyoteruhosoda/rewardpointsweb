"""Shared logic that turns an invitation code into one membership.

There are two entry points for accepting an invitation:

- Someone who already has an account joins the family (``accept``)
- A child creates an account on their own device and joins (``redeem``, ADR-0011)

The only difference is how the account is prepared; code verification, membership
creation and marking the code as used are the same. Extracted here so both can call it.
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
        # Mark the code as used before creating the membership. Even if two requests with
        # the same code arrive at once, only one gets past here. If a later check rejects
        # it, the whole transaction rolls back, so a still-valid code is not wasted.
        #
        # "Not found", "expired" and "already used" are not distinguished (no hints for brute force)
        invitation = self._invitations.consume(code, now=utcnow())
        if invitation is None:
            raise InvitationNotFoundError
        # An account can belong to at most one family (ADR-0013). Joining the same family
        # twice and joining while still in another family are rejected separately (the
        # on-screen guidance differs).
        existing = self._memberships.list_for_account(account_id)
        if any(membership.family_id == invitation.family_id for membership in existing):
            raise AccountAlreadyInFamilyError
        if existing:
            raise AlreadyBelongsToFamilyError

        return (
            self._link_target(invitation.target_membership_id, family_id=invitation.family_id, account_id=account_id)
            if invitation.target_membership_id is not None
            else self._join_as_new(
                family_id=invitation.family_id,
                role=invitation.role,
                account_id=account_id,
                display_name=display_name,
            )
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
        *,
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
