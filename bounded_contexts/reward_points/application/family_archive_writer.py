"""Assemble an entire family into the archive shape (ADR-0026).

Members, ledgers and records come from separate sources, so they are read in bulk and
matched up in one pass (same shape as ``FamilyOverviewBuilder``). Nothing is filtered by
viewer — the archive is "everything in this family", not a view from someone's perspective.
Whether the recipient may receive it is decided beforehand by the caller (``ExportFamilyUseCase``).

Records are ordered by **ascending ID**. Reversals and corrections are always written after
their target, so this order guarantees "the target comes first". Ordering by occurrence time
breaks this — a correction inherits the original row's occurrence time (ADR-0022), and a
correction that fixes the date itself can even be earlier than the original.
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
        # Display devices are not archived. A device is not owned by the family; it only comes
        # into being through operator approval (ADR-0047). On import there would be no device to show it
        members = [member for member in self._memberships.list_for_family(family_id) if not member.role.is_display]
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
        # If the recorder has left the family the reference is cleared (``SET NULL``). Blank in the archive too
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
