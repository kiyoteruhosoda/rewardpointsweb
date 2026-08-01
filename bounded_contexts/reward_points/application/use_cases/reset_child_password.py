"""親が子の一時パスワードを発行する（ADR-0011）。

メールアドレスを持たないアカウントでは SMTP 経由のリセットが成立しないため、
回復経路を家庭内で完結させる。発行できるのは同一家族の ``role = child`` に
対してだけで、親から親へのリセットは許可しない。

一時パスワードでログインした後は、パスワードの変更を完了するまで他の操作を
許可しない（``users.must_change_password``）。
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
