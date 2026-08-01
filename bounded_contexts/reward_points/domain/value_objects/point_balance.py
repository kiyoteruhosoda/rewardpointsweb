"""ポイント残高。

マイナスを許容する（前借りの運用を認める。ADR-0010）。
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PointBalance:
    value: int

    @property
    def is_negative(self) -> bool:
        return self.value < 0


__all__ = ["PointBalance"]
