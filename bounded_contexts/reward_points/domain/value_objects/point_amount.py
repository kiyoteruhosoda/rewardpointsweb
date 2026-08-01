"""台帳へ 1 回で動かす量（符号付き）。

加算は正、消費は負で表す。0 は台帳に意味を持たないため許さない
（``CHECK (amount <> 0)`` と同じ不変条件をドメイン側でも守る。ADR-0010）。
"""

from __future__ import annotations

from dataclasses import dataclass

MAX_MAGNITUDE = 1_000_000


@dataclass(frozen=True)
class PointAmount:
    value: int

    def __post_init__(self) -> None:
        if self.value == 0:
            raise ValueError("Point amount must not be zero")
        if abs(self.value) > MAX_MAGNITUDE:
            raise ValueError(f"Point amount cannot exceed {MAX_MAGNITUDE} in magnitude")

    @property
    def negated(self) -> PointAmount:
        """打ち消しに使う逆符号の量。"""
        return PointAmount(-self.value)


__all__ = ["MAX_MAGNITUDE", "PointAmount"]
