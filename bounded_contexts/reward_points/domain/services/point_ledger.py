"""あるメンバーのポイント台帳（履歴とそこから決まる残高）。

残高は履歴の合計として **その場で計算する**。残高を別に持って加算・消費のたびに
書き換えると、履歴を消したときに合わなくなる（履歴が唯一の事実で、残高は導出値）。

加算・消費の符号は各履歴の ``signed_points`` が知っているので、ここに種別の分岐は
現れない。新しい種別が増えても合計の式は変わらない。
"""

from __future__ import annotations

from collections.abc import Sequence

from bounded_contexts.reward_points.domain.entities.point_entry import PointEntry
from bounded_contexts.reward_points.domain.value_objects.point_balance import PointBalance


class PointLedger:
    def __init__(self, entries: Sequence[PointEntry]) -> None:
        self._entries = tuple(entries)

    @property
    def entries(self) -> tuple[PointEntry, ...]:
        """渡された順のまま返す（並び順の決定はリポジトリの責務）。"""
        return self._entries

    @property
    def balance(self) -> PointBalance:
        return PointBalance(sum(entry.signed_points for entry in self._entries))


__all__ = ["PointLedger"]
