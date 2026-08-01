"""家族の名前。"""

from __future__ import annotations

from dataclasses import dataclass

MAX_LENGTH = 100


@dataclass(frozen=True)
class FamilyName:
    value: str

    def __post_init__(self) -> None:
        if not self.value.strip():
            raise ValueError("Family name cannot be empty")
        if len(self.value) > MAX_LENGTH:
            raise ValueError(f"Family name cannot exceed {MAX_LENGTH} characters")


__all__ = ["MAX_LENGTH", "FamilyName"]
