"""控えの中身の辻褄（ADR-0026）。

台帳の決まり（ADR-0010 / ADR-0022）が、記録の入口だけでなく取り込みの入口でも
効いていることを確かめる。API を通した往復は
``tests/integration/api/test_family_archive.py`` が見るので、ここでは「この API を
通しては作れない形」を並べる — 打ち消しの打ち消し、二重の打ち消し、打ち消しの訂正。
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
    """owner 1 人（``m1``）と、渡された履歴を持つ子 1 人（``m2``）の控え。"""
    return FamilyArchiveDTO(
        format=ARCHIVE_FORMAT,
        version=ARCHIVE_VERSION,
        exported_at=_OCCURRED,
        family_name="ほその家",
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
    """打ち消しは打ち消せない（ADR-0010）。"""
    archive = _archive(_entry("t1", 10), _entry("t2", -10, reverses="t1"), _entry("t3", 10, reverses="t2"))

    with pytest.raises(InvalidFamilyArchiveError):
        family_archive_rules.require_importable(archive)


def test_undoing_the_same_entry_twice_is_refused() -> None:
    """``UNIQUE (reversal_of_id)`` と同じ決まり。"""
    archive = _archive(_entry("t1", 10), _entry("t2", -10, reverses="t1"), _entry("t3", -10, reverses="t1"))

    with pytest.raises(InvalidFamilyArchiveError):
        family_archive_rules.require_importable(archive)


def test_correcting_an_undo_is_refused() -> None:
    """打ち消しの行は訂正できない（ADR-0022）。"""
    archive = _archive(_entry("t1", 10), _entry("t2", -10, reverses="t1"), _entry("t3", 5, corrects="t2"))

    with pytest.raises(InvalidFamilyArchiveError):
        family_archive_rules.require_importable(archive)


def test_correcting_the_same_entry_twice_is_refused() -> None:
    """``UNIQUE (corrects_id)`` と同じ決まり。"""
    archive = _archive(
        _entry("t1", 10),
        _entry("t2", -10, reverses="t1"),
        _entry("t3", 20, corrects="t1"),
        _entry("t4", 30, corrects="t1"),
    )

    with pytest.raises(InvalidFamilyArchiveError):
        family_archive_rules.require_importable(archive)


def test_a_correction_without_the_undo_is_refused() -> None:
    """訂正は打ち消しを必ず伴う 1 つの操作（ADR-0022）。

    打ち消しの無い言い直しを通すと、効いたままの元の行と訂正後の行が二重に
    足された残高になる。
    """
    archive = _archive(_entry("t1", 10), _entry("t2", 20, corrects="t1"))

    with pytest.raises(InvalidFamilyArchiveError):
        family_archive_rules.require_importable(archive)


def test_pointing_at_a_later_entry_is_refused() -> None:
    """並び順が繋がりの向きを決める。後ろを指す行は書けない。"""
    archive = _archive(_entry("t1", -10, reverses="t2"), _entry("t2", 10))

    with pytest.raises(InvalidFamilyArchiveError):
        family_archive_rules.require_importable(archive)


def test_pointing_at_itself_is_refused() -> None:
    with pytest.raises(InvalidFamilyArchiveError):
        family_archive_rules.require_importable(_archive(_entry("t1", 10, reverses="t1")))


def test_an_undo_with_the_wrong_amount_is_refused() -> None:
    """打ち消しは逆符号。崩れた控えは、この API を通しては作れない残高を持つ。"""
    archive = _archive(_entry("t1", 10), _entry("t2", -4, reverses="t1"))

    with pytest.raises(InvalidFamilyArchiveError):
        family_archive_rules.require_importable(archive)


# --- 記録した人 --------------------------------------------------------------


def test_a_guardian_can_be_the_one_who_recorded_it() -> None:
    family_archive_rules.require_importable(_archive(_entry("t1", 10, granted_by="m1")))


def test_a_child_cannot_be_the_one_who_recorded_it() -> None:
    """台帳へ書けるのは親だけ（``can_modify_ledger``）。

    子の名前を記録者に置いた控えは、この API を通しては作れない履歴になる。
    """
    with pytest.raises(InvalidFamilyArchiveError):
        family_archive_rules.require_importable(_archive(_entry("t1", 10, granted_by="m2")))


def test_someone_outside_the_family_cannot_be_the_one_who_recorded_it() -> None:
    with pytest.raises(InvalidFamilyArchiveError):
        family_archive_rules.require_importable(_archive(_entry("t1", 10, granted_by="m9")))


# --- 毎日のボーナス ----------------------------------------------------------


def test_a_bonus_that_has_not_been_handed_out_yet_is_importable() -> None:
    archive = _archive(bonus=_bonus(starts_on=date(2026, 8, 9), granted_through=None))

    family_archive_rules.require_importable(archive)


def test_a_bonus_granted_before_it_starts_is_refused() -> None:
    """渡し終えた日は開始日より前にならない（ADR-0024）。

    通すと、次の付与が ``granted_through`` の翌日から始まり、開始日より前の
    日付でボーナスが足される。
    """
    archive = _archive(bonus=_bonus(starts_on=date(2026, 8, 9), granted_through=date(2026, 7, 1)))

    with pytest.raises(InvalidFamilyArchiveError):
        family_archive_rules.require_importable(archive)
