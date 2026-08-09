"""毎日のボーナス（ADR-0024）。

子の台帳 1 つにつき 1 つ。「毎日いくつ足すか」を持ち、日付が変わったら台帳へ
1 行追記される。追記そのものは台帳の決まりに従うので、ここは **どの日がまだ
渡っていないか** だけを受け持つ。

渡した所までを ``granted_through`` で覚える。次に動いたときは翌日から今日までを
まとめて渡すので、アプリが止まっていた日も飛ばない。ただし長く止まっていた分を
際限なく取り戻すと、久しぶりに開いた台帳が数百行のボーナスで埋まる。遡る日数には
上限を置き、超えた分は捨てたことを呼び出し側が言えるよう数で返す。

二重付与は冪等キーで止める（``UNIQUE (ledger_id, idempotency_key)``。ADR-0010）。
キーは日付そのものから決まるので、同じ日を 2 度渡そうとしても台帳には 1 行しか
入らない — 複数のワーカーが同時に動いても、追いつきが途中で落ちて再開しても同じ。
段階付きの鍵（``daily-bonus#2026-08-09``）にしてあるのは、利用者が送る鍵には
``#`` が現れないから（:func:`~...idempotency_key.is_derived`）。ボーナスの行と
手で書いた行が同じ鍵にぶつかることは無い。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from bounded_contexts.reward_points.domain.value_objects.idempotency_key import IdempotencyKey
from bounded_contexts.reward_points.domain.value_objects.point_amount import PointAmount
from bounded_contexts.reward_points.domain.value_objects.transaction_reason import TransactionReason

#: 冪等キーの土台。日付を段階として足した形（``daily-bonus#2026-08-09``）で使う
IDEMPOTENCY_BASE = "daily-bonus"


def idempotency_key_for(day: date) -> str:
    """*day* の付与を表す冪等キー。同じ日からは必ず同じ値が出る。"""
    return IdempotencyKey(IDEMPOTENCY_BASE).for_step(day.isoformat()).value


@dataclass(frozen=True, kw_only=True)
class DueDays:
    """まだ渡していない日と、上限で切り捨てた日数。"""

    days: tuple[date, ...]
    #: 遡る上限を超えたため渡さない日の数。0 なら取りこぼしなし
    skipped: int


@dataclass(frozen=True, kw_only=True)
class DailyBonus:
    id: int
    ledger_id: int
    amount: PointAmount
    reason: TransactionReason
    #: 最初に渡す日（設定した日）。これより前へは遡らない
    starts_on: date
    #: 渡し終えた最後の日。まだ 1 日も渡していなければ ``None``
    granted_through: date | None

    def __post_init__(self) -> None:
        # 毎日減っていく設定は「ボーナス」ではない。消費は手で記録する
        if self.amount.value <= 0:
            raise ValueError("Daily bonus must add points")

    def due_days(self, *, today: date, limit: int) -> DueDays:
        """*today* までに渡すべき日を、古い順に返す。

        ``limit`` を超える場合は **新しい方から** ``limit`` 日だけを渡す。久しぶりに
        動かしたときに古い日から埋めると、上限に当たるたびに何日も前の行が増え続け、
        今日のボーナスが着くまでに何周もかかる。
        """
        first = self.granted_through + timedelta(days=1) if self.granted_through else self.starts_on
        if today < first:
            return DueDays(days=(), skipped=0)
        total = (today - first).days + 1
        skipped = max(0, total - max(1, limit))
        start = first + timedelta(days=skipped)
        return DueDays(
            days=tuple(start + timedelta(days=offset) for offset in range(total - skipped)),
            skipped=skipped,
        )


__all__ = ["IDEMPOTENCY_BASE", "DailyBonus", "DueDays", "idempotency_key_for"]
