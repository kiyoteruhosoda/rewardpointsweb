"""1 日の区切り。

保存・比較する時刻は常に UTC（``shared.kernel.timestamps``）だが、「毎日」を
UTC の 0 時で切ると、日本の家族には毎朝 9 時が日付の変わり目になる。暮らしの
側の 1 日と台帳の上の 1 日を合わせるため、区切りに使う地域をここへ 1 つ持たせる。

受け渡しする時刻は入口も出口も **UTC の naive datetime** で、地域を意識するのは
この中だけに閉じる。呼び出し側が tz 付きと naive を混ぜると、比較のたびに例外に
なる（ADR-0024）。
"""

from __future__ import annotations

from datetime import UTC, date, datetime, time, tzinfo


class DayBoundary:
    def __init__(self, time_zone: tzinfo) -> None:
        self._time_zone = time_zone

    def day_of(self, moment: datetime) -> date:
        """*moment*（UTC の naive datetime）が、この区切りで何日にあたるか。"""
        return moment.replace(tzinfo=UTC).astimezone(self._time_zone).date()

    def starts_at(self, day: date) -> datetime:
        """*day* の始まり（UTC の naive datetime）。

        その日の出来事として台帳へ並ぶよう、付与の ``occurred_at`` に使う。実際に
        書き込まれる時刻（``created_at``）とは別物で、停止中に跨いだ日をまとめて
        追いついたときも、履歴はそれぞれの日付の位置に収まる。
        """
        return datetime.combine(day, time.min, tzinfo=self._time_zone).astimezone(UTC).replace(tzinfo=None)


__all__ = ["DayBoundary"]
