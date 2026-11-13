"""Family rules (a note of the agreements the family made).

Holds the family's agreements in plain human words, such as "90 points on a
test earns 100 pt" or "1 hour of games = 50 pt". The machine does not
interpret them; grants are recorded by a parent by hand or by the daily bonus
(ADR-0024). This exists only so that everyone in the family can read **what
was agreed** in the same wording.

Having no rules is represented as **not set** (``None``), not as an empty
string. When this value object exists, it always has content.
"""

from __future__ import annotations

from dataclasses import dataclass

#: Upper length limit that can still be read on screen; about 20-30 bullet lines
MAX_LENGTH = 2000


@dataclass(frozen=True)
class FamilyRules:
    value: str

    def __post_init__(self) -> None:
        if not self.value.strip():
            raise ValueError("Family rules cannot be empty")
        if len(self.value) > MAX_LENGTH:
            raise ValueError(f"Family rules cannot exceed {MAX_LENGTH} characters")


__all__ = ["MAX_LENGTH", "FamilyRules"]
