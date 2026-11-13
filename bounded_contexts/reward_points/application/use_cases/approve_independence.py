"""A child (guest) approves independence, and independence takes effect (ADR-0014).

Only the child themself, once a parent member has directed independence, can approve. On completion:

- The membership, ledger and all records are deleted from the family (an explicit exception
  to append-only — ADR-0010. Independence is a ceremony, not a path for silently disappearing)
- The account remains, in the initial state of belonging to no family
- It is promoted to the same application role as parents (members), so it can create its own
  family and accept invitations as a member
"""

from __future__ import annotations

from bounded_contexts.reward_points.application.family_access_resolver import FamilyAccessResolver
from bounded_contexts.reward_points.domain.exceptions import (
    FamilyAccessDeniedError,
    IndependenceNotProposedError,
)
from bounded_contexts.reward_points.domain.repositories.account_directory import IAccountProvisioning
from bounded_contexts.reward_points.domain.repositories.family_membership_repository import (
    IFamilyMembershipRepository,
)
from bounded_contexts.reward_points.domain.repositories.point_ledger_repository import IPointLedgerRepository
from bounded_contexts.reward_points.domain.repositories.point_transaction_repository import (
    IPointTransactionRepository,
)


class ApproveIndependenceUseCase:
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

    def execute(self, *, family_id: int, account_id: int) -> None:
        me = self._access.membership_in(family_id=family_id, account_id=account_id)
        if not me.role.has_own_ledger:
            # Parents have no independence. A parent who wants to leave the family uses leave
            raise FamilyAccessDeniedError
        if not me.independence_proposed:
            raise IndependenceNotProposedError
        self._remove_ledger_with_records(me.id)
        self._memberships.delete(me.id)
        self._provisioning.grant_guardian_permissions(account_id)

    def _remove_ledger_with_records(self, membership_id: int) -> None:
        ledger = self._ledgers.find_by_membership(membership_id)
        if ledger is None:
            return
        self._transactions.delete_by_ledger(ledger.id)
        self._ledgers.delete(ledger.id)


__all__ = ["ApproveIndependenceUseCase"]
