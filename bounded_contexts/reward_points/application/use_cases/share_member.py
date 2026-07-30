"""メンバーを他のログインアカウントへ共有する（要 ``MANAGE``）。

共有相手は **メールアドレス** で指定する。ユーザー一覧を返す API を用意すると、
``user:manage`` を持たない管理者にも全アカウントが見えてしまうため。

渡す範囲は ``view``（見るだけ）と ``manage``（加算・消費もできる）から選ぶ。
"""

from __future__ import annotations

from dataclasses import dataclass

from bounded_contexts.reward_points.application.dto.member_dto import MemberShareDTO
from bounded_contexts.reward_points.application.member_access_resolver import MemberAccessResolver
from bounded_contexts.reward_points.domain.exceptions import (
    MemberAlreadySharedError,
    ShareTargetNotFoundError,
    ShareWithOwnerNotAllowedError,
)
from bounded_contexts.reward_points.domain.repositories.member_share_repository import IMemberShareRepository
from bounded_contexts.reward_points.domain.repositories.share_target_directory import (
    IShareTargetDirectory,
    ShareTarget,
)
from bounded_contexts.reward_points.domain.value_objects.member_access_level import MemberAccessLevel


@dataclass(frozen=True, kw_only=True)
class ShareMemberCommand:
    member_id: int
    user_id: int
    target_email: str
    access_level: MemberAccessLevel


class ShareMemberUseCase:
    def __init__(
        self,
        access: MemberAccessResolver,
        shares: IMemberShareRepository,
        directory: IShareTargetDirectory,
    ) -> None:
        self._access = access
        self._shares = shares
        self._directory = directory

    def execute(self, command: ShareMemberCommand) -> MemberShareDTO:
        member = self._access.require_manage(member_id=command.member_id, user_id=command.user_id).member
        target = self._require_target(command.target_email)
        if target.user_id == member.owner_user_id:
            raise ShareWithOwnerNotAllowedError
        if any(share.user_id == target.user_id for share in self._shares.list_for_member(member.id)):
            raise MemberAlreadySharedError
        share = self._shares.grant(
            member_id=member.id,
            user_id=target.user_id,
            level=command.access_level,
        )
        return MemberShareDTO.of(share, target)

    def _require_target(self, email: str) -> ShareTarget:
        target = self._directory.find_by_email(email)
        if target is None:
            raise ShareTargetNotFoundError
        return target


__all__ = ["ShareMemberCommand", "ShareMemberUseCase"]
