"""TOTP secret (shared key of a time-based one-time password).

One per user. Two-factor authentication becomes "enabled" only once ``confirmed_at``
is set. Enabling it mid-enrollment (just showing the QR code) would keep users
whose registration in the authenticator app failed from logging in, so it stays
unconfirmed until the confirmation code is verified.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class TotpSecret:
    user_id: int
    secret: str
    confirmed_at: datetime | None = None

    @property
    def is_confirmed(self) -> bool:
        return self.confirmed_at is not None


__all__ = ["TotpSecret"]
