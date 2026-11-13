"""A user asserted by the IdP (result of mapping the claims).

``subject`` is an immutable identifier within the IdP, and account links are held by it.
Email addresses can change, so they are **not used as the link key** (only as a hint for finding an
existing user on the first sign-in; ADR-0029).

⚠ **Since it is not a key, it can be absent** (ADR-0038). Some IdPs do not provide it
-- **rejecting it in that case was a leftover from when it was the key.**
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FederatedUser:
    subject: str
    #: ⚠ **Optional** (ADR-0038). The link key is ``subject``, so someone already
    #: linked can sign in without an email address. It is needed only
    #: **when looking for an existing user on the first sign-in**.
    email: str | None
    display_name: str
    email_verified: bool = False
    #: Login identifier at the IdP (``preferred_username``). Used as the source of this app's
    #: ``username`` when creating an account for a first-time user (ADR-0041). ⚠ **Optional** -- the IdP
    #: may not provide it (when the ``profile`` scope is not requested), in which case no account can be created.
    preferred_username: str | None = None

    @property
    def email_domain(self) -> str:
        _, _, domain = (self.email or "").rpartition("@")
        return domain.lower()


__all__ = ["FederatedUser"]
