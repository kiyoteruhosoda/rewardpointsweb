"""Rebuild a family from an archive (restore; ADR-0026).

An import always creates a **new family**. There is no way to merge into an existing
family — when two children with the same name end up side by side, only a person can tell
which is from the archive and which is current; letting the machine choose would silently
duplicate ledgers.

The importer takes the owner's seat. The owner's display name from the archive is kept,
so the on-screen order returns to what it was at export. **Other members are created
without linked accounts** — the archive holds no accounts (ADR-0026), so people re-join via
invitation codes (ADR-0011). Children are restored with their ledgers, so an invited child
logs in with their records intact.

All ledger rows are written as **appends** (ADR-0010). The event time comes from the
archive and the recorded time is the moment of import — it is a fact that the row was
written to this DB now, and we do not falsify that.
"""

from __future__ import annotations

from dataclasses import dataclass

from bounded_contexts.reward_points.application import family_archive_rules
from bounded_contexts.reward_points.application.dto.family_archive_dto import (
    ArchivedLedgerDTO,
    ArchivedMemberDTO,
    FamilyArchiveDTO,
    ImportedFamilyDTO,
)
from bounded_contexts.reward_points.domain.entities.family_membership import FamilyMembership
from bounded_contexts.reward_points.domain.exceptions import AlreadyBelongsToFamilyError
from bounded_contexts.reward_points.domain.repositories.daily_bonus_repository import (
    DailyBonusDraft,
    IDailyBonusRepository,
)
from bounded_contexts.reward_points.domain.repositories.family_membership_repository import (
    IFamilyMembershipRepository,
)
from bounded_contexts.reward_points.domain.repositories.family_repository import IFamilyRepository
from bounded_contexts.reward_points.domain.repositories.point_ledger_repository import IPointLedgerRepository
from bounded_contexts.reward_points.domain.repositories.point_transaction_repository import (
    IPointTransactionRepository,
    NewTransaction,
)
from shared.kernel.timestamps import as_naive_utc

#: Prefix of idempotency keys for imported rows, followed by the archive ref (``import-t1``).
#:
#: Archive refs are unique within a ledger (``family_archive_rules``), so the keys also
#: satisfy ``UNIQUE (ledger_id, idempotency_key)``. Keys from the exporting side are not
#: carried over — they exist to detect "the same request arriving twice" and mean nothing
#: in another ledger.
IMPORT_KEY_PREFIX = "import-"


@dataclass(frozen=True, kw_only=True)
class ImportFamilyCommand:
    account_id: int
    archive: FamilyArchiveDTO


class ImportFamilyUseCase:
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

    def execute(self, command: ImportFamilyCommand) -> ImportedFamilyDTO:
        archive = command.archive
        family_archive_rules.require_importable(archive)
        # An account may belong to at most one family (ADR-0013). Reject on the same condition as creation
        if self._memberships.list_for_account(command.account_id):
            raise AlreadyBelongsToFamilyError

        family = self._families.add(name=archive.family_name, rules=archive.family_rules)
        members = self._restore_members(family_id=family.id, command=command)
        written = sum(self._restore_ledger(member, family_id=family.id, members=members) for member in archive.members)
        return ImportedFamilyDTO(
            family_id=family.id,
            name=family.name_value,
            member_count=len(members),
            transaction_count=written,
        )

    def _restore_members(self, *, family_id: int, command: ImportFamilyCommand) -> dict[str, FamilyMembership]:
        """Create memberships in archive order (sort order follows creation order).

        Only the owner is linked to the importer. The rest are unlinked; each person joins
        later with the invitation code they receive (ADR-0011).
        """
        return {
            member.ref: self._memberships.add(
                family_id=family_id,
                account_id=command.account_id if member.role.can_administer_family else None,
                role=member.role,
                display_name=member.display_name,
            )
            for member in command.archive.members
        }

    def _restore_ledger(
        self, member: ArchivedMemberDTO, *, family_id: int, members: dict[str, FamilyMembership]
    ) -> int:
        """Create the child's ledger and restore records and daily bonus. Returns the rows written."""
        if member.ledger is None:
            return 0
        ledger = self._ledgers.add(family_id=family_id, membership_id=members[member.ref].id)
        written = self._append_history(member.ledger, ledger_id=ledger.id, members=members)
        self._restore_daily_bonus(member.ledger, ledger_id=ledger.id)
        return written

    def _append_history(
        self, archived: ArchivedLedgerDTO, *, ledger_id: int, members: dict[str, FamilyMembership]
    ) -> int:
        # The archive is in writing order, so reversal/correction targets are already written
        ids: dict[str, int] = {}
        for entry in archived.transactions:
            actor = members[entry.granted_by] if entry.granted_by else None
            appended = self._transactions.append(
                NewTransaction(
                    ledger_id=ledger_id,
                    amount=entry.amount,
                    reason=entry.reason,
                    granted_by_membership_id=actor.id if actor else None,
                    # The archive is external JSON carrying offsets (exports use ``Z``), so
                    # normalise to naive UTC like stored values before writing
                    occurred_at=as_naive_utc(entry.occurred_at),
                    idempotency_key=f"{IMPORT_KEY_PREFIX}{entry.ref}",
                    reversal_of_id=ids[entry.reverses] if entry.reverses else None,
                    corrects_id=ids[entry.corrects] if entry.corrects else None,
                )
            )
            ids[entry.ref] = appended.id
        return len(archived.transactions)

    def _restore_daily_bonus(self, archived: ArchivedLedgerDTO, *, ledger_id: int) -> None:
        bonus = archived.daily_bonus
        if bonus is None:
            return
        saved = self._bonuses.save(
            DailyBonusDraft(
                ledger_id=ledger_id,
                amount=bonus.amount,
                reason=bonus.reason,
                starts_on=bonus.starts_on,
            )
        )
        # Restore the last granted day. Dropping it would add bonuses for days already in the
        # archive again right after import (the ADR-0024 catch-up)
        if bonus.granted_through is not None:
            self._bonuses.mark_granted_through(bonus_id=saved.id, day=bonus.granted_through)


__all__ = ["IMPORT_KEY_PREFIX", "ImportFamilyCommand", "ImportFamilyUseCase"]
