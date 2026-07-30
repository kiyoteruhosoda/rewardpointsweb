"""ポイント残高。"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PointBalance:
    value: int


__all__ = ["PointBalance"]
