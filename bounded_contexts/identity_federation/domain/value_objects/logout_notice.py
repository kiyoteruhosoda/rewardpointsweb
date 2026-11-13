"""A "stop this session" from the IdP (OpenID Connect Back-Channel Logout 1.0).

Checking the ``logout_token``'s **signature, issuer, audience and expiry** is the Infrastructure layer's job
(it is a JWT matter). This looks at **the other four**, all of which the spec explicitly
requires (§2.6).

- ``events`` contains the back-channel logout event
  -- a JWT without it is not a "logout notice"
- ``nonce`` is **absent** -- one that has it is an ID token, and
  accepting it would let **anyone cause a logout just by throwing back an ID token they hold**
- either ``sub`` or ``sid`` is present -- without both, there is no telling whom to stop
- ``jti`` is present -- it is the key for rejecting resends (ADR-0024 uses the same ``jti`` on resend)
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from bounded_contexts.identity_federation.domain.exceptions import (
    InvalidLogoutTokenError,
)
from bounded_contexts.identity_federation.domain.value_objects.federated_session import (
    FederatedSession,
)

#: Event name for back-channel logout (OpenID Connect Back-Channel Logout 1.0 §2.4).
LOGOUT_EVENT = "http://schemas.openid.net/event/backchannel-logout"


@dataclass(frozen=True)
class LogoutNotice:
    """A notice that passed verification. ``jti`` is the delivery identity and does not change on resend."""

    jti: str
    session: FederatedSession

    @classmethod
    def from_claims(cls, claims: Mapping[str, Any], *, issuer: str) -> LogoutNotice:
        """Build from verified claims. Anything invalid raises an exception."""
        _ensure_logout_event(claims)
        _ensure_not_an_id_token(claims)
        jti = _text(claims.get("jti"))
        if not jti:
            raise InvalidLogoutTokenError
        subject = _text(claims.get("sub"))
        session_id = _text(claims.get("sid"))
        if not subject and not session_id:
            raise InvalidLogoutTokenError
        return cls(
            jti=jti,
            session=FederatedSession(issuer=issuer, subject=subject, session_id=session_id or None),
        )


def _ensure_logout_event(claims: Mapping[str, Any]) -> None:
    events = claims.get("events")
    if not isinstance(events, Mapping) or LOGOUT_EVENT not in events:
        raise InvalidLogoutTokenError


def _ensure_not_an_id_token(claims: Mapping[str, Any]) -> None:
    """Reject anything with a ``nonce`` (the spec says MUST NOT).

    An ID token and a logout token share the signing key, issuer and audience, so **this one point**
    alone tells them apart. Dropping it would let anyone take down another person's session just by
    sending back a legitimately received ID token.
    """
    if "nonce" in claims:
        raise InvalidLogoutTokenError


def _text(value: object) -> str:
    return value.strip() if isinstance(value, str) else ""


__all__ = ["LOGOUT_EVENT", "LogoutNotice"]
