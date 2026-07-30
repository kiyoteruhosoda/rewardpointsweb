"""メンバーへ触れられる範囲。

閲覧（``VIEW``）と変更（``MANAGE``）の 2 段階だけを持つ。「メンバー本人は自分の
ポイントを見られるが変更はできない」という要件が、この 2 段階で表現できる。
"""

from __future__ import annotations

from collections.abc import Iterable
from enum import Enum


class MemberAccessLevel(Enum):
    VIEW = "view"
    MANAGE = "manage"

    @property
    def can_manage(self) -> bool:
        return self is MemberAccessLevel.MANAGE

    @classmethod
    def strongest(cls, levels: Iterable[MemberAccessLevel]) -> MemberAccessLevel | None:
        """複数の経路（所有・共有・本人）で到達できるときは強い方を採る。

        経路が 1 つも無ければ ``None``（アクセス不可）。
        """
        found = list(levels)
        if not found:
            return None
        return cls.MANAGE if any(level.can_manage for level in found) else cls.VIEW


__all__ = ["MemberAccessLevel"]
