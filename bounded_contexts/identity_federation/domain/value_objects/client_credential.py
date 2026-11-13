"""Credentials used to identify ourselves to the token endpoint (ADR-0029).

There are two methods. Both prove "this is the client itself" and are
used **only when redeeming the authorization code**.

``client_secret_basic``
    Send a shared secret via Basic authentication. The settings hold the secret itself.
``private_key_jwt``
    Send an assertion signed with a private key on the host (RFC 7523). The settings hold only
    **where the key is**; the secret itself appears neither in app settings nor in deployment
    variables.
"""

from __future__ import annotations

from dataclasses import dataclass

CLIENT_SECRET_BASIC = "client_secret_basic"
PRIVATE_KEY_JWT = "private_key_jwt"

#: Methods accepted as settings. Any value not listed here is treated as "misconfigured".
CLIENT_AUTH_METHODS = (CLIENT_SECRET_BASIC, PRIVATE_KEY_JWT)


@dataclass(frozen=True)
class ClientCredential:
    """The method and the material it needs.

    The material differs per method, so **whether it is complete also depends on the method**.
    Values not held here (empty strings) mean "not configured".
    """

    method: str
    secret: str = ""
    private_key_file: str = ""
    private_key_kid: str = ""

    @property
    def is_complete(self) -> bool:
        """Whether there is enough material to identify ourselves with the method.

        Do not let a misspelling fall back to the default method. Silently treating a value like
        ``private-key-jwt`` as ``client_secret_basic`` would just get an unexplained
        ``invalid_client`` back from the IdP. Unknown methods are treated as misconfigured.
        """
        if self.method == PRIVATE_KEY_JWT:
            return bool(self.private_key_file)
        if self.method == CLIENT_SECRET_BASIC:
            return bool(self.secret)
        return False

    @property
    def uses_private_key(self) -> bool:
        return self.method == PRIVATE_KEY_JWT


__all__ = [
    "CLIENT_AUTH_METHODS",
    "CLIENT_SECRET_BASIC",
    "PRIVATE_KEY_JWT",
    "ClientCredential",
]
