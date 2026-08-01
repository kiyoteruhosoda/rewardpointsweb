"""家族の中での呼び名。

アカウントの表示名とは別に持つ。同じ人でも家族ごとに呼ばれ方は変わりうるし、
まだアカウントを持たない子どもにも呼び名は必要になる（ADR-0010）。
"""

from __future__ import annotations

from dataclasses import dataclass

MAX_LENGTH = 100


@dataclass(frozen=True)
class DisplayName:
    value: str

    def __post_init__(self) -> None:
        if not self.value.strip():
            raise ValueError("Display name cannot be empty")
        if len(self.value) > MAX_LENGTH:
            raise ValueError(f"Display name cannot exceed {MAX_LENGTH} characters")


__all__ = ["MAX_LENGTH", "DisplayName"]
