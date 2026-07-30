"""メンバーを登録する。

``linked_user_email`` を指定すると、そのログインアカウントの本人として紐付ける。
紐付いた本人は自分のポイントを閲覧できるが変更はできない。1 つのアカウントを
複数のメンバーへ紐付けることは許さない（「自分のポイント」が一意に決まらなくなる）。
"""

from __future__ import annotations

from dataclasses import dataclass

from bounded_contexts.reward_points.application.dto.member_dto import MemberDetailDTO
from bounded_contexts.reward_points.domain.exceptions import (
    LinkedUserAlreadyTakenError,
    ShareTargetNotFoundError,
)
from bounded_contexts.reward_points.domain.repositories.member_repository import IMemberRepository
from bounded_contexts.reward_points.domain.repositories.share_target_directory import (
    IShareTargetDirectory,
    ShareTarget,
)
from bounded_contexts.reward_points.domain.value_objects.member_access_level import MemberAccessLevel


@dataclass(frozen=True, kw_only=True)
class RegisterMemberCommand:
    name: str
    owner_user_id: int
    linked_user_email: str | None


class RegisterMemberUseCase:
    def __init__(self, members: IMemberRepository, directory: IShareTargetDirectory) -> None:
        self._members = members
        self._directory = directory

    def execute(self, command: RegisterMemberCommand) -> MemberDetailDTO:
        linked = self._resolve_linked_user(command.linked_user_email)
        member = self._members.add(
            name=command.name,
            owner_user_id=command.owner_user_id,
            linked_user_id=linked.user_id if linked else None,
        )
        return MemberDetailDTO(
            id=member.id,
            name=member.name_value,
            balance=0,
            access_level=MemberAccessLevel.MANAGE,
            is_self=member.is_linked_to(command.owner_user_id),
            linked_user_email=linked.email if linked else None,
        )

    def _resolve_linked_user(self, email: str | None) -> ShareTarget | None:
        if not email:
            return None
        target = self._directory.find_by_email(email)
        if target is None:
            raise ShareTargetNotFoundError
        if self._members.find_by_linked_user(target.user_id) is not None:
            raise LinkedUserAlreadyTakenError
        return target


__all__ = ["RegisterMemberCommand", "RegisterMemberUseCase"]
