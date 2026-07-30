"""ログイン中のユーザーが見られるメンバーの一覧。

管理する側には自分のメンバーと共有されたメンバーが並び、メンバー本人には自分
1 人だけが並ぶ。どちらも同じ 1 本の経路で解決する（役割で画面を分けない）。
"""

from __future__ import annotations

from bounded_contexts.reward_points.application.dto.member_dto import MemberSummaryDTO
from bounded_contexts.reward_points.domain.repositories.member_repository import IMemberRepository
from bounded_contexts.reward_points.domain.repositories.member_share_repository import IMemberShareRepository
from bounded_contexts.reward_points.domain.repositories.point_entry_repository import IPointEntryRepository
from bounded_contexts.reward_points.domain.services.member_access_policy import MemberAccessPolicy
from bounded_contexts.reward_points.domain.services.point_ledger import PointLedger


class ListAccessibleMembersUseCase:
    def __init__(
        self,
        members: IMemberRepository,
        shares: IMemberShareRepository,
        entries: IPointEntryRepository,
    ) -> None:
        self._members = members
        self._shares = shares
        self._entries = entries

    def execute(self, user_id: int) -> list[MemberSummaryDTO]:
        members = self._members.find_reachable_by(user_id)
        member_ids = [member.id for member in members]
        shares = self._shares.list_for_members(member_ids)
        entries_by_member = self._entries.list_by_members(member_ids)

        summaries: list[MemberSummaryDTO] = []
        for member in members:
            level = MemberAccessPolicy.resolve(member, user_id=user_id, shares=shares)
            if level is None:  # リポジトリの絞り込みとポリシーの判断が食い違った場合の保険
                continue
            balance = PointLedger(entries_by_member.get(member.id, [])).balance
            summaries.append(MemberSummaryDTO.of(member, level=level, balance=balance.value, viewer_user_id=user_id))
        return summaries


__all__ = ["ListAccessibleMembersUseCase"]
