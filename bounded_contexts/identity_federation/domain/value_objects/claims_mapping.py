"""Mapping of ID token (and UserInfo) claims -> :class:`FederatedUser`.

Claim names differ per IdP, so they are configurable (``OIDC_*_CLAIM``). This holds only
"which name to read what from" and does no I/O (it is a pure transformation, so it can be
checked with unit tests).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from bounded_contexts.identity_federation.domain.exceptions import (
    InvalidIdTokenError,
)
from bounded_contexts.identity_federation.domain.value_objects.federated_user import (
    FederatedUser,
)

# Fallbacks when the display name is missing from the mapped claim. Absorbs IdP implementation differences.
_DISPLAY_NAME_FALLBACK_CLAIMS = ("name", "preferred_username", "nickname")


@dataclass(frozen=True)
class ClaimsMapping:
    email_claim: str = "email"
    display_name_claim: str = "name"

    def apply(self, claims: Mapping[str, Any]) -> FederatedUser:
        """Map claims to user information.

        Anything without ``sub`` is not a valid ID token.

        ⚠ **Pass even without an email address** (ADR-0038). The link key is ``sub``, so
        someone already linked can sign in without an email. **Refuse only where its absence matters**
        -- which is only when looking for an existing user on the first sign-in.
        """
        subject = _text(claims.get("sub"))
        if not subject:
            raise InvalidIdTokenError
        email = _text(claims.get(self.email_claim))
        return FederatedUser(
            subject=subject,
            email=email.lower() if email else None,
            display_name=self._display_name(claims, email, subject),
            email_verified=claims.get("email_verified") is True,
            # ⚠ **The claim name is not configurable.** It is a standard OIDC Core claim and the source of
            #   ``username`` when creating an account (ADR-0041). If it could be remapped, the identifier of
            #   created accounts would change with a single setting.
            preferred_username=_text(claims.get("preferred_username")) or None,
        )

    def _display_name(self, claims: Mapping[str, Any], email: str, subject: str) -> str:
        """Display name. If the mapped claim is empty, an alternate claim; failing that, the local part of the email.

        ⚠ **If there is no email either, use ``sub``.** It is hard to read, but **better than creating a user
        with an empty name** -- it can be fixed on screen later.
        """
        for claim in (self.display_name_claim, *_DISPLAY_NAME_FALLBACK_CLAIMS):
            value = _text(claims.get(claim))
            if value:
                return value
        return email.partition("@")[0] if email else subject


def _text(value: object) -> str:
    return value.strip() if isinstance(value, str) else ""


__all__ = ["ClaimsMapping"]
