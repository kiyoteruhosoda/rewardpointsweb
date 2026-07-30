"""reward_points コンテキストの値オブジェクトの不変条件。"""

from __future__ import annotations

import pytest

from bounded_contexts.reward_points.domain.value_objects.entry_description import (
    MAX_LENGTH as DESCRIPTION_MAX_LENGTH,
)
from bounded_contexts.reward_points.domain.value_objects.entry_description import EntryDescription
from bounded_contexts.reward_points.domain.value_objects.member_name import MAX_LENGTH as NAME_MAX_LENGTH
from bounded_contexts.reward_points.domain.value_objects.member_name import MemberName
from bounded_contexts.reward_points.domain.value_objects.point_amount import MAX_VALUE as POINTS_MAX
from bounded_contexts.reward_points.domain.value_objects.point_amount import PointAmount


@pytest.mark.parametrize("value", ["", "   ", "\n"])
def test_member_name_rejects_blank(value: str) -> None:
    with pytest.raises(ValueError, match="empty"):
        MemberName(value)


def test_member_name_rejects_too_long() -> None:
    with pytest.raises(ValueError, match="exceed"):
        MemberName("あ" * (NAME_MAX_LENGTH + 1))


def test_member_name_accepts_the_maximum_length() -> None:
    assert MemberName("あ" * NAME_MAX_LENGTH).value


@pytest.mark.parametrize("value", [0, -1])
def test_point_amount_must_be_positive(value: int) -> None:
    """符号は履歴の種別が持つ。量そのものに 0 や負を許すと残高の意味が壊れる。"""
    with pytest.raises(ValueError, match="positive"):
        PointAmount(value)


def test_point_amount_rejects_above_the_maximum() -> None:
    with pytest.raises(ValueError, match="exceed"):
        PointAmount(POINTS_MAX + 1)


@pytest.mark.parametrize("value", ["", "  "])
def test_entry_description_rejects_blank(value: str) -> None:
    with pytest.raises(ValueError, match="empty"):
        EntryDescription(value)


def test_entry_description_rejects_too_long() -> None:
    with pytest.raises(ValueError, match="exceed"):
        EntryDescription("x" * (DESCRIPTION_MAX_LENGTH + 1))
