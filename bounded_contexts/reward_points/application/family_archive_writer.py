"""家族まるごとを控えの形へ組み立てる（ADR-0026）。

参加者・台帳・記録は別々の入口から来るため、まとめて読んでから 1 回で突き合わせる
（``FamilyOverviewBuilder`` と同じ形）。閲覧者による出し分けはしない — 控えは
「この家族の全部」であって、誰かから見た眺めではない。届いてよい相手かどうかは
呼び出し側（``ExportFamilyUseCase``）が先に決める。

記録は **ID の昇順** に並べる。打ち消し・訂正は必ず相手より後に書かれているので、
この順なら「相手が先に並ぶ」が保証される。発生日時で並べるとこれが崩れる —
訂正は元の行の発生日時を引き継ぐ（ADR-0022）うえ、日付そのものを直す訂正では
元より前の日時にもなる。
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from bounded_contexts.reward_points.application.dto.family_archive_dto import (
    ARCHIVE_FORMAT,
    ARCHIVE_VERSION,
    ArchivedDailyBonusDTO,
    ArchivedLedgerDTO,
    ArchivedMemberDTO,
    ArchivedTransactionDTO,
    FamilyArchiveDTO,
)
from bounded_contexts.reward_points.domain.entities.daily_bonus import DailyBonus
from bounded_contexts.reward_points.domain.entities.family_membership import FamilyMembership
from bounded_contexts.reward_points.domain.entities.point_ledger import PointLedger
from bounded_contexts.reward_points.domain.entities.point_transaction import PointTransaction
from bounded_contexts.reward_points.domain.exceptions import FamilyNotFoundError
from bounded_contexts.reward_points.domain.repositories.daily_bonus_repository import IDailyBonusRepository
from bounded_contexts.reward_points.domain.repositories.family_membership_repository import (
    IFamilyMembershipRepository,
)
from bounded_contexts.reward_points.domain.repositories.family_repository import IFamilyRepository
from bounded_contexts.reward_points.domain.repositories.point_ledger_repository import IPointLedgerRepository
from bounded_contexts.reward_points.domain.repositories.point_transaction_repository import (
    IPointTransactionRepository,
)
from shared.kernel.timestamps import utcnow


class FamilyArchiveWriter:
    def __init__(
        self,
        *,
        families: IFamilyRepository,
        memberships: IFamilyMembershipRepository,
        ledgers: IPointLedgerRepository,
        transactions: IPointTransactionRepository,
        bonuses: IDailyBonusRepository,
    ) -> None:
        self._families = families
        self._memberships = memberships
        self._ledgers = ledgers
        self._transactions = transactions
        self._bonuses = bonuses

    def write(self, family_id: int) -> FamilyArchiveDTO:
        family = self._families.find_by_id(family_id)
        if family is None:
            raise FamilyNotFoundError
        members = self._memberships.list_for_family(family_id)
        ledgers = {ledger.membership_id: ledger for ledger in self._ledgers.list_for_family(family_id)}
        histories = self._transactions.list_by_ledgers([ledger.id for ledger in ledgers.values()])
        member_refs = {member.id: f"m{index + 1}" for index, member in enumerate(members)}
        return FamilyArchiveDTO(
            format=ARCHIVE_FORMAT,
            version=ARCHIVE_VERSION,
            exported_at=utcnow(),
            family_name=family.name_value,
            family_rules=family.rules_value,
            members=tuple(
                self._member(member, ledger=ledgers.get(member.id), histories=histories, member_refs=member_refs)
                for member in members
            ),
        )

    def _member(
        self,
        membership: FamilyMembership,
        *,
        ledger: PointLedger | None,
        histories: Mapping[int, list[PointTransaction]],
        member_refs: Mapping[int, str],
    ) -> ArchivedMemberDTO:
        return ArchivedMemberDTO(
            ref=member_refs[membership.id],
            display_name=membership.display_name_value,
            role=membership.role,
            ledger=(
                None
                if ledger is None
                else self._ledger(ledger, history=histories.get(ledger.id, []), member_refs=member_refs)
            ),
        )

    def _ledger(
        self,
        ledger: PointLedger,
        *,
        history: Sequence[PointTransaction],
        member_refs: Mapping[int, str],
    ) -> ArchivedLedgerDTO:
        ordered = sorted(history, key=lambda transaction: transaction.id)
        entry_refs = {transaction.id: f"t{index + 1}" for index, transaction in enumerate(ordered)}
        return ArchivedLedgerDTO(
            transactions=tuple(
                _to_entry(transaction, entry_refs=entry_refs, member_refs=member_refs) for transaction in ordered
            ),
            daily_bonus=_to_bonus(self._bonuses.find_by_ledger(ledger.id)),
        )


def _to_entry(
    transaction: PointTransaction,
    *,
    entry_refs: Mapping[int, str],
    member_refs: Mapping[int, str],
) -> ArchivedTransactionDTO:
    return ArchivedTransactionDTO(
        ref=entry_refs[transaction.id],
        amount=transaction.amount.value,
        reason=transaction.reason.value,
        occurred_at=transaction.occurred_at,
        # 記録した人が家族を離れていれば参照は外れている（``SET NULL``）。控えでも空欄
        granted_by=_ref_of(transaction.granted_by_membership_id, member_refs),
        reverses=_ref_of(transaction.reversal_of_id, entry_refs),
        corrects=_ref_of(transaction.corrects_id, entry_refs),
    )


def _ref_of(row_id: int | None, refs: Mapping[int, str]) -> str | None:
    return None if row_id is None else refs.get(row_id)


def _to_bonus(bonus: DailyBonus | None) -> ArchivedDailyBonusDTO | None:
    if bonus is None:
        return None
    return ArchivedDailyBonusDTO(
        amount=bonus.amount.value,
        reason=bonus.reason.value,
        starts_on=bonus.starts_on,
        granted_through=bonus.granted_through,
    )


__all__ = ["FamilyArchiveWriter"]
