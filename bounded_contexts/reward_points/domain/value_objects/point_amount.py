"""ポイント数。

加算・消費のどちらも「何ポイント動かすか」は正の整数で表す。符号は履歴の種別
（加算 / 消費）が持つ責務であり、量そのものには持たせない。0 や負の値を許すと
「加算したのに残高が減る」履歴を作れてしまう。
"""

from __future__ import annotations

from dataclasses import dataclass

MAX_VALUE = 1_000_000


@dataclass(frozen=True)
class PointAmount:
    value: int

    def __post_init__(self) -> None:
        if self.value <= 0:
            raise ValueError("Point amount must be positive")
        if self.value > MAX_VALUE:
            raise ValueError(f"Point amount cannot exceed {MAX_VALUE}")


__all__ = ["MAX_VALUE", "PointAmount"]
