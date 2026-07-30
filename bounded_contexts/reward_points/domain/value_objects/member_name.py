"""メンバー名。"""

from __future__ import annotations

from dataclasses import dataclass

MAX_LENGTH = 100


@dataclass(frozen=True)
class MemberName:
    value: str

    def __post_init__(self) -> None:
        if not self.value.strip():
            raise ValueError("Member name cannot be empty")
        if len(self.value) > MAX_LENGTH:
            raise ValueError(f"Member name cannot exceed {MAX_LENGTH} characters")


__all__ = ["MAX_LENGTH", "MemberName"]
