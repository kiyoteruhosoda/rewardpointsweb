"""Reason for a grant or spend (free text)."""

from __future__ import annotations

from dataclasses import dataclass

MAX_LENGTH = 255


@dataclass(frozen=True)
class TransactionReason:
    value: str

    def __post_init__(self) -> None:
        if not self.value.strip():
            raise ValueError("Transaction reason cannot be empty")
        if len(self.value) > MAX_LENGTH:
            raise ValueError(f"Transaction reason cannot exceed {MAX_LENGTH} characters")


__all__ = ["MAX_LENGTH", "TransactionReason"]
