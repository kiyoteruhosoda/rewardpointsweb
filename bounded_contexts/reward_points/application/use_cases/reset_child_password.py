"""A parent issues a temporary password for a child (ADR-0011).

Accounts without an email address cannot use SMTP-based reset, so recovery is kept
within the household. Only ``role = child`` members of the same family can receive one;
parent-to-parent resets are not allowed.

After signing in with a temporary password, no other operation is allowed until the
password change is completed (``users.must_change_password``).
"""

from __future__ import annotations

from bounded_contexts.reward_points.application.dto.family_dto import TemporaryPasswordDTO
from bounded_contexts.reward_points.application.family_access_resolver import FamilyAccessResolver
from bounded_contexts.reward_points.domain.exceptions import (
    ChildAccountRequiredError,
    MembershipNotFoundError,
    MembershipNotLinkedError,
)
from bounded_contexts.reward_points.domain.repositories.account_directory import (
    IAccountDirectory,
    IAccountProvisioning,
)
from bounded_contexts.reward_points.domain.repositories.family_membership_repository import (
    IFamilyMembershipRepository,
)
from bounded_contexts.reward_points.domain.services import family_access_policy


class ResetChildPasswordUseCase:
    def __init__(
        self,
        *,
        access: FamilyAccessResolver,
        memberships: IFamilyMembershipRepository,
        provisioning: IAccountProvisioning,
        accounts: IAccountDirectory,
    ) -> None:
        self._access = access
        self._memberships = memberships
        self._provisioning = provisioning
        self._accounts = accounts

    def execute(self, *, family_id: int, membership_id: int, account_id: int) -> TemporaryPasswordDTO:
        actor = self._access.membership_in(family_id=family_id, account_id=account_id)
        target = self._memberships.find_by_id(membership_id)
        if target is None or target.family_id != family_id:
            raise MembershipNotFoundError
        if not family_access_policy.can_reset_password_of(actor, target):
            raise ChildAccountRequiredError
        if target.account_id is None:
            raise MembershipNotLinkedError

        issued = self._provisioning.issue_temporary_password(target.account_id)
        described = self._accounts.describe([target.account_id])
        username = described[target.account_id].username if target.account_id in described else ""
        return TemporaryPasswordDTO(
            membership_id=target.id,
            username=username,
            password=issued.password,
            expires_at=issued.expires_at,
            issued_by_membership_id=actor.id,
        )


__all__ = ["ResetChildPasswordUseCase"]
