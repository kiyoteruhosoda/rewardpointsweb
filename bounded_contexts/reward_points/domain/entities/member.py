"""メンバー（ポイントを貯める人）。

``owner_user_id`` は登録した人（管理する側のログインアカウント）。
``linked_user_id`` はメンバー本人のログインアカウントで、紐付けると本人が自分の
ポイントを閲覧できるようになる（変更はできない。
:class:`~bounded_contexts.reward_points.domain.services.member_access_policy.MemberAccessPolicy`
参照）。紐付けは任意で、ログインしない子どものようなメンバーは ``None`` のまま扱う。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from bounded_contexts.reward_points.domain.value_objects.member_name import MemberName


@dataclass(frozen=True, kw_only=True)
class Member:
    id: int
    name: MemberName
    owner_user_id: int
    linked_user_id: int | None
    created_at: datetime

    @property
    def name_value(self) -> str:
        return self.name.value

    def is_linked_to(self, user_id: int) -> bool:
        return self.linked_user_id is not None and self.linked_user_id == user_id

    def is_owned_by(self, user_id: int) -> bool:
        """*user_id* が登録した本人か。

        共有を配る・取り消す権限は所有者だけが持つ。``MANAGE`` で共有された相手は
        ポイントを記録できるが、共有の配り直しはできない（ADR-0007）。
        """
        return self.owner_user_id == user_id


__all__ = ["Member"]
