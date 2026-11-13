"""Consistency of RP ID and origin (WebAuthn rules).

At ``navigator.credentials.create()`` the browser checks that "``rp.id`` equals the caller's
effective domain or is a registrable suffix of it", and throws ``SecurityError`` if not.
Even with mismatched settings, starting the registration still succeeds,
so unless the server rejects it first we end up with "saving worked, but it fails only on the
user's screen".

Along with validation, it **returns the normalized values**. Passing whitespace from the settings or a default port
(``:443``) to the authenticator as is causes another kind of mismatch: validation passes but it does not
match the origin the browser sends. Whoever builds the RP must always use the return value.

The decision is the domain rule itself (independent of framework and DB), so it lives here.
"""

from __future__ import annotations

import ipaddress
import re
from dataclasses import dataclass
from urllib.parse import SplitResult, urlsplit

from bounded_contexts.account_security.domain.exceptions import (
    InvalidWebAuthnOriginError,
    InvalidWebAuthnRelyingPartyIdError,
)

# WebAuthn only works in a secure context. http is allowed only for loopback, which browsers
# treat as secure as an exception (see OPERATIONS.md "Before using passkeys").
_HTTP_ALLOWED_HOSTS = frozenset({"localhost"})

# The origin the browser sends carries no default port (``https://example.com``, not
# ``https://example.com:443``). Unless we drop it too, verification fails.
_DEFAULT_PORTS = {"http": 80, "https": 443}

# Labels are alphanumerics and hyphens. Internationalized domains are kept in punycode (``xn--``) form.
_LABEL = re.compile(r"^[a-z0-9]([a-z0-9-]*[a-z0-9])?$")


@dataclass(frozen=True)
class RelyingPartyConfiguration:
    """Validated and normalized RP settings."""

    rp_id: str
    origin: str


def validate_relying_party_configuration(*, rp_id: str, origin: str) -> RelyingPartyConfiguration:
    """Check that ``rp_id`` can be used for the domain of ``origin``, and return them normalized.

    If they do not match, raise :class:`InvalidWebAuthnOriginError` or
    :class:`InvalidWebAuthnRelyingPartyIdError`.
    """
    canonical_origin, host = _canonical_origin(origin)
    identifier = _normalize_domain(rp_id)
    if not _is_domain(identifier) or not _is_registrable_suffix(identifier, host):
        raise InvalidWebAuthnRelyingPartyIdError
    return RelyingPartyConfiguration(rp_id=identifier, origin=canonical_origin)


def _canonical_origin(origin: str) -> tuple[str, str]:
    """Return the string normalized to ``scheme://host[:port]`` and its host name."""
    parts = urlsplit(origin.strip())
    _reject_non_origin(parts)
    host = _normalize_domain(parts.hostname or "")
    if not host:
        raise InvalidWebAuthnOriginError
    if parts.scheme == "http" and host not in _HTTP_ALLOWED_HOSTS:
        raise InvalidWebAuthnOriginError
    return f"{parts.scheme}://{host}{_explicit_port(parts)}", host


def _reject_non_origin(parts: SplitResult) -> None:
    """An origin is only scheme, host and port. Values with anything else cannot be used.

    A URL with a path, query, fragment or credentials never matches the origin the browser
    puts into ``clientDataJSON``. Unless rejected here, registration passes in the
    browser but only the server-side verification fails.
    """
    if parts.scheme not in _DEFAULT_PORTS:
        raise InvalidWebAuthnOriginError
    if parts.path.strip("/") or parts.query or parts.fragment or parts.username or parts.password:
        raise InvalidWebAuthnOriginError


def _explicit_port(parts: SplitResult) -> str:
    try:
        port = parts.port
    except ValueError as error:  # port is not numeric or out of range
        raise InvalidWebAuthnOriginError from error
    return "" if port is None or port == _DEFAULT_PORTS[parts.scheme] else f":{port}"


def _normalize_domain(value: str) -> str:
    """Normalize for comparison (drop surrounding whitespace, uppercase and trailing dot)."""
    return value.strip().rstrip(".").lower()


def _is_domain(value: str) -> bool:
    """Whether it is usable as an RP ID. IP addresses and values with a port or path cannot be used."""
    if not value or _is_ip_address(value):
        return False
    return all(_LABEL.match(label) for label in value.split("."))


def _is_ip_address(value: str) -> bool:
    try:
        ipaddress.ip_address(value.strip("[]"))
    except ValueError:
        return False
    return True


def _is_registrable_suffix(rp_id: str, host: str) -> bool:
    """Whether ``host`` is ``rp_id`` itself or a domain below it.

    Only **registrable** domains can be used as an RP ID. Browsers reject a public suffix such as
    ``com`` for ``example.com``. Here we drop RP IDs with a single label,
    which rejects most of them (``com`` / ``jp`` etc.). When the host itself has one label,
    like ``localhost``, it counts as a match.

    Multi-level public suffixes such as ``co.uk`` are not detected (that would need the public suffix
    list). Choosing such a setting is unrealistic, and if it slips through the browser just
    rejects it, so we accept that instead of carrying the list.
    """
    if host == rp_id:
        return True
    if "." not in rp_id:
        return False
    return host.endswith(f".{rp_id}")


__all__ = ["RelyingPartyConfiguration", "validate_relying_party_configuration"]
