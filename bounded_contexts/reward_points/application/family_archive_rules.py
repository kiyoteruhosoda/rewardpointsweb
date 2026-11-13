"""Before importing an archive, check that it can be written (ADR-0026).

Presence, types and lengths of fields are checked first by Pydantic. This module checks
**internal consistency**, asking "could the same family be built by calling this API in
order?". An archive that could not be built is rejected without writing a single row —
the import is one transaction, so noticing midway would only roll back, but this keeps the
guarantee that no half-written family remains somewhere the caller can read.

The ledger rules (a reversal cannot be reversed, a row can be reversed only once, a
reversal cannot be corrected; ADR-0010 / ADR-0022) are enforced here exactly as at the
recording entry points. No loophole where only rows from an archive are exempt.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence

from bounded_contexts.reward_points.application.dto.family_archive_dto import (
    ARCHIVE_FORMAT,
    SUPPORTED_ARCHIVE_VERSIONS,
    ArchivedDailyBonusDTO,
    ArchivedLedgerDTO,
    ArchivedMemberDTO,
    ArchivedTransactionDTO,
    FamilyArchiveDTO,
)
from bounded_contexts.reward_points.domain.exceptions import (
    InvalidFamilyArchiveError,
    UnsupportedArchiveVersionError,
)


def require_importable(archive: FamilyArchiveDTO) -> None:
    """Raise unless the archive can be imported."""
    _require_readable_format(archive)
    _unique_refs(member.ref for member in archive.members)
    _require_single_owner(archive.members)
    # Only parents can write to ledgers (``can_modify_ledger``). An archive with a child in the
    # recorder field holds a history that could not be created through this API
    recorders = frozenset(member.ref for member in archive.members if member.role.is_guardian)
    for member in archive.members:
        _require_person(member)
        _require_ledger_matches_role(member)
        if member.ledger is not None:
            _require_writable_ledger(member.ledger, recorders=recorders)


def _require_readable_format(archive: FamilyArchiveDTO) -> None:
    if archive.format != ARCHIVE_FORMAT:
        raise InvalidFamilyArchiveError
    # Do not read just the readable parts of an unknown version. If dropped fields held
    # records, the import would look successful while content was lost. Older versions are
    # accepted only when they are known to lack nothing but fields "the restore works without"
    if archive.version not in SUPPORTED_ARCHIVE_VERSIONS:
        raise UnsupportedArchiveVersionError


def _unique_refs(refs: Iterable[str]) -> frozenset[str]:
    seen: set[str] = set()
    for ref in refs:
        if ref in seen:
            raise InvalidFamilyArchiveError
        seen.add(ref)
    return frozenset(seen)


def _require_single_owner(members: Sequence[ArchivedMemberDTO]) -> None:
    """Exactly one owner.

    The importer takes that seat (``ImportFamilyUseCase``). With zero, nobody could manage
    the family; with two or more, it is undecidable whose name the importer inherits.
    """
    owners = [member for member in members if member.role.can_administer_family]
    if len(owners) != 1:
        raise InvalidFamilyArchiveError


def _require_person(member: ArchivedMemberDTO) -> None:
    """Only people go into an archive. Display devices are never exported (ADR-0047): one present means tampering."""
    if member.role.is_display:
        raise InvalidFamilyArchiveError


def _require_ledger_matches_role(member: ArchivedMemberDTO) -> None:
    """Only children have a ledger, and every child has one (ADR-0009)."""
    if (member.ledger is not None) != member.role.has_own_ledger:
        raise InvalidFamilyArchiveError


def _require_writable_ledger(ledger: ArchivedLedgerDTO, *, recorders: frozenset[str]) -> None:
    _require_consistent_bonus(ledger.daily_bonus)
    _require_writable_history(ledger.transactions, recorders=recorders)


def _require_consistent_bonus(bonus: ArchivedDailyBonusDTO | None) -> None:
    """The last granted day must not precede the first day to grant (ADR-0024).

    Granted days are always on or after ``starts_on``, so a genuine archive never breaks this.
    If a tampered archive got through, the next grant would start the day after
    ``granted_through``, **adding bonuses dated before the start date**
    (``DailyBonus.due_days``).
    """
    if bonus is None or bonus.granted_through is None:
        return
    if bonus.granted_through < bonus.starts_on:
        raise InvalidFamilyArchiveError


def _require_writable_history(entries: Sequence[ArchivedTransactionDTO], *, recorders: frozenset[str]) -> None:
    history = _WrittenHistory()
    for entry in entries:
        # The recorder must be a member of this family allowed to write ledgers (a parent)
        if entry.granted_by is not None and entry.granted_by not in recorders:
            raise InvalidFamilyArchiveError
        history.append(entry)


class _WrittenHistory:
    """Track "rows written so far" following the order.

    An archive is in writing order, so the target of a reversal/correction is always
    **earlier**. Checking that links only point backwards rejects both cyclic references
    and references to rows not yet present with one single rule.
    """

    def __init__(self) -> None:
        self._amounts: dict[str, int] = {}
        self._reversals: set[str] = set()
        self._reversed: set[str] = set()
        self._corrected: set[str] = set()

    def append(self, entry: ArchivedTransactionDTO) -> None:
        if entry.ref in self._amounts:
            raise InvalidFamilyArchiveError
        self._claim_reversal(entry)
        self._claim_correction(entry)
        self._amounts[entry.ref] = entry.amount
        if entry.reverses is not None:
            self._reversals.add(entry.ref)

    def _claim_reversal(self, entry: ArchivedTransactionDTO) -> None:
        target = entry.reverses
        if target is None:
            return
        # A reversal cannot be reversed (ADR-0010), and a row cannot be reversed twice
        # (``UNIQUE (reversal_of_id)``)
        if target in self._reversals or target in self._reversed:
            raise InvalidFamilyArchiveError
        # A reversal has the opposite sign (``PointTransaction.plan_reversal``). An archive
        # breaking this holds a balance that could not be produced through this API
        if entry.amount != -self._amount_of(target):
            raise InvalidFamilyArchiveError
        self._reversed.add(target)

    def _claim_correction(self, entry: ArchivedTransactionDTO) -> None:
        target = entry.corrects
        if target is None:
            return
        # A reversal row cannot be corrected (ADR-0022), and a row can be restated only once
        # (``UNIQUE (corrects_id)``)
        if target in self._reversals or target in self._corrected:
            raise InvalidFamilyArchiveError
        self._amount_of(target)
        # A correction is a single "reverse and rewrite" operation and always comes with a
        # reversal row (``CorrectPointTransactionUseCase``). Letting a restatement through
        # without a reversal would double-count the still-effective original and the corrected row
        if target not in self._reversed:
            raise InvalidFamilyArchiveError
        self._corrected.add(target)

    def _amount_of(self, ref: str) -> int:
        """A row not yet written cannot be referenced."""
        amount = self._amounts.get(ref)
        if amount is None:
            raise InvalidFamilyArchiveError
        return amount


__all__ = ["require_importable"]
