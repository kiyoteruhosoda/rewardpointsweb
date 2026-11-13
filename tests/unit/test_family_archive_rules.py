"""Consistency of the archive contents (ADR-0026).

Checks that the ledger rules (ADR-0010 / ADR-0022) hold not only at the recording entry point
but also at the import entry point. The round trip through the API is covered by
``tests/integration/api/test_family_archive.py``, so this lists "shapes that cannot be built
through this API" -- reversing a reversal, a double reversal, correcting a reversal.
"""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest

from bounded_contexts.reward_points.application import family_archive_rules
from bounded_contexts.reward_points.application.dto.family_archive_dto import (
    ARCHIVE_FORMAT,
    ARCHIVE_VERSION,
    ArchivedDailyBonusDTO,
    ArchivedLedgerDTO,
    ArchivedMemberDTO,
    ArchivedTransactionDTO,
    FamilyArchiveDTO,
)
from bounded_contexts.reward_points.domain.exceptions import InvalidFamilyArchiveError
from bounded_contexts.reward_points.domain.value_objects.family_role import FamilyRole

_OCCURRED = datetime(2026, 8, 9, 12, 0, tzinfo=UTC).replace(tzinfo=None)


def _entry(
    ref: str,
    amount: int,
    *,
    granted_by: str | None = None,
    reverses: str | None = None,
    corrects: str | None = None,
) -> ArchivedTransactionDTO:
    return ArchivedTransactionDTO(
        ref=ref,
        amount=amount,
        reason="おてつだい",
        occurred_at=_OCCURRED,
        granted_by=granted_by,
        reverses=reverses,
        corrects=corrects,
    )


def _archive(*entries: ArchivedTransactionDTO, bonus: ArchivedDailyBonusDTO | None = None) -> FamilyArchiveDTO:
    """An archive with one owner (``m1``) and one child with transferred history (``m2``)."""
    return FamilyArchiveDTO(
        format=ARCHIVE_FORMAT,
        version=ARCHIVE_VERSION,
        exported_at=_OCCURRED,
        family_name="ほその家",
        family_rules="ゲームは 1 日 1 時間",
        members=(
            ArchivedMemberDTO(ref="m1", display_name="おとうさん", role=FamilyRole.OWNER, ledger=None),
            ArchivedMemberDTO(
                ref="m2",
                display_name="たろう",
                role=FamilyRole.CHILD,
                ledger=ArchivedLedgerDTO(transactions=entries, daily_bonus=bonus),
            ),
        ),
    )


def _bonus(*, starts_on: date, granted_through: date | None) -> ArchivedDailyBonusDTO:
    return ArchivedDailyBonusDTO(
        amount=7,
        reason="まいにちボーナス",
        starts_on=starts_on,
        granted_through=granted_through,
    )


def test_a_plain_history_is_importable() -> None:
    family_archive_rules.require_importable(_archive(_entry("t1", 10), _entry("t2", -3)))


def test_an_undone_entry_is_importable() -> None:
    family_archive_rules.require_importable(_archive(_entry("t1", 10), _entry("t2", -10, reverses="t1")))


def test_a_corrected_entry_is_importable() -> None:
    family_archive_rules.require_importable(
        _archive(_entry("t1", 10), _entry("t2", -10, reverses="t1"), _entry("t3", 20, corrects="t1"))
    )


def test_an_undo_of_an_undo_is_refused() -> None:
    """A reversal cannot be reversed (ADR-0010)."""
    archive = _archive(_entry("t1", 10), _entry("t2", -10, reverses="t1"), _entry("t3", 10, reverses="t2"))

    with pytest.raises(InvalidFamilyArchiveError):
        family_archive_rules.require_importable(archive)


def test_undoing_the_same_entry_twice_is_refused() -> None:
    """Same rule as ``UNIQUE (reversal_of_id)``."""
    archive = _archive(_entry("t1", 10), _entry("t2", -10, reverses="t1"), _entry("t3", -10, reverses="t1"))

    with pytest.raises(InvalidFamilyArchiveError):
        family_archive_rules.require_importable(archive)


