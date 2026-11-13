"""Settings for one external IdP (OpenID Provider) to federate with.

This app has exactly one IdP, and its values are built from settings (``OIDC_*`` in ``settings``)
(ADR-0029). This receives the built values and decides only "is this usable" and
"which scopes go into the authorization request".
"""

from __future__ import annotations

from dataclasses import dataclass

from bounded_contexts.identity_federation.domain.exceptions import (
    SsoNotConfiguredError,
)
from bounded_contexts.identity_federation.domain.value_objects.client_credential import (
    ClientCredential,
)

# OpenID Connect does not return an ID token without the ``openid`` scope. Always request it,
# even if it is missing from the settings.
REQUIRED_SCOPE = "openid"


@dataclass(frozen=True)
class IdentityProvider:
    display_name: str
    issuer: str
    client_id: str
    credential: ClientCredential
    redirect_uri: str
    scopes: tuple[str, ...] = ()

    @property
    def is_usable(self) -> bool:
        """Whether an authorization request can be started (endpoint and credentials are in place).

        Whether the credentials are complete differs per method, so it is left to
        :class:`ClientCredential`.
        """
        return bool(self.issuer and self.client_id and self.redirect_uri and self.credential.is_complete)

    @property
    def scope_parameter(self) -> str:
        """Value of the ``scope`` parameter. ``openid`` always comes first; duplicates are collapsed."""
        requested = (REQUIRED_SCOPE, *(scope for scope in self.scopes if scope))
        return " ".join(dict.fromkeys(requested))


def require_usable(provider: IdentityProvider | None) -> IdentityProvider:
    """Return it after checking it is usable. If not, :class:`SsoNotConfiguredError`.

    The caller does not need to distinguish "disabled" from "settings not filled in"
    (both lead to the same single result: SSO cannot start).
    """
    if provider is None or not provider.is_usable:
        raise SsoNotConfiguredError
    return provider


__all__ = ["REQUIRED_SCOPE", "IdentityProvider", "require_usable"]
