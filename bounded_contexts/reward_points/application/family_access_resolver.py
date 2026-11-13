"""Entry point that resolves access to families and ledgers.

Every use case goes through here before touching its target. The decision itself
belongs to the domain's
:mod:`~bounded_contexts.reward_points.domain.services.family_access_policy`;
this handles "load, have it decide, and raise if not allowed".

Denials are uniformly **403** (``family_access_denied``). The caller cannot tell
"not a member", "insufficient role" and "belongs to another family" apart.

A nonexistent family ID also yields the same 403 (it ends the same way: no
membership found), so this response does not reveal whether a family exists.
Only for ledgers, when the row does not exist at all, it returns 404
(``ledger_not_found``), because calling something nonexistent "no permission"
would be more misleading.
"""

from __future__ import annotations

from dataclasses import dataclass

from bounded_contexts.reward_points.domain.entities.family_membership import FamilyMembership
from bounded_contexts.reward_points.domain.entities.point_ledger import PointLedger
from bounded_contexts.reward_points.domain.exceptions import (
    FamilyAccessDeniedError,
    LedgerNotFoundError,
)
from bounded_contexts.reward_points.domain.repositories.family_membership_repository import (
    IFamilyMembershipRepository,
)
from bounded_contexts.reward_points.domain.repositories.point_ledger_repository import IPointLedgerRepository
from bounded_contexts.reward_points.domain.services import family_access_policy


@dataclass(frozen=True, kw_only=True)
class LedgerAccess:
    """A ledger and the member who reached it."""

    membership: FamilyMembership
    ledger: PointLedger


class FamilyAccessResolver:
    def __init__(self, memberships: IFamilyMembershipRepository, ledgers: IPointLedgerRepository) -> None:
        self._memberships = memberships
        self._ledgers = ledgers

    def membership_in(self, *, family_id: int, account_id: int) -> FamilyMembership:
        membership = self._memberships.find_in_family(family_id=family_id, account_id=account_id)
        if membership is None:
            raise FamilyAccessDeniedError
        return membership

    def require_guardian(self, *, family_id: int, account_id: int) -> FamilyMembership:
        membership = self.membership_in(family_id=family_id, account_id=account_id)
        if not family_access_policy.can_create_child(membership):
            raise FamilyAccessDeniedError
        return membership

    def require_owner(self, *, family_id: int, account_id: int) -> FamilyMembership:
        membership = self.membership_in(family_id=family_id, account_id=account_id)
        if not family_access_policy.can_administer_family(membership):
            raise FamilyAccessDeniedError
        return membership

    def viewable_ledger(self, *, ledger_id: int, account_id: int) -> LedgerAccess:
        ledger = self._ledgers.find_by_id(ledger_id)
        if ledger is None:
            raise LedgerNotFoundError
        membership = self._memberships.find_in_family(family_id=ledger.family_id, account_id=account_id)
        # Siblings' ledgers and other families' ledgers both stop here (ADR-0009)
        if membership is None or not family_access_policy.can_view_ledger(membership, ledger):
            raise FamilyAccessDeniedError
        return LedgerAccess(membership=membership, ledger=ledger)

    def modifiable_ledger(self, *, ledger_id: int, account_id: int) -> LedgerAccess:
        access = self.viewable_ledger(ledger_id=ledger_id, account_id=account_id)
        if not family_access_policy.can_modify_ledger(access.membership, access.ledger):
            raise FamilyAccessDeniedError
        return access


__all__ = ["FamilyAccessResolver", "LedgerAccess"]
