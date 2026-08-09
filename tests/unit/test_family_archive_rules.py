"""控えの中身の辻褄（ADR-0025）。

台帳の決まり（ADR-0010 / ADR-0022）が、記録の入口だけでなく取り込みの入口でも
効いていることを確かめる。API を通した往復は
``tests/integration/api/test_family_archive.py`` が見るので、ここでは「この API を
通しては作れない形」を並べる — 打ち消しの打ち消し、二重の打ち消し、打ち消しの訂正。
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from bounded_contexts.reward_points.application import family_archive_rules
from bounded_contexts.reward_points.application.dto.family_archive_dto import (
    ARCHIVE_FORMAT,
    ARCHIVE_VERSION,
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
    reverses: str | None = None,
    corrects: str | None = None,
) -> ArchivedTransactionDTO:
    return ArchivedTransactionDTO(
        ref=ref,
        amount=amount,
        reason="おてつだい",
        occurred_at=_OCCURRED,
        granted_by=None,
        reverses=reverses,
        corrects=corrects,
    )


def _archive(*entries: ArchivedTransactionDTO) -> FamilyArchiveDTO:
    """owner 1 人と、渡された履歴を持つ子 1 人の控え。"""
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
                ledger=ArchivedLedgerDTO(transactions=entries, daily_bonus=None),
            ),
        ),
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
    archive = _archive(_entry("t1", 10), _entry("t2", 20, corrects="t1"), _entry("t3", 30, corrects="t1"))

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
