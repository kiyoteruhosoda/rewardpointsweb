"""Fetching and caching OpenID Provider metadata (endpoints and signing keys).

- **Endpoints are looked up via discovery** (``<issuer>/.well-known/openid-configuration``).
  Configuring URLs one by one could not follow IdP-side changes and would add settings.
- **Signing keys are fetched from JWKS**. Keys rotate, so they are also held in a form that can be
  refetched (``PyJWKClient`` caches and refetches internally).
- **Outgoing requests identify themselves** (``USER_AGENT``). With the default, the layer in front of the IdP
  may drop them (see below).

Fetching both on every login would add two round trips to the IdP, so a short-TTL cache sits
in between. The cache is per process, so stale values last only for the TTL.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Any

import httpx
import jwt

from bounded_contexts.identity_federation.domain.exceptions import (
    IdentityProviderUnavailableError,
)

# Signature algorithms accepted for ID tokens. **Symmetric keys (HS*) and ``none`` are excluded**
# -- HS* uses the client secret as the key, so parties other than the IdP could make signatures.
ALLOWED_SIGNING_ALGORITHMS: tuple[str, ...] = (
    "RS256",
    "RS384",
    "RS512",
    "PS256",
    "PS384",
    "PS512",
    "ES256",
    "ES384",
    "ES512",
)

_DISCOVERY_PATH = "/.well-known/openid-configuration"
_CACHE_TTL_SECONDS = 300.0

# The name outgoing requests to the IdP identify with. **Do not leave it to the default UA.**
# Only JWKS is fetched by PyJWT (``PyJWKClient``) through its internal urllib, which by default
# identifies as ``Python-urllib/3.x``. A CDN/WAF in front of the IdP may drop this UA,
# so discovery and token exchange pass while only ID token verification fails.
USER_AGENT = "rewardpointsweb"


@dataclass(frozen=True)
class ProviderMetadata:
    issuer: str
    authorization_endpoint: str
    token_endpoint: str
    jwks_uri: str
    userinfo_endpoint: str = ""
    signing_algorithms: tuple[str, ...] = ()
    token_auth_methods: tuple[str, ...] = ()

    @classmethod
    def of(cls, document: dict[str, Any]) -> ProviderMetadata:
        """Extract only the needed items from the discovery document.

        A response missing any of authorization, token or JWKS is not a valid OpenID Provider
        (an HTML response caused by a mistyped IdP URL also fails here).
        """
        metadata = cls(
            issuer=_text(document.get("issuer")),
            authorization_endpoint=_text(document.get("authorization_endpoint")),
            token_endpoint=_text(document.get("token_endpoint")),
            jwks_uri=_text(document.get("jwks_uri")),
            userinfo_endpoint=_text(document.get("userinfo_endpoint")),
            signing_algorithms=_supported_algorithms(document.get("id_token_signing_alg_values_supported")),
            token_auth_methods=tuple(_texts(document.get("token_endpoint_auth_methods_supported"))),
        )
        if not (metadata.authorization_endpoint and metadata.token_endpoint and metadata.jwks_uri):
            raise IdentityProviderUnavailableError
        return metadata


class OidcMetadataCache:
    """TTL cache of the discovery document and the JWKS client (in-process)."""

    def __init__(self, *, timeout_seconds: float = 10.0) -> None:
        self._timeout = timeout_seconds
        self._lock = threading.Lock()
        self._documents: dict[str, tuple[float, ProviderMetadata]] = {}
        self._jwks: dict[str, jwt.PyJWKClient] = {}

    def metadata(self, issuer: str) -> ProviderMetadata:
        with self._lock:
            cached = self._documents.get(issuer)
            if cached is not None and cached[0] > time.monotonic():
                return cached[1]
        metadata = ProviderMetadata.of(self._fetch(f"{issuer.rstrip('/')}{_DISCOVERY_PATH}"))
        _require_same_issuer(metadata, issuer)
        with self._lock:
            self._documents[issuer] = (time.monotonic() + _CACHE_TTL_SECONDS, metadata)
        return metadata

    def signing_key(self, jwks_uri: str, id_token: str) -> Any:
        """Return the public key matching the ID token's ``kid``."""
        with self._lock:
            client = self._jwks.get(jwks_uri)
            if client is None:
                client = jwt.PyJWKClient(
                    jwks_uri,
                    cache_keys=True,
                    headers={"User-Agent": USER_AGENT},
                    timeout=self._timeout,
                )
                self._jwks[jwks_uri] = client
        try:
            return client.get_signing_key_from_jwt(id_token).key
        except jwt.PyJWKClientError as error:
            raise IdentityProviderUnavailableError from error

    def _fetch(self, url: str) -> dict[str, Any]:
        try:
            response = httpx.get(
                url,
                headers={"User-Agent": USER_AGENT},
                timeout=self._timeout,
                # ⚠ Do not follow redirects (ADR-0056). The issuer check only applies to the first URL.
                follow_redirects=False,
            )
            response.raise_for_status()
            document = response.json()
        except (httpx.HTTPError, ValueError) as error:
            raise IdentityProviderUnavailableError from error
        if not isinstance(document, dict):
            raise IdentityProviderUnavailableError
        return document


def _require_same_issuer(metadata: ProviderMetadata, issuer: str) -> None:
    """Check that the ``issuer`` claimed by the discovery document equals where it was fetched from.

    OpenID Connect Discovery requires them to match. Fetching follows redirects
    (``follow_redirects``), so without the check, being handed another issuer's document would
    make us accept ID tokens signed by that issuer as is.
    Only a trailing ``/`` difference is allowed (the settings side strips it).
    """
    if metadata.issuer.rstrip("/") != issuer.rstrip("/"):
        raise IdentityProviderUnavailableError


def _text(value: object) -> str:
    return value.strip() if isinstance(value, str) else ""


def _texts(value: object) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    return tuple(_text(item) for item in value if _text(item))


def _supported_algorithms(value: object) -> tuple[str, ...]:
    """Of the algorithms the IdP advertises, keep only those we accept.

    If none are advertised, use ``RS256``, which OpenID Connect requires.
    """
    advertised = _texts(value)
    allowed = tuple(algorithm for algorithm in advertised if algorithm in ALLOWED_SIGNING_ALGORITHMS)
    return allowed or ("RS256",)


__all__ = ["ALLOWED_SIGNING_ALGORITHMS", "OidcMetadataCache", "ProviderMetadata"]
