"""メンバーへのアクセス範囲の判定（所有 / 共有 / 本人）。"""

from __future__ import annotations

from datetime import datetime

import pytest

from bounded_contexts.reward_points.domain.entities.member import Member
from bounded_contexts.reward_points.domain.entities.member_share import MemberShare
from bounded_contexts.reward_points.domain.services.member_access_policy import MemberAccessPolicy
from bounded_contexts.reward_points.domain.value_objects.member_access_level import MemberAccessLevel
from bounded_contexts.reward_points.domain.value_objects.member_name import MemberName

OWNER_ID = 10
MEMBER_USER_ID = 20
OTHER_ID = 30


def _member(*, linked_user_id: int | None = None) -> Member:
    return Member(
        id=1,
        name=MemberName("ハナ"),
        owner_user_id=OWNER_ID,
        linked_user_id=linked_user_id,
        created_at=datetime(2026, 7, 30, 12, 0, 0),
    )


def test_owner_can_manage() -> None:
    assert MemberAccessPolicy.resolve(_member(), user_id=OWNER_ID, shares=[]) is MemberAccessLevel.MANAGE


def test_unrelated_user_has_no_access() -> None:
    assert MemberAccessPolicy.resolve(_member(), user_id=OTHER_ID, shares=[]) is None


def test_linked_member_can_only_view() -> None:
    """メンバー本人は自分のポイントを見られるが変更はできない。"""
    member = _member(linked_user_id=MEMBER_USER_ID)

    assert MemberAccessPolicy.resolve(member, user_id=MEMBER_USER_ID, shares=[]) is MemberAccessLevel.VIEW


@pytest.mark.parametrize("level", list(MemberAccessLevel))
def test_share_grants_exactly_what_was_given(level: MemberAccessLevel) -> None:
    share = MemberShare(member_id=1, user_id=OTHER_ID, level=level)

    assert MemberAccessPolicy.resolve(_member(), user_id=OTHER_ID, shares=[share]) is level


def test_share_for_another_member_is_ignored() -> None:
    """他のメンバーの共有が、このメンバーへのアクセスを生んではいけない。"""
    share = MemberShare(member_id=999, user_id=OTHER_ID, level=MemberAccessLevel.MANAGE)

    assert MemberAccessPolicy.resolve(_member(), user_id=OTHER_ID, shares=[share]) is None


def test_share_for_another_user_is_ignored() -> None:
    share = MemberShare(member_id=1, user_id=OTHER_ID, level=MemberAccessLevel.MANAGE)

    assert MemberAccessPolicy.resolve(_member(), user_id=999, shares=[share]) is None


def test_strongest_route_wins_for_a_self_registered_owner() -> None:
    """自分自身をメンバーとして登録した管理者は、本人でもあるが変更できる。"""
    member = _member(linked_user_id=OWNER_ID)

    assert MemberAccessPolicy.resolve(member, user_id=OWNER_ID, shares=[]) is MemberAccessLevel.MANAGE


def test_view_share_does_not_weaken_ownership() -> None:
    member = _member()
    share = MemberShare(member_id=1, user_id=OWNER_ID, level=MemberAccessLevel.VIEW)

    assert MemberAccessPolicy.resolve(member, user_id=OWNER_ID, shares=[share]) is MemberAccessLevel.MANAGE
