"""メンバーの共有先一覧（所有者のみ）。"""

from __future__ import annotations

from bounded_contexts.reward_points.application.dto.member_dto import MemberShareDTO
from bounded_contexts.reward_points.application.member_access_resolver import MemberAccessResolver
from bounded_contexts.reward_points.domain.repositories.member_share_repository import IMemberShareRepository
from bounded_contexts.reward_points.domain.repositories.share_target_directory import IShareTargetDirectory


class ListMemberSharesUseCase:
    def __init__(
        self,
        access: MemberAccessResolver,
        shares: IMemberShareRepository,
        directory: IShareTargetDirectory,
    ) -> None:
        self._access = access
        self._shares = shares
        self._directory = directory

    def execute(self, *, member_id: int, user_id: int) -> list[MemberShareDTO]:
        self._access.require_ownership(member_id=member_id, user_id=user_id)
        shares = self._shares.list_for_member(member_id)
        targets = self._directory.describe([share.user_id for share in shares])
        return [
            MemberShareDTO.of(share, target)
            for share in shares
            # 共有先のアカウントが消えていれば、その共有はもう意味を持たない
            if (target := targets.get(share.user_id)) is not None
        ]


__all__ = ["ListMemberSharesUseCase"]
