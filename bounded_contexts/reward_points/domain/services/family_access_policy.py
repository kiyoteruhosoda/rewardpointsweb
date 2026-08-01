"""誰がどの台帳・どの操作へ届くかを決める、唯一の場所（ADR-0009）。

呼び出し側に条件を散在させないため、判定はすべてこのモジュールの関数を経由する。
「特定の子だけを特定の参加者に見せる」要求が出た場合も、可視範囲テーブルを足して
ここの内部だけを変える。

台帳は必ず ``role = child`` の参加者に 1 対 1 で紐付くため、判定は
「同じ家族か」と「立場」の 2 つだけで決まる。
"""

from __future__ import annotations

from bounded_contexts.reward_points.domain.entities.family_membership import FamilyMembership
from bounded_contexts.reward_points.domain.entities.point_ledger import PointLedger


def can_view_ledger(membership: FamilyMembership, ledger: PointLedger) -> bool:
    """親は家族の全ての台帳を、子は自分の台帳だけを見られる。

    兄弟の残高・履歴は相互に参照できない。
    """
    if not ledger.belongs_to_family(membership.family_id):
        return False
    if membership.role.is_guardian:
        return True
    return ledger.membership_id == membership.id


def can_modify_ledger(membership: FamilyMembership, ledger: PointLedger) -> bool:
    """加算・消費・訂正ができるか。子は自分の台帳でも変更できない。"""
    return ledger.belongs_to_family(membership.family_id) and membership.role.is_guardian


def can_administer_family(membership: FamilyMembership) -> bool:
    """家族そのものの管理（名前の変更・参加者の除名）。owner のみ。"""
    return membership.role.can_administer_family


def can_invite(membership: FamilyMembership) -> bool:
    """招待コードの発行。**家族の管理**にあたるので owner のみ。

    子の追加（呼び名と台帳を作る）は parent にも許すが、誰をこの家族へ入れるかは
    owner が決める。招待は「家族の構成を変える」操作で、除名と対になる。
    """
    return membership.role.can_administer_family


def can_create_child(membership: FamilyMembership) -> bool:
    return membership.role.is_guardian


def can_reset_password_of(actor: FamilyMembership, target: FamilyMembership) -> bool:
    """一時パスワードを発行できるか（ADR-0011）。

    親から親へのリセットは許可しない。対象が同一家族の ``role = child`` の
    場合に限る。
    """
    return (
        actor.role.is_guardian
        and actor.family_id == target.family_id
        and target.role.has_own_ledger
        and target.id != actor.id
    )


__all__ = [
    "can_administer_family",
    "can_create_child",
    "can_invite",
    "can_modify_ledger",
    "can_reset_password_of",
    "can_view_ledger",
]
