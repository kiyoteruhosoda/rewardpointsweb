"""家族への参加の永続化インターフェース。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence

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
        """*account_id* が所属する全ての家族での参加（複数家族を許す）。"""

    @abstractmethod
    def link_account(self, *, membership_id: int, account_id: int) -> FamilyMembership:
        """招待の受諾でアカウントを結び付ける。"""

    @abstractmethod
    def delete(self, membership_id: int) -> None: ...

    @abstractmethod
    def update_display_name(self, *, membership_id: int, display_name: str) -> FamilyMembership: ...

    @abstractmethod
    def list_by_ids(self, membership_ids: Sequence[int]) -> list[FamilyMembership]: ...


__all__ = ["IFamilyMembershipRepository"]
