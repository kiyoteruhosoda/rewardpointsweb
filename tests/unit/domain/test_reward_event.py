"""イベント（がんばりカード）の決まり（ADR-0042）。

シールを貼る・はがす順序と、達成の冪等キー。DB に触らないので、カードを直接作って確かめる。
"""

from __future__ import annotations

from datetime import datetime

import pytest

from bounded_contexts.reward_points.domain.entities.reward_event import EventSticker, RewardEvent
from bounded_contexts.reward_points.domain.exceptions import RewardEventCompletedError, StickerOutOfOrderError
from bounded_contexts.reward_points.domain.value_objects.idempotency_key import is_derived
from bounded_contexts.reward_points.domain.value_objects.point_amount import PointAmount
from bounded_contexts.reward_points.domain.value_objects.transaction_reason import TransactionReason

_NOW = datetime(2026, 10, 3, 12, 0)


def _event(*, stuck: int = 0, goal_count: int = 3, completed: bool = False, reward: int = 50) -> RewardEvent:
    return RewardEvent(
        id=7,
        ledger_id=2,
        title=TransactionReason("はみがき"),
        reward=PointAmount(reward),
        goal_count=goal_count,
        stickers=tuple(EventSticker(number=n, stuck_at=_NOW) for n in range(1, stuck + 1)),
        completed_at=_NOW if completed else None,
        created_at=_NOW,
    )


def test_the_next_number_is_stuck() -> None:
    assert _event(stuck=1).should_stick(2) is True


def test_a_number_already_stuck_is_a_resend() -> None:
    assert _event(stuck=2).should_stick(1) is False


def test_skipping_a_number_is_out_of_order() -> None:
    with pytest.raises(StickerOutOfOrderError):
        _event(stuck=1, goal_count=3).should_stick(3)


def test_a_number_past_the_last_square_is_out_of_order() -> None:
    with pytest.raises(StickerOutOfOrderError):
        _event(stuck=3, goal_count=3).should_stick(4)


def test_a_completed_card_takes_nothing_new() -> None:
    with pytest.raises(RewardEventCompletedError):
        _event(stuck=3, goal_count=3, completed=True).should_stick(4)


def test_the_last_square_completes_the_card() -> None:
    event = _event(stuck=2, goal_count=3)

    assert event.completes_with(3) is True
    assert event.completes_with(2) is False


def test_only_the_last_sticker_peels() -> None:
    event = _event(stuck=2)

    assert event.should_peel(2) is True
    assert event.should_peel(3) is False
    with pytest.raises(StickerOutOfOrderError):
        event.should_peel(1)


def test_a_completed_card_does_not_peel() -> None:
    with pytest.raises(RewardEventCompletedError):
        _event(stuck=3, completed=True).should_peel(3)


def test_the_award_key_cannot_collide_with_a_users_key() -> None:
    """``#`` は利用者の鍵に現れない予約文字。手で書いた行と取り違えない。"""
    key = _event().award_key

    assert key == "reward-event#7"
    assert is_derived(key)


@pytest.mark.parametrize(("reward", "goal_count"), [(-5, 3), (10, 0), (10, 51)])
def test_a_card_that_takes_points_or_cannot_be_filled_is_invalid(reward: int, goal_count: int) -> None:
    with pytest.raises(ValueError, match=r"must|Goal"):
        _event(reward=reward, goal_count=goal_count)
