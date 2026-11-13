"""Login identifier (``users.username``).

Separating the identifier from the email address made it "a string the app decides"
(ADR-0011). Existing accounts were migrated with their email address, so values
containing ``@`` and ``.`` must still be accepted.

Case-insensitive. Being case-sensitive would list ``Taro`` and ``taro`` as separate
accounts and cause mix-ups within a household. Normalization (lowercasing) happens
only here, once, and both saving and lookup use this value.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

MIN_LENGTH = 3
MAX_LENGTH = 255

# Children type this by hand, so whitespace and confusing symbols are not allowed.
_ALLOWED = re.compile(r"^[a-z0-9._@+-]+$")


@dataclass(frozen=True)
class Username:
    value: str

    def __post_init__(self) -> None:
        normalized = self.value.strip().lower()
        object.__setattr__(self, "value", normalized)
        if len(normalized) < MIN_LENGTH:
            raise ValueError(f"Username must be at least {MIN_LENGTH} characters")
        if len(normalized) > MAX_LENGTH:
            raise ValueError(f"Username cannot exceed {MAX_LENGTH} characters")
        if not _ALLOWED.match(normalized):
            raise ValueError("Username may only contain letters, digits and . _ - + @")


def normalize_username(value: str) -> str:
    """Apply the same normalization for lookup (invalid values are rejected here)."""
    return Username(value).value


__all__ = ["MAX_LENGTH", "MIN_LENGTH", "Username", "normalize_username"]
