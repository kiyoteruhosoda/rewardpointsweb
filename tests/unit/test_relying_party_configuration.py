"""Validation of RP ID and origin consistency (WebAuthn rules)."""

from __future__ import annotations

import pytest

from bounded_contexts.account_security.domain.exceptions import (
    InvalidWebAuthnOriginError,
    InvalidWebAuthnRelyingPartyIdError,
)
from bounded_contexts.account_security.domain.services.relying_party_configuration import (
    validate_relying_party_configuration,
)


@pytest.mark.parametrize(
    ("rp_id", "origin"),
    [
        # Default (development)
        ("localhost", "http://localhost:5173"),
        ("localhost", "http://localhost:8080"),
        # Production
        ("rewardpointsweb.com", "https://rewardpointsweb.com"),
        ("rewardpointsweb.com", "https://rewardpointsweb.com:8443"),
        # Opened on a subdomain with the parent domain as RP ID (a registrable suffix)
        ("rewardpointsweb.com", "https://app.rewardpointsweb.com"),
        ("example.co.jp", "https://www.example.co.jp"),
        # Uppercase, trailing dot and surrounding whitespace are normalized before comparing
        ("Example.COM", " https://EXAMPLE.com. "),
    ],
)
def test_accepts_matching_configuration(rp_id: str, origin: str) -> None:
    validate_relying_party_configuration(rp_id=rp_id, origin=origin)


@pytest.mark.parametrize(
    ("rp_id", "origin", "expected"),
    [
        # Stray whitespace and uppercase in the settings are dropped here. Passed to the authenticator as is,
        # the browser's rp.id check and the origin comparison fail.
        (" Example.COM ", " HTTPS://Example.com ", ("example.com", "https://example.com")),
        # Trailing dot and slash
        ("example.com.", "https://example.com./", ("example.com", "https://example.com")),
        # The default port is not included in the origin the browser sends
        ("example.com", "https://example.com:443", ("example.com", "https://example.com")),
        ("localhost", "http://localhost:80", ("localhost", "http://localhost")),
        # Non-default ports are kept
        ("example.com", "https://example.com:8443", ("example.com", "https://example.com:8443")),
    ],
)
def test_returns_normalized_values(rp_id: str, origin: str, expected: tuple[str, str]) -> None:
    configuration = validate_relying_party_configuration(rp_id=rp_id, origin=origin)
    assert (configuration.rp_id, configuration.origin) == expected


@pytest.mark.parametrize(
    ("rp_id", "origin"),
    [
        # An error reported from the screen: the RP name was entered as the RP ID
        ("rewardpointsweb", "https://rewardpointsweb.com"),
        # A different domain
        ("example.com", "https://rewardpointsweb.com"),
        # A partial match is not a suffix (compared by dot-separated labels)
        ("pointsweb.com", "https://rewardpointsweb.com"),
        # The reverse (child domain as RP ID, opened on the parent) does not work
        ("app.example.com", "https://example.com"),
        # Public suffix (not a registrable domain)
        ("com", "https://example.com"),
        ("jp", "https://www.example.jp"),
        # Only a domain name can be used as the RP ID
        ("", "https://example.com"),
        ("192.0.2.10", "https://192.0.2.10"),
        ("example.com:8443", "https://example.com:8443"),
        ("https://example.com", "https://example.com"),
        ("example.com/path", "https://example.com"),
    ],
)
def test_rejects_mismatched_relying_party_id(rp_id: str, origin: str) -> None:
    with pytest.raises(InvalidWebAuthnRelyingPartyIdError) as error:
        validate_relying_party_configuration(rp_id=rp_id, origin=origin)
    assert error.value.code == "invalid_webauthn_rp_id"


@pytest.mark.parametrize(
    "origin",
    [
        "",
        "example.com",  # no scheme
        "ftp://example.com",
        "https://",
        "https://example.com/app",  # with a path it is not an origin
        "http://example.com",  # http only for loopback (WebAuthn requires a secure context)
        # None of the following can match the origin the browser puts in clientDataJSON. Accepting them
        # fails in the form "registration succeeded but only the server's verification fails".
        "https://example.com?tenant=1",
        "https://example.com#top",
        "https://user:pass@example.com",
        "https://example.com:port",
        "https://example.com:99999",
    ],
)
def test_rejects_unusable_origin(origin: str) -> None:
    with pytest.raises(InvalidWebAuthnOriginError) as error:
        validate_relying_party_configuration(rp_id="example.com", origin=origin)
    assert error.value.code == "invalid_webauthn_origin"