def test_correcting_an_undo_is_refused() -> None:
    """A reversal row cannot be corrected (ADR-0022)."""
    archive = _archive(_entry("t1", 10), _entry("t2", -10, reverses="t1"), _entry("t3", 5, corrects="t2"))

    with pytest.raises(InvalidFamilyArchiveError):
        family_archive_rules.require_importable(archive)


def test_correcting_the_same_entry_twice_is_refused() -> None:
    """Same rule as ``UNIQUE (corrects_id)``."""
    archive = _archive(
        _entry("t1", 10),
        _entry("t2", -10, reverses="t1"),
        _entry("t3", 20, corrects="t1"),
        _entry("t4", 30, corrects="t1"),
    )

    with pytest.raises(InvalidFamilyArchiveError):
        family_archive_rules.require_importable(archive)


def test_a_correction_without_the_undo_is_refused() -> None:
    """A correction is a single operation that always comes with a reversal (ADR-0022).

    Letting a restatement without a reversal through would yield a balance that adds both the
    still-effective original row and the corrected row.
    """
    archive = _archive(_entry("t1", 10), _entry("t2", 20, corrects="t1"))

    with pytest.raises(InvalidFamilyArchiveError):
        family_archive_rules.require_importable(archive)


def test_pointing_at_a_later_entry_is_refused() -> None:
    """The order decides the direction of links. A row cannot point to a later row."""
    archive = _archive(_entry("t1", -10, reverses="t2"), _entry("t2", 10))

    with pytest.raises(InvalidFamilyArchiveError):
        family_archive_rules.require_importable(archive)


def test_pointing_at_itself_is_refused() -> None:
    with pytest.raises(InvalidFamilyArchiveError):
        family_archive_rules.require_importable(_archive(_entry("t1", 10, reverses="t1")))


def test_an_undo_with_the_wrong_amount_is_refused() -> None:
    """A reversal has the opposite sign. A broken archive has a balance this API could not produce."""
    archive = _archive(_entry("t1", 10), _entry("t2", -4, reverses="t1"))

    with pytest.raises(InvalidFamilyArchiveError):
        family_archive_rules.require_importable(archive)


# --- Who recorded it --------------------------------------------------------


def test_a_guardian_can_be_the_one_who_recorded_it() -> None:
    family_archive_rules.require_importable(_archive(_entry("t1", 10, granted_by="m1")))


def test_a_child_cannot_be_the_one_who_recorded_it() -> None:
    """Only parents can write to the ledger (``can_modify_ledger``).

    An archive that names a child as the recorder is history this API could not produce.
    """
    with pytest.raises(InvalidFamilyArchiveError):
        family_archive_rules.require_importable(_archive(_entry("t1", 10, granted_by="m2")))


def test_someone_outside_the_family_cannot_be_the_one_who_recorded_it() -> None:
    with pytest.raises(InvalidFamilyArchiveError):
        family_archive_rules.require_importable(_archive(_entry("t1", 10, granted_by="m9")))


# --- Daily bonus -------------------------------------------------------------


def test_a_bonus_that_has_not_been_handed_out_yet_is_importable() -> None:
    archive = _archive(bonus=_bonus(starts_on=date(2026, 8, 9), granted_through=None))

    family_archive_rules.require_importable(archive)


def test_a_bonus_granted_before_it_starts_is_refused() -> None:
    """The granted-through date is never before the start date (ADR-0024).

    If it were allowed, the next grant would start the day after ``granted_through`` and bonuses
    would be added for dates before the start date.
    """
    archive = _archive(bonus=_bonus(starts_on=date(2026, 8, 9), granted_through=date(2026, 7, 1)))

    with pytest.raises(InvalidFamilyArchiveError):
        family_archive_rules.require_importable(archive)
