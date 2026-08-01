"""招待の永続化インターフェース。

コードのハッシュ化はこのポートの実装（Infrastructure）に閉じる。ドメイン側は
平文のコードだけを扱い、保存形式を知らない。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime

from bounded_contexts.reward_points.domain.entities.family_invitation import FamilyInvitation
from bounded_contexts.reward_points.domain.value_objects.family_role import FamilyRole


@dataclass(frozen=True, kw_only=True)
class IssuedInvitation:
    """発行結果。平文のコードはこの 1 回しか取り出せない。"""

    invitation: FamilyInvitation
    code: str


class IFamilyInvitationRepository(ABC):
    @abstractmethod
    def issue(
        self,
        *,
        family_id: int,
        role: FamilyRole,
        target_membership_id: int | None,
        expires_at: datetime,
    ) -> IssuedInvitation: ...

    @abstractmethod
    def find_by_code(self, code: str) -> FamilyInvitation | None: ...

    @abstractmethod
    def list_pending(self, family_id: int, *, now: datetime) -> list[FamilyInvitation]:
        """未使用かつ期限内のものだけ。"""

    @abstractmethod
    def find_in_family(self, *, family_id: int, invitation_id: int) -> FamilyInvitation | None: ...

    @abstractmethod
    def mark_used(self, *, invitation_id: int, used_at: datetime) -> None: ...

    @abstractmethod
    def delete(self, invitation_id: int) -> None: ...


__all__ = ["IFamilyInvitationRepository", "IssuedInvitation"]
