"""One pairing (from the display device showing a confirmation code until it receives its credential).

There are 4 states, derived from the columns (there is no state column).

============ ============================================
pending      Neither approved nor claimed, and not expired
approved     ``approved_account_id`` is set, not yet claimed
claimed      ``claimed_at`` is set. Can no longer be used
expired      Past ``expires_at`` (cannot be claimed even if approved)
============ ============================================
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, kw_only=True)
class DisplayPairing:
    id: int
    expires_at: datetime
    created_at: datetime
    #: Display account created on approval. ``None`` before approval
    approved_account_id: int | None = None
    claimed_at: datetime | None = None

    def is_expired(self, now: datetime) -> bool:
        return now >= self.expires_at

    @property
    def is_claimed(self) -> bool:
        return self.claimed_at is not None

    @property
    def is_approved(self) -> bool:
        return self.approved_account_id is not None

    def can_be_approved(self, now: datetime) -> bool:
        return not self.is_expired(now) and not self.is_approved and not self.is_claimed


__all__ = ["DisplayPairing"]
