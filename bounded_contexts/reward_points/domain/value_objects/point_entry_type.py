"""履歴の種別。

DB へは値（文字列）を保存するが、ネイティブ ENUM 型は使わない
（CLAUDE.md「DB モデリング」）。ここは Python 側の許可値の集中管理。
"""

from __future__ import annotations

from enum import Enum


class PointEntryType(Enum):
    ADDITION = "addition"
    CONSUMPTION = "consumption"


__all__ = ["PointEntryType"]
