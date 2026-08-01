"""家族への参加の永続化インターフェース。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence
from datetime import datetime

from bounded_contexts.reward_points.domain.entities.family_membership import FamilyMembership
from bounded_contexts.reward_points.domain.value_objects.family_role import FamilyRole


class IFamilyMembershipRepository(ABC):
    @abstractmethod
    def add(
        self,
        *,
        family_id: int,
        account_id: int | None,
        role: FamilyRole,
        display_name: str,
    ) -> FamilyMembership: ...

    @abstractmethod
    def find_by_id(self, membership_id: int) -> FamilyMembership | None: ...

    @abstractmethod
    def find_in_family(self, *, family_id: int, account_id: int) -> FamilyMembership | None:
        """呼び出し元がその家族でどの立場かを引く（認可の起点）。"""

    @abstractmethod
    def list_for_family(self, family_id: int) -> list[FamilyMembership]: ...

    @abstractmethod
    def list_for_account(self, account_id: int) -> list[FamilyMembership]:
        """*account_id* の参加。所属は 1 家族までなので通常 0 件か 1 件（ADR-0013）。"""

    @abstractmethod
    def link_account(self, *, membership_id: int, account_id: int) -> FamilyMembership:
        """招待の受諾でアカウントを結び付ける。"""

    @abstractmethod
    def delete(self, membership_id: int) -> None: ...

    @abstractmethod
    def update_display_name(self, *, membership_id: int, display_name: str) -> FamilyMembership: ...

    @abstractmethod
    def update_role(self, *, membership_id: int, role: FamilyRole) -> FamilyMembership:
        """立場を変える（owner 脱退時の引き継ぎ。ADR-0013）。"""

    @abstractmethod
    def propose_independence(self, *, membership_id: int, proposed_at: datetime) -> FamilyMembership:
        """独立の指示を記録する（ADR-0014）。子本人の承認までは所属のまま。"""

    @abstractmethod
    def clear_independence_proposal(self, membership_id: int) -> FamilyMembership:
        """独立の指示を取り下げる（ADR-0014）。"""

    @abstractmethod
    def reorder(self, *, family_id: int, membership_ids: Sequence[int]) -> None:
        """並び順を、渡された順（先頭が 0）に振り直す。

        一覧の並びは実装がまとめて決めるので、呼び出し側は順番の列だけを渡す。
        """

    @abstractmethod
    def list_by_ids(self, membership_ids: Sequence[int]) -> list[FamilyMembership]: ...


__all__ = ["IFamilyMembershipRepository"]
