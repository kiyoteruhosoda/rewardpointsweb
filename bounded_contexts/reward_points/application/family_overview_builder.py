"""家族の参加者一覧を、画面が出せる形へ組み立てる。

参加者・台帳・残高・アカウント名は別々の入口から来るため、まとめて読んでから
1 回で突き合わせる（参加者ごとに引き直さない）。

台帳 ID と残高は、その参加者の台帳を **見られる相手にだけ** 載せる。兄弟の
残高は相互に参照できない（ADR-0009）。名前は伏せない — 同じ家族に誰がいるかは
参加している時点で分かってよい。
"""

from __future__ import annotations

from collections.abc import Mapping

from bounded_contexts.reward_points.application.dto.family_dto import MembershipDTO
from bounded_contexts.reward_points.domain.entities.family_membership import FamilyMembership
from bounded_contexts.reward_points.domain.entities.point_ledger import PointLedger
from bounded_contexts.reward_points.domain.repositories.account_directory import AccountRef, IAccountDirectory
from bounded_contexts.reward_points.domain.repositories.family_membership_repository import (
    IFamilyMembershipRepository,
)
from bounded_contexts.reward_points.domain.repositories.point_ledger_repository import IPointLedgerRepository
from bounded_contexts.reward_points.domain.repositories.point_transaction_repository import (
    IPointTransactionRepository,
)
from bounded_contexts.reward_points.domain.services import family_access_policy
from bounded_contexts.reward_points.domain.services.ledger_statement import LedgerStatement


class FamilyOverviewBuilder:
    def __init__(
        self,
        *,
        memberships: IFamilyMembershipRepository,
        ledgers: IPointLedgerRepository,
        transactions: IPointTransactionRepository,
        accounts: IAccountDirectory,
    ) -> None:
        self._memberships = memberships
        self._ledgers = ledgers
        self._transactions = transactions
        self._accounts = accounts

    def build(self, viewer: FamilyMembership) -> tuple[MembershipDTO, ...]:
        members = self._memberships.list_for_family(viewer.family_id)
        ledgers = {ledger.membership_id: ledger for ledger in self._ledgers.list_for_family(viewer.family_id)}
        balances = self._balances(list(ledgers.values()))
        names = self._accounts.describe([m.account_id for m in members if m.account_id is not None])
        return tuple(
            _to_dto(
                member,
                viewer=viewer,
                ledger=ledgers.get(member.id),
                balances=balances,
                username=_username_of(member, names),
            )
            for member in members
        )

    def _balances(self, ledgers: list[PointLedger]) -> dict[int, int]:
        grouped = self._transactions.list_by_ledgers([ledger.id for ledger in ledgers])
        return {ledger_id: LedgerStatement(rows).balance.value for ledger_id, rows in grouped.items()}


def _username_of(member: FamilyMembership, names: Mapping[int, AccountRef]) -> str | None:
    if member.account_id is None:
        return None
    found = names.get(member.account_id)
    return found.username if found else None


def _to_dto(
    member: FamilyMembership,
    *,
    viewer: FamilyMembership,
    ledger: PointLedger | None,
    balances: dict[int, int],
    username: str | None,
) -> MembershipDTO:
    visible = ledger is not None and family_access_policy.can_view_ledger(viewer, ledger)
    return MembershipDTO(
        id=member.id,
        display_name=member.display_name_value,
        role=member.role,
        is_linked=member.is_linked,
        is_me=member.id == viewer.id,
        username=username,
        ledger_id=ledger.id if visible and ledger else None,
        balance=balances.get(ledger.id, 0) if visible and ledger else None,
        independence_proposed=member.independence_proposed,
    )


__all__ = ["FamilyOverviewBuilder"]
