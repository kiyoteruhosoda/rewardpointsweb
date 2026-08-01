"""子（ゲスト）の独立を指示する（親メンバー。ADR-0014）。

独立は「親メンバーが指示し、子本人が承認する」の 2 段階で成立する。この
ユースケースは前半。指示しただけでは何も消えず、承認までは取り下げられる。

対象はアカウントの結び付いた子だけ。未紐付けの子は承認のしようがない
（そもそも本人がログインできない）ので、除名（``RemoveMembershipUseCase``）を使う。
"""

from __future__ import annotations

from bounded_contexts.reward_points.application.family_access_resolver import FamilyAccessResolver
from bounded_contexts.reward_points.domain.entities.family_membership import FamilyMembership
from bounded_contexts.reward_points.domain.exceptions import (
    ChildAccountRequiredError,
    MembershipNotFoundError,
    MembershipNotLinkedError,
)
from bounded_contexts.reward_points.domain.repositories.family_membership_repository import (
    IFamilyMembershipRepository,
)
from shared.kernel.timestamps import utcnow


class ProposeIndependenceUseCase:
    def __init__(self, access: FamilyAccessResolver, memberships: IFamilyMembershipRepository) -> None:
        self._access = access
        self._memberships = memberships

    def execute(self, *, family_id: int, membership_id: int, account_id: int) -> FamilyMembership:
        self._access.require_guardian(family_id=family_id, account_id=account_id)
        target = self._memberships.find_by_id(membership_id)
        if target is None or target.family_id != family_id:
            raise MembershipNotFoundError
        if not target.role.has_own_ledger:
            raise ChildAccountRequiredError
        if not target.is_linked:
            raise MembershipNotLinkedError
        return self._memberships.propose_independence(membership_id=target.id, proposed_at=utcnow())


class RevokeIndependenceProposalUseCase:
    """独立の指示を取り下げる（親メンバー。承認前ならいつでも）。"""

    def __init__(self, access: FamilyAccessResolver, memberships: IFamilyMembershipRepository) -> None:
        self._access = access
        self._memberships = memberships

    def execute(self, *, family_id: int, membership_id: int, account_id: int) -> None:
        self._access.require_guardian(family_id=family_id, account_id=account_id)
        target = self._memberships.find_by_id(membership_id)
        if target is None or target.family_id != family_id:
            raise MembershipNotFoundError
        self._memberships.clear_independence_proposal(target.id)


__all__ = ["ProposeIndependenceUseCase", "RevokeIndependenceProposalUseCase"]
