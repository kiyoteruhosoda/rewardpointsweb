"""Timing rules for pairings and device credentials (ADR-0047).

These are not settings: they are all part of how display devices are built, not values
tuned in operation.
"""

from __future__ import annotations

from datetime import timedelta

#: Lifetime of a confirmation code. When it expires, the device shows a new code
PAIRING_TTL = timedelta(minutes=10)
#: Interval at which the device polls for its credential (``interval`` in RFC 8628)
POLL_INTERVAL_SECONDS = 5
#: Expired pairings are deleted after this long (so they do not pile up)
PAIRING_RETENTION = timedelta(days=1)
#: A credential unused for longer than this is revoked. A device left on uses it every 5 minutes
CREDENTIAL_IDLE_LIMIT = timedelta(days=90)


__all__ = ["CREDENTIAL_IDLE_LIMIT", "PAIRING_RETENTION", "PAIRING_TTL", "POLL_INTERVAL_SECONDS"]
