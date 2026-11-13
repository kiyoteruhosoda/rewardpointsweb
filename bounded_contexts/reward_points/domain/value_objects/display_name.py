"""The name a member goes by within a family.

Kept separate from the account's display name. The same person may be called
differently in each family, and children without an account still need a name (ADR-0010).
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
