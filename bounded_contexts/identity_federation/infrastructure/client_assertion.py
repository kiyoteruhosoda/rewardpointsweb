"""Client authentication assertion for ``private_key_jwt`` (RFC 7523 / OIDC Core 9).

The private key is in a file on the host and **is read only when signing**. App settings hold
only its location and ``kid``; the key itself appears neither in deployment variables nor in the DB
(ADR-0029).

Verification on our own idp side:

- ``client_assertion_type`` must be ``urn:ietf:params:oauth:client-assertion-type:jwt-bearer``
- ``iss`` and ``sub`` are both **the client_id itself** (RFC 7523 section 3)
- ``aud`` is either ``<issuer>/token`` or ``<issuer>``
- **``jti`` is required**. The IdP records it to prevent replay
- ``exp`` is **within 5 minutes from now**. Beyond that, ``assertion_lifetime_too_long``
- The verification algorithm is determined by **the registered key's type**. The header ``alg`` is not trusted
  (to prevent alg confusion attacks)
"""

from __future__ import annotations

import logging
import secrets
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path

import jwt

from bounded_contexts.identity_federation.domain.exceptions import (
    SsoNotConfiguredError,
)
from bounded_contexts.identity_federation.domain.value_objects.client_credential import (
    ClientCredential,
)
from shared.kernel.timestamps import utcnow

logger = logging.getLogger(__name__)

ASSERTION_TYPE = "urn:ietf:params:oauth:client-assertion-type:jwt-bearer"

# idp's limit is 5 minutes. It is kept short because longer gains nothing and only widens the
# replay window and how long the IdP has to keep the jti.
_LIFETIME_SECONDS = 60

_ALGORITHM = "RS256"


@dataclass(frozen=True)
class ClientAssertionRequest:
    """Input for building one assertion.

    ``client_id`` and ``audience`` are both ``str``, so passing them positionally lets a mix-up
    slip past type checking. A mix-up yields ``invalid_client`` at the IdP, but **which one
    caused it is not reported**, so they are carried together from the entry point.
    """

    client_id: str
    audience: str
    credential: ClientCredential


def build_client_assertion(request: ClientAssertionRequest) -> str:
    """Build the signed assertion presented to the token endpoint."""
    now = utcnow()
    headers = {"typ": "JWT"}
    kid = request.credential.private_key_kid
    if kid:
        # With multiple keys registered, the IdP cannot decide which to verify with unless kid is given.
        headers["kid"] = kid
    return jwt.encode(
        {
            "iss": request.client_id,
            "sub": request.client_id,
            "aud": request.audience,
            # A different value every time. The IdP records it to prevent replay.
            "jti": secrets.token_urlsafe(32),
            "iat": now,
            "exp": now + timedelta(seconds=_LIFETIME_SECONDS),
        },
        read_private_key(request.credential),
        algorithm=_ALGORITHM,
        headers=headers,
    )


def read_private_key(credential: ClientCredential) -> str:
    """Read the signing key (PEM). If unreadable, :class:`SsoNotConfiguredError`.

    **Whether it is readable is only known when it is used.** Even with wrong permissions,
    startup and configuration checks pass, and it fails only at the moment a user returns from the IdP.
    So it is also checked once at startup and logged (``presentation/startup_check.py``).
    """
    path = credential.private_key_file
    if not path:
        raise SsoNotConfiguredError
    try:
        return Path(path).read_text(encoding="utf-8")
    except OSError as error:
        # With 0400 root the container's runtime user cannot read it. The directory itself
        # also needs traverse permission (``/srv/secrets/oidc`` is 0710).
        logger.error("sso_private_key_unreadable", extra={"reason": type(error).__name__})
        raise SsoNotConfiguredError from error


__all__ = [
    "ASSERTION_TYPE",
    "ClientAssertionRequest",
    "build_client_assertion",
    "read_private_key",
]
