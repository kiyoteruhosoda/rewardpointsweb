"""誰がどのメンバーへどこまで触れるかを決める、唯一の場所。

到達経路は 3 つある。

============ =========================================================
所有者       登録した人。変更できる（``MANAGE``）
共有された人 共有時に決めた範囲（``VIEW`` / ``MANAGE``）
本人         メンバーに紐付いたログインアカウント。**閲覧だけ**（``VIEW``）
============ =========================================================

「メンバーは自分のポイントを見られるが変更はできない」ため、本人であることは
``VIEW`` しか生まない。ただし複数の経路で到達できるときは強い方を採るので、
自分自身をメンバーとして登録した管理者（所有者かつ本人）は変更できる。所有者
としての権限を、本人でもあるという理由で弱めるのは筋が通らない。
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence

from bounded_contexts.reward_points.domain.entities.member import Member
from bounded_contexts.reward_points.domain.entities.member_share import MemberShare
from bounded_contexts.reward_points.domain.value_objects.member_access_level import MemberAccessLevel


class MemberAccessPolicy:
    @staticmethod
    def resolve(member: Member, *, user_id: int, shares: Sequence[MemberShare]) -> MemberAccessLevel | None:
        """*user_id* が *member* へ触れられる範囲。どの経路も無ければ ``None``。

        *shares* は「そのメンバーの共有」でも「そのユーザーの共有」でも良い。
        どちらで渡しても同じ結果になるよう、両方の一致を確かめる。
        """
        return MemberAccessLevel.strongest(_granted_levels(member, user_id=user_id, shares=shares))


def _granted_levels(member: Member, *, user_id: int, shares: Sequence[MemberShare]) -> Iterable[MemberAccessLevel]:
    if member.owner_user_id == user_id:
        yield MemberAccessLevel.MANAGE
    for share in shares:
        if share.grants_to(user_id, member.id):
            yield share.level
    if member.is_linked_to(user_id):
        yield MemberAccessLevel.VIEW


__all__ = ["MemberAccessPolicy"]
