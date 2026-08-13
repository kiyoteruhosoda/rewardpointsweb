"""家族の参加者一覧を、画面が出せる形へ組み立てる。

参加者・台帳・残高・アカウント名は別々の入口から来るため、まとめて読んでから
1 回で突き合わせる（参加者ごとに引き直さない）。

台帳 ID・残高・毎日のボーナスの設定は、その参加者の台帳を **見られる相手にだけ**
載せる。兄弟の残高は相互に参照できない（ADR-0009）。名前は伏せない — 同じ家族に
誰がいるかは参加している時点で分かってよい。

毎日のボーナス（ADR-0024）の設定をここに載せるのは、決めるのが家族設定の画面
だから（ADR-0027）。子ども一人ひとりで量は違うので、参加者ごとに持つ。

「この人に何ができるか」（一時パスワード・独立の指示・削除）も、ここで決めて載せる。
画面が立場から組み立て直すと、サーバーが断る操作を出してしまう。

判断には 2 段の認可（router のモジュール docstring）が両方要る。家族の中での
立場・台帳の状態に加えて、**呼び出し元が ``family:manage`` を持っているか**
（``can_manage``）を受け取る。これらの操作の入口はすべて ``family:manage`` を
要求するので、立場だけで決めると、運用者がロールの権限を編集した後に
「owner なのに scope が無い」アカウントへ 403 になる操作を出してしまう。
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from bounded_contexts.reward_points.application.dto.daily_bonus_dto import DailyBonusDTO
from bounded_contexts.reward_points.application.dto.daily_bonus_dto import to_dto as bonus_to_dto
from bounded_contexts.reward_points.application.dto.family_dto import MembershipDTO
from bounded_contexts.reward_points.domain.entities.daily_bonus import DailyBonus
from bounded_contexts.reward_points.domain.entities.family_membership import FamilyMembership
from bounded_contexts.reward_points.domain.entities.point_ledger import PointLedger
from bounded_contexts.reward_points.domain.entities.point_transaction import PointTransaction
from bounded_contexts.reward_points.domain.repositories.account_directory import AccountRef, IAccountDirectory
from bounded_contexts.reward_points.domain.repositories.daily_bonus_repository import IDailyBonusRepository
from bounded_contexts.reward_points.domain.repositories.family_membership_repository import (
    IFamilyMembershipRepository,
)
from bounded_contexts.reward_points.domain.repositories.point_ledger_repository import IPointLedgerRepository
from bounded_contexts.reward_points.domain.repositories.point_transaction_repository import (
    IPointTransactionRepository,
)
from bounded_contexts.reward_points.domain.services import family_access_policy
from bounded_contexts.reward_points.domain.services.ledger_statement import LedgerStatement


@dataclass(frozen=True, kw_only=True)
class _LedgerView:
    """ある参加者の台帳を、閲覧者から見たところ。

    ``ledger_id`` ・ ``balance`` ・ ``daily_bonus`` は見える相手にだけ入る。
    ``is_empty`` は見え方に依らない事実で、削除できるかの判断に使う（記録の残る
    台帳は外せない）。
    """

    ledger_id: int | None
    balance: int | None
    # 毎日のボーナスの設定（ADR-0024）。決めていなければ ``None``
    daily_bonus: DailyBonusDTO | None
    is_empty: bool


@dataclass(frozen=True, kw_only=True)
class _Readings:
    """台帳 ID から引ける、家族ぶんの読み込み結果。"""

    entries: Mapping[int, list[PointTransaction]]
    bonuses: Mapping[int, DailyBonus]


class FamilyOverviewBuilder:
    def __init__(
        self,
        *,
        memberships: IFamilyMembershipRepository,
        ledgers: IPointLedgerRepository,
        transactions: IPointTransactionRepository,
        bonuses: IDailyBonusRepository,
        accounts: IAccountDirectory,
    ) -> None:
        self._memberships = memberships
        self._ledgers = ledgers
        self._transactions = transactions
        self._bonuses = bonuses
        self._accounts = accounts

    def build(self, viewer: FamilyMembership, *, can_manage: bool) -> tuple[MembershipDTO, ...]:
        members = self._memberships.list_for_family(viewer.family_id)
        ledgers = {ledger.membership_id: ledger for ledger in self._ledgers.list_for_family(viewer.family_id)}
        ledger_ids = [ledger.id for ledger in ledgers.values()]
        entries = self._transactions.list_by_ledgers(ledger_ids)
        # 毎日のボーナスの設定は家族設定に並ぶ（ADR-0027）。参加者ごとに引かず、
        # 台帳をまとめて 1 回で読む
        bonuses = {bonus.ledger_id: bonus for bonus in self._bonuses.list_for_ledgers(ledger_ids)}
        names = self._accounts.describe([m.account_id for m in members if m.account_id is not None])
        return tuple(
            _to_dto(
                member,
                viewer=viewer,
                ledger=_ledger_view(viewer, ledgers.get(member.id), _Readings(entries=entries, bonuses=bonuses)),
                username=_username_of(member, names),
                can_manage=can_manage,
            )
            for member in members
        )


def _ledger_view(
    viewer: FamilyMembership,
    ledger: PointLedger | None,
    readings: _Readings,
) -> _LedgerView:
    if ledger is None:
        # 台帳を持たない立場（親）。外すのを妨げる記録も無い
        return _LedgerView(ledger_id=None, balance=None, daily_bonus=None, is_empty=True)
    rows = readings.entries.get(ledger.id, [])
    bonus = readings.bonuses.get(ledger.id)
    visible = family_access_policy.can_view_ledger(viewer, ledger)
    return _LedgerView(
        ledger_id=ledger.id if visible else None,
        balance=LedgerStatement(rows).balance.value if visible else None,
        daily_bonus=bonus_to_dto(bonus) if visible and bonus else None,
        is_empty=not rows,
    )


def _username_of(member: FamilyMembership, names: Mapping[int, AccountRef]) -> str | None:
    if member.account_id is None:
        return None
    found = names.get(member.account_id)
    return found.username if found else None


def _to_dto(
    member: FamilyMembership,
    *,
    viewer: FamilyMembership,
    ledger: _LedgerView,
    username: str | None,
    can_manage: bool,
) -> MembershipDTO:
    return MembershipDTO(
        id=member.id,
        display_name=member.display_name_value,
        role=member.role,
        is_linked=member.is_linked,
        is_me=member.id == viewer.id,
        username=username,
        ledger_id=ledger.ledger_id,
        balance=ledger.balance,
        daily_bonus=ledger.daily_bonus,
        independence_proposed=member.independence_proposed,
        can_reset_password=can_manage and family_access_policy.can_issue_temporary_password_for(viewer, member),
        can_propose_independence=can_manage and family_access_policy.can_propose_independence_for(viewer, member),
        can_remove=can_manage
        and family_access_policy.can_remove_member(viewer, member, ledger_is_empty=ledger.is_empty),
    )


__all__ = ["FamilyOverviewBuilder"]
