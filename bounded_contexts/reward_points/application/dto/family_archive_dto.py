"""A whole-family archive — the exchange shape for backup and restore (ADR-0026).

Holds the family, members, ledgers, records and daily bonuses in one nested structure.
**Accounts are not included** — no login IDs, passwords or invitation codes appear here.
People re-join a restored family via invitation codes, provided separately from the
archive contents.

Links between rows (who recorded it, which record a reversal/correction targets) are
expressed as **refs** (``"m1"`` / ``"t1"``) that are meaningful only inside the file, not
as DB IDs. All IDs change at the restore destination, so writing exported IDs as-is would
always mismatch. With refs the links survive being carried to another instance.

Bump ``version`` when the shape changes. Unreadable versions are rejected with
:class:`~bounded_contexts.reward_points.domain.exceptions.UnsupportedArchiveVersionError`
— silently dropping unknown fields would make records vanish from a supposedly restored
family.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

from bounded_contexts.reward_points.domain.value_objects.family_role import FamilyRole

#: File kind. A marker to notice when another app's JSON is passed by mistake
ARCHIVE_FORMAT = "rewardpointsweb.family"

#: Version of the exported shape. Bump it when the shape changes
ARCHIVE_VERSION = 2

#: Versions that can be imported.
#:
#: The only difference from version 1 is whether the family rules (``family_rules``) are
#: included; without them the family can still be rebuilt as before (ADR-0027). **To keep
#: archives people already hold readable**, older versions are accepted as long as the added
#: fields are ones "the restore still works without". When the shape of records changes,
#: remove the old version from this set and reject it.
SUPPORTED_ARCHIVE_VERSIONS = frozenset({1, ARCHIVE_VERSION})


@dataclass(frozen=True, kw_only=True)
class ArchivedTransactionDTO:
    """One ledger row."""

    #: Name referring to this row within the file (unique within the ledger)
    ref: str
    amount: int
    reason: str
    occurred_at: datetime
    #: Ref of the recording member. None for daily bonuses (ADR-0024) and rows by people who
    #: left the family
    granted_by: str | None
    #: For a reversal row, the ref of the row it reverses (ADR-0010)
    reverses: str | None
    #: For a corrected row, the ref of the row it restates (ADR-0022)
    corrects: str | None


@dataclass(frozen=True, kw_only=True)
class ArchivedDailyBonusDTO:
    """A daily bonus arrangement (ADR-0024).

    ``granted_through`` is archived too. Dropping it would, right after a restore, revive
    the "days not yet granted" back to the start date, adding the bonus again for days
    whose rows are already in the archive.
    """

    amount: int
    reason: str
    starts_on: date
    granted_through: date | None


@dataclass(frozen=True, kw_only=True)
class ArchivedLedgerDTO:
    #: In writing order (oldest first). Reversals/corrections always come after their target
    transactions: tuple[ArchivedTransactionDTO, ...]
    daily_bonus: ArchivedDailyBonusDTO | None


@dataclass(frozen=True, kw_only=True)
class ArchivedMemberDTO:
    """Membership in the family. Does not record whose account it was."""

    ref: str
    display_name: str
    role: FamilyRole
    #: Only ``role = child`` has a ledger (ADR-0009)
    ledger: ArchivedLedgerDTO | None


@dataclass(frozen=True, kw_only=True)
class FamilyArchiveDTO:
    format: str
    version: int
    exported_at: datetime
    family_name: str
    #: Rules agreed in the family (ADR-0027). None if unwritten. Absent in version 1 archives
    family_rules: str | None
    #: On-screen order (owner first, then parents, finally children in the family's chosen order)
    members: tuple[ArchivedMemberDTO, ...]


@dataclass(frozen=True, kw_only=True)
class ImportedFamilyDTO:
    """Import result. Counts are returned so a person can check how much was restored."""

    family_id: int
    name: str
    member_count: int
    transaction_count: int


__all__ = [
    "ARCHIVE_FORMAT",
    "ARCHIVE_VERSION",
    "SUPPORTED_ARCHIVE_VERSIONS",
    "ArchivedDailyBonusDTO",
    "ArchivedLedgerDTO",
    "ArchivedMemberDTO",
    "ArchivedTransactionDTO",
    "FamilyArchiveDTO",
    "ImportedFamilyDTO",
]
