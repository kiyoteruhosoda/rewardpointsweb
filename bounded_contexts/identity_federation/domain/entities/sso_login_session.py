"""Record of an authorization request (from sending the browser to the IdP until it returns).

``state`` checks "is the returned response for a request we issued", ``nonce``
checks "is the received ID token a response to our request", and
``code_verifier`` is PKCE (proof that prevents use of an intercepted authorization code).
None of them can be checked unless the issuing side remembers them.

``binding_hash`` checks "did **the browser that issued this request** come back".
All records share one table, so anyone who merely knows ``state`` could complete the
return. If an attacker makes a victim open the URL of an authorization request the attacker
started, the victim ends up signed in **as the attacker** (login CSRF). Matching against the
passphrase put into a cookie when sending the browser out stops that. The passphrase itself is not stored.

Gunicorn runs multiple workers, so the process that sent the browser out and the one it returns to differ.
Keep this in the DB rather than process memory (same reason as passkey challenges).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class SsoLoginSession:
    state: str
    nonce: str
    code_verifier: str
    redirect_to: str
    expires_at: datetime
    binding_hash: str = ""
    #: The user who started a linking round trip (ADR-0036). ``None`` for a login round trip.
    #:
    #: ⚠ **This one field serves as both "what the round trip is for" and "whose it is".** If set,
    #:   it is linking; if not, it is a login. Holding the purpose separately would make the
    #:   impossible state "a linking round trip that belongs to nobody known" representable.
    #:
    #: ⚠ **The session at return time cannot be used instead.** If the user signs out mid-round-trip
    #:   and signs in as another user, the link target would be swapped to that person.
    link_user_id: int | None = None
    #: A round trip tried without showing a screen (``prompt=none``; ADR-0052).
    #:
    #: ⚠ **Exists to decide what to do when the return says "not signed in".** It was only a try, so it is
    #:   not a failure: go back to the login screen without showing an error.
    silent: bool = False
    #: A round trip that continues an expired login (inside a hidden frame; ADR-0058). Always ``silent`` too.
    #:
    #: ⚠ **Exists to decide where the return goes.** Being inside a frame, it goes to the result page,
    #:   not an SPA screen.
    renewal: bool = False

    def is_expired(self, now: datetime) -> bool:
        return now >= self.expires_at

    def belongs_to(self, binding_hash: str) -> bool:
        """Whether this is the passphrase held by the browser that was sent out.

        Matching is done hash to hash (the raw value is not stored).
        """
        return bool(binding_hash) and binding_hash == self.binding_hash

    def declined_silently(self, binding_hash: str) -> bool:
        """Whether this is a return to the sending browser of a round trip tried without a screen (ADR-0052)."""
        return self.silent and self.belongs_to(binding_hash)

    def renewal_from(self, binding_hash: str) -> bool:
        """Whether this is a return to the sending browser of a round trip continuing an expired login (ADR-0058)."""
        return self.renewal and self.belongs_to(binding_hash)

    def started_by(self, user_id: int) -> bool:
        """Whether the linking round trip was started by the user who is signed in now (ADR-0036)."""
        return self.link_user_id is not None and self.link_user_id == user_id


__all__ = ["SsoLoginSession"]
