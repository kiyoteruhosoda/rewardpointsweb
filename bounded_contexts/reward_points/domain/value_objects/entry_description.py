"""履歴 1 件の説明（加算なら理由、消費なら用途）。"""

from __future__ import annotations

from dataclasses import dataclass

MAX_LENGTH = 255


@dataclass(frozen=True)
class EntryDescription:
    value: str

    def __post_init__(self) -> None:
        if not self.value.strip():
            raise ValueError("Entry description cannot be empty")
        if len(self.value) > MAX_LENGTH:
            raise ValueError(f"Entry description cannot exceed {MAX_LENGTH} characters")


__all__ = ["MAX_LENGTH", "EntryDescription"]
