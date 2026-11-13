"""Remove a member from a family (owner only; display devices can be removed by any parent).

Ledgers are append-only and there is no way to delete them (ADR-0010). A member with even
one remaining record cannot be removed — otherwise it would become a path for history to silently vanish.

Child accounts are created by redeeming an invitation and exist only as a family membership,
so removal deletes the account as well (ADR-0018). That a linked child account came from
redeem is guaranteed by accept rejecting child invitations
(``child_invitation_requires_signup``). Parent accounts exist independently of the family
(created by an administrator), so they are not deleted.

Display devices (ADR-0047) can be removed by parents (owner / parent). The device account
is also created on approval and exists only to show that family, so it is deleted with the membership.
"""

from __future__ import annotations

from bounded_contexts.reward_points.application.family_access_resolver import FamilyAccessResolver
from bounded_contexts.reward_points.domain.entities.family_membership import FamilyMembership
from bounded_contexts.reward_points.domain.exceptions import (
    FamilyAccessDeniedError,
    LedgerNotEmptyError,
    MembershipNotFoundError,
)
from bounded_contexts.reward_points.domain.repositories.account_directory import IAccountProvisioning
from bounded_contexts.reward_points.domain.repositories.family_membership_repository import (
    IFamilyMembershipRepository,
)
from bounded_contexts.reward_points.domain.repositories.point_ledger_repository import IPointLedgerRepository
from bounded_contexts.reward_points.domain.repositories.point_transaction_repository import (
    IPointTransactionRepository,
)
from bounded_contexts.reward_points.domain.services import family_access_policy


class RemoveMembershipUseCase:
    def __init__(
        self,
        *,
        access: FamilyAccessResolver,
        memberships: IFamilyMembershipRepository,
        ledgers: IPointLedgerRepository,
        transactions: IPointTransactionRepository,
        provisioning: IAccountProvisioning,
    ) -> None:
        self._access = access
        self._memberships = memberships
        self._ledgers = ledgers
        self._transactions = transactions
        self._provisioning = provisioning

    def execute(self, *, family_id: int, membership_id: int, account_id: int) -> int | None:
        """Remove. When a display device is removed, return that device's account ID (for the audit log)."""
        actor = self._access.membership_in(family_id=family_id, account_id=account_id)
        target = self._memberships.find_by_id(membership_id)
        if target is None or target.family_id != family_id:
            # Return 403 to those not allowed to remove before revealing whether the target exists
            # (same order as require_owner)
            if not family_access_policy.can_administer_family(actor):
                raise FamilyAccessDeniedError
            raise MembershipNotFoundError
        if target.role.is_display:
            self._detach_display(actor, target)
            return target.account_id
        if not family_access_policy.can_administer_family(actor) or target.id == actor.id:
            # If the owner removed themself, nobody would be left to manage the family
            raise FamilyAccessDeniedError
        self._remove_ledger_of(target.id)
        self._memberships.delete(target.id)
        self._delete_owned_account_of(target)
        return None

    def _detach_display(self, actor: FamilyMembership, target: FamilyMembership) -> None:
        if not family_access_policy.can_detach_display(actor, target):
            raise FamilyAccessDeniedError
        self._memberships.delete(target.id)
        self._delete_owned_account_of(target)

    def _delete_owned_account_of(self, target: FamilyMembership) -> None:
        """Delete accounts that exist only as a family membership (children, display devices)."""
        owned = target.role.has_own_ledger or target.role.is_display
        if owned and target.account_id is not None:
            self._provisioning.delete_account(target.account_id)

    def _remove_ledger_of(self, membership_id: int) -> None:
        ledger = self._ledgers.find_by_membership(membership_id)
        if ledger is None:
            return
        if self._transactions.count_by_ledger(ledger.id) > 0:
            raise LedgerNotEmptyError
        self._ledgers.delete(ledger.id)


__all__ = ["RemoveMembershipUseCase"]
