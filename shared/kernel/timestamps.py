"""時刻の取り扱い。

保存・比較する時刻は常に UTC で、DB へは naive datetime として書く
（CLAUDE.md「ログ」参照）。tz 情報の有無が混ざると比較が例外になるため、
生成口をここ 1 か所に集約する。
"""

from __future__ import annotations

from datetime import UTC, datetime


def utcnow() -> datetime:
    """現在時刻を UTC の naive datetime で返す。"""
    return datetime.now(UTC).replace(tzinfo=None)


def as_naive_utc(moment: datetime) -> datetime:
    """外から受け取った時刻を、保存できる形（UTC の naive datetime）へ揃える。

    API のリクエストにはタイムゾーン付きの時刻（``2026-07-30T09:00:00+09:00``）が
    来る。tz 付きのまま保存すると、tz 無しで保存された既存行との比較で例外になる。
    tz が無い時刻は、すでに UTC として渡されたものとして扱う。
    """
    if moment.tzinfo is None:
        return moment
    return moment.astimezone(UTC).replace(tzinfo=None)


__all__ = ["as_naive_utc", "utcnow"]
