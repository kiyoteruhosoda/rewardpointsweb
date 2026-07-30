"""メンバー関連の出力 DTO。

``access_level`` はドメインの列挙をそのまま載せる。文字列へ落とすと Presentation
層で ``Literal["view", "manage"]`` へ戻す変換が必要になり、型検査が効かなくなる。
JSON へは列挙の値（``"view"`` / ``"manage"``）が出る。
"""

from __future__ import annotations

from dataclasses import dataclass

from bounded_contexts.reward_points.domain.entities.member import Member
from bounded_contexts.reward_points.domain.entities.member_share import MemberShare
from bounded_contexts.reward_points.domain.repositories.share_target_directory import ShareTarget
from bounded_contexts.reward_points.domain.value_objects.member_access_level import MemberAccessLevel


@dataclass(frozen=True, kw_only=True)
class MemberSummaryDTO:
    id: int
    name: str
    balance: int
    access_level: MemberAccessLevel
    is_self: bool
    is_owner: bool
    has_linked_user: bool

    @classmethod
    def of(cls, member: Member, *, level: MemberAccessLevel, balance: int, viewer_user_id: int) -> MemberSummaryDTO:
        return cls(
            id=member.id,
            name=member.name_value,
            balance=balance,
            access_level=level,
            is_self=member.is_linked_to(viewer_user_id),
            # メンバーの削除と共有の管理は所有者だけができる（ADR-0007）
            is_owner=member.is_owned_by(viewer_user_id),
            # 紐付いたアカウントのメールアドレスは返さない。共有先にまでメンバー
            # 本人のアドレスを見せる理由が無いため、有無だけを伝える。
            has_linked_user=member.linked_user_id is not None,
        )


@dataclass(frozen=True, kw_only=True)
class MemberDetailDTO:
    id: int
    name: str
    balance: int
    access_level: MemberAccessLevel
    is_self: bool
    is_owner: bool
    linked_user_email: str | None


@dataclass(frozen=True, kw_only=True)
class MemberShareDTO:
    user_id: int
    email: str
    username: str
    access_level: MemberAccessLevel

    @classmethod
    def of(cls, share: MemberShare, target: ShareTarget) -> MemberShareDTO:
        return cls(
            user_id=share.user_id,
            email=target.email,
            username=target.username,
            access_level=share.level,
        )


__all__ = ["MemberDetailDTO", "MemberShareDTO", "MemberSummaryDTO"]
