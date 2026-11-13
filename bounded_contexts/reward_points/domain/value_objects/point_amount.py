"""Amount moved on a ledger in one entry (signed).

Additions are positive, spending is negative. Zero is not allowed since it means nothing
on a ledger (the domain enforces the same invariant as ``CHECK (amount <> 0)``; ADR-0010).
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
        """The opposite-sign amount used for a reversal."""
        return PointAmount(-self.value)


__all__ = ["MAX_MAGNITUDE", "PointAmount"]
