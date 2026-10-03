"""イベント（ADR-0042）。

子の台帳 1 つに、いくつでも持てる「がんばりカード」。目標（``title``）・達成で
もらえるポイント（``reward``）・達成回数（``goal_count``）を決めておき、1 回達成
するたびにシールを 1 枚貼る。マスが全部埋まったら目標達成で、そのとき台帳へ
``reward`` を 1 行足す。

シールは **番号つき** で貼る（1 枚目・2 枚目…）。番号は画面が「次に貼る番号」を
送るので、同じ押下が 2 度届いても 2 枚にはならない（``UNIQUE (event_id, number)``）。
はがせるのは最後の 1 枚だけ（押し間違いを戻すため）。達成した後は貼るのも
はがすのもできない — ポイントはもう台帳に入っている。

期限（``deadline``）は任意の日付。期限の日が終わるまでに埋まらなければ **期限切れ** で、
それ以上は貼れない（ポイントも入らない）。日付の区切りは家族の暮らしの 1 日
（:class:`~...day_boundary.DayBoundary`）で、判定に使う「今日」は呼び出し側が渡す。
親が期限を延ばせば、また貼れるようになる。

達成の 1 行は **イベントごとに 1 つ** の冪等キー（``reward-event#<id>``）で書く。
2 人の親が同時に最後の 1 枚を貼っても、台帳には 1 行しか入らない。``#`` は
利用者の送る鍵には現れない（:func:`~...idempotency_key.is_derived`）ので、
手で書いた行とぶつかることも無い。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

from bounded_contexts.reward_points.domain.exceptions import (
    RewardEventCompletedError,
    RewardEventExpiredError,
    StickerOutOfOrderError,
)
from bounded_contexts.reward_points.domain.value_objects.idempotency_key import STEP_SEPARATOR, IdempotencyKey
from bounded_contexts.reward_points.domain.value_objects.point_amount import PointAmount
from bounded_contexts.reward_points.domain.value_objects.transaction_reason import TransactionReason

#: 目標の長さの上限。カードの見出しに収まる長さに留める（台帳の理由の上限より短い）
TITLE_MAX_LENGTH = 100

#: 達成回数の上限。1 枚のカードにマスが並び切る数に留める（画面は 1 画面で見せる）
MAX_GOAL_COUNT = 50

#: 達成の 1 行の冪等キーの土台。``reward-event#<id>`` の形で使う
IDEMPOTENCY_BASE = "reward-event"


@dataclass(frozen=True, kw_only=True)
class EventSticker:
    """貼られた 1 枚。``number`` は 1 から始まる通し番号。"""

    number: int
    stuck_at: datetime


@dataclass(frozen=True, kw_only=True)
class RewardEvent:
    id: int
    ledger_id: int
    title: TransactionReason
    reward: PointAmount
    goal_count: int
    #: 番号の小さい順
    stickers: tuple[EventSticker, ...]
    #: マスが埋まった日時。まだなら ``None``
    completed_at: datetime | None
    created_at: datetime
    #: この日のうちに埋めれば達成。決めていなければ ``None``（いつまでも貼れる）
    deadline: date | None = None

    def __post_init__(self) -> None:
        # 達成で減るイベントは無い（消費は手で記録する）
        if self.reward.value <= 0:
            raise ValueError("Reward event must add points")
        if len(self.title.value) > TITLE_MAX_LENGTH:
            raise ValueError(f"Reward event title cannot exceed {TITLE_MAX_LENGTH} characters")
        if not 1 <= self.goal_count <= MAX_GOAL_COUNT:
            raise ValueError(f"Goal count must be 1..{MAX_GOAL_COUNT}")

    @property
    def sticker_count(self) -> int:
        return len(self.stickers)

    @property
    def is_completed(self) -> bool:
        return self.completed_at is not None

    def is_expired(self, today: date) -> bool:
        """期限の日を過ぎても埋まっていないか。達成したカードは期限切れにならない。"""
        return not self.is_completed and self.deadline is not None and today > self.deadline

    @property
    def award_key(self) -> str:
        """達成の 1 行の冪等キー。同じイベントからは必ず同じ値が出る。"""
        return IdempotencyKey(f"{IDEMPOTENCY_BASE}{STEP_SEPARATOR}{self.id}").value

    def should_stick(self, number: int, *, today: date) -> bool:
        """*number* 枚目を **いま貼るべきか**。

        すでに貼ってある番号なら偽（同じ押下の再送。何もせずに今の姿を返す）。
        飛ばした番号・マスの外・達成済み・期限切れは例外にする — 画面が古い姿を見ている。
        """
        if number <= self.sticker_count:
            return False
        if self.is_completed:
            raise RewardEventCompletedError
        if self.is_expired(today):
            raise RewardEventExpiredError
        if number != self.sticker_count + 1 or number > self.goal_count:
            raise StickerOutOfOrderError
        return True

    def completes_with(self, number: int) -> bool:
        """*number* 枚目でマスが埋まるか。"""
        return number == self.goal_count

    def should_peel(self, number: int) -> bool:
        """*number* 枚目を **いまはがすべきか**。

        もう無い番号なら偽（はがしたいという求めは満たされている）。はがせるのは
        最後の 1 枚だけで、達成した後ははがせない。
        """
        if self.is_completed:
            raise RewardEventCompletedError
        if number > self.sticker_count:
            return False
        if number != self.sticker_count:
            raise StickerOutOfOrderError
        return True


__all__ = ["IDEMPOTENCY_BASE", "MAX_GOAL_COUNT", "TITLE_MAX_LENGTH", "EventSticker", "RewardEvent"]
