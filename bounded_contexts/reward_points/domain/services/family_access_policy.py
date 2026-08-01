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
from bounded_contexts.reward_points.domain.value_objects.family_role import FamilyRole


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


def can_invite(membership: FamilyMembership, invited: FamilyRole) -> bool:
    """招待コードを発行できるか。配る立場で分かれる（ADR-0020）。

    **新しい人を家族へ入れる招待（親）は owner のみ。** 誰をこの家族へ入れるかは
    owner が決める。除名と対になる「家族の構成を変える」操作だから。

    **すでにいる子ども宛の招待は親（owner / parent）も配れる。** 指す先は自分たちが
    作った未紐付けの参加者だけで、顔ぶれは変わらない — 変わるのは「その子が本人と
    してログインできるか」だけ。子の参加を作れるのは親なのだから
    （:func:`can_create_child`）、作った本人がログインを渡せないと経路が途切れる。
    """
    if invited.has_own_ledger:
        return membership.role.is_guardian
    return membership.role.can_administer_family


def can_create_child(membership: FamilyMembership) -> bool:
    return membership.role.is_guardian


def can_reorder_members(membership: FamilyMembership) -> bool:
    """参加者の並び順を変えられるか。親（owner / parent）なら変えられる。

    並びは見え方だけの話で、家族の構成も台帳も動かさない。除名や招待と同じ
    「家族の管理」に含めると、日々の画面を整えるのに owner を呼ぶことになる。
    """
    return membership.role.is_guardian


def can_propose_independence_for(actor: FamilyMembership, target: FamilyMembership) -> bool:
    """独立を指示できるか（ADR-0014）。

    対象はアカウントの結び付いた子だけ。未紐付けの子は本人が承認のしようが
    ないので、そちらは :func:`can_remove_member`（削除）が受け持つ。
    """
    return actor.role.is_guardian and target.role.has_own_ledger and target.is_linked


def can_remove_member(actor: FamilyMembership, target: FamilyMembership, *, ledger_is_empty: bool) -> bool:
    """参加者を家族から削除できるか。

    owner だけができ、自分自身は外せない（家族を管理できる人がいなくなる）。
    記録の残る台帳は道連れにしない（``ledger_not_empty``。ADR-0010）ので、
    台帳が空であることも条件に含める — 押してから断られる操作を画面に出さない。
    """
    return actor.role.can_administer_family and target.id != actor.id and ledger_is_empty


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


def can_issue_temporary_password_for(actor: FamilyMembership, target: FamilyMembership) -> bool:
    """いま一時パスワードを発行できるか（画面の出し分け用）。

    :func:`can_reset_password_of` に「本人のアカウントがあること」を足したもの。
    立場の判定（誰に対して許すか）と、アカウントの有無（今できるか）は別の理由で
    断られる — ユースケースは区別してエラーコードを返し、画面は両方が揃った
    ときだけボタンを出す。
    """
    return can_reset_password_of(actor, target) and target.is_linked


__all__ = [
    "can_administer_family",
    "can_create_child",
    "can_invite",
    "can_issue_temporary_password_for",
    "can_modify_ledger",
    "can_propose_independence_for",
    "can_remove_member",
    "can_reorder_members",
    "can_reset_password_of",
    "can_view_ledger",
]
