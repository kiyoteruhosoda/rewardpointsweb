"""Domain exceptions of the identity federation context.

``code`` becomes the API error code as is (the display text is up to the frontend).
A failure in the middle of the browser round trip comes back to the login screen as
``?sso_error=<code>`` (ADR-0029).
"""

from __future__ import annotations


class IdentityFederationError(Exception):
    """Base exception of this context."""

    code = "sso_error"


class SsoNotConfiguredError(IdentityFederationError):
    """SSO is disabled, or the connection target (issuer / client) is not filled in."""

    code = "sso_not_configured"


class SsoLoginSessionNotFoundError(IdentityFederationError):
    """The saved authorization request is not found (``state`` mismatch, expired, or already used)."""

    code = "sso_state_invalid"


class SsoTicketNotFoundError(IdentityFederationError):
    """The exchange ticket is not found (expired or already used)."""

    code = "sso_ticket_invalid"


class IdentityProviderUnavailableError(IdentityFederationError):
    """Cannot talk to the IdP (communication / response failure in discovery or token exchange)."""

    code = "sso_provider_unavailable"


class InvalidIdTokenError(IdentityFederationError):
    """ID token verification failed (signature, issuer, audience, nonce)."""

    code = "sso_invalid_id_token"


class InvalidLogoutTokenError(IdentityFederationError):
    """``logout_token`` verification failed (signature, issuer, audience, expiry, shape).

    **Do not expose the reason.** This endpoint can be called unauthenticated, so a detailed answer
    would give brute-force attempts a hint about "how far it got".
    """

    code = "sso_invalid_logout_token"


class SsoAcrNotSatisfiedError(IdentityFederationError):
    """The requested authentication strength (``acr_values``) is not satisfied (ADR-0039).

    This also applies when no ``acr`` comes back. We asked for it and got no assurance,
    so it must not pass.
    """

    code = "sso_acr_not_satisfied"


class SsoEmailNotAllowedError(IdentityFederationError):
    """Email domain is not allowed."""

    code = "sso_email_not_allowed"


class SsoAccountNotLinkedError(IdentityFederationError):
    """An account with the same email address already exists but is not yet linked to this IdP (ADR-0041).

    ⚠ **Refuse instead of creating one.** Creating it would give the same person two accounts (``users.email`` is
    unique, so the second one would have no email address). Merging by email (ADR-0033) is off by default,
    so the person signs in to that account with a password and links it from the settings screen (ADR-0036).
    """

    code = "sso_account_not_linked"


class SsoUsernameUnavailableError(IdentityFederationError):
    """Tried to create an account for a first-time user, but cannot decide the ``username`` (ADR-0041).

    The IdP's ``preferred_username`` is missing, does not match this app's identifier rules,
    or is already used by another user. ⚠ **Do not silently add a sequence number or another value**
    -- the login identifier would become a value the person does not know.
    """

    code = "sso_username_unavailable"


class SsoIdentityTakenError(IdentityFederationError):
    """That IdP account is linked to **another user** (ADR-0036).

    ⚠ **Refuse, since it would be a takeover.** If re-linking were allowed, someone sharing one account
    on the IdP side could later steal another person's way into this app.
    """

    code = "sso_identity_taken"


class SsoAlreadyLinkedError(IdentityFederationError):
    """This user **already has** a link to that IdP (ADR-0036).

    To switch to another ``subject``, unlink first and then link again. Silently
    overwriting it would remove the route that used the previous link without notice.
    """

    code = "sso_already_linked"


class SsoIdentityNotLinkedError(IdentityFederationError):
    """Tried to unlink, but there is no link to that IdP."""

    code = "sso_identity_not_linked"


class SsoLastEntranceError(IdentityFederationError):
    """Unlinking would leave this user with **no way to sign in at all** (ADR-0036).

    ⚠ **Do not create a lockout.** Removing the IdP from a user with neither a local password
    nor a passkey leaves recovery by an administrator as the only option.
    """

    code = "sso_last_entrance"


class SsoLinkSessionMismatchError(IdentityFederationError):
    """The user who started the linking round trip differs from the session that came back.

    Happens when the user signed out mid-round-trip or signed in again as another user.
    **We cannot decide which account to link**, so the user has to start over.
    """

    code = "sso_link_session_mismatch"


class SsoAccountInactiveError(IdentityFederationError):
    """The account is deactivated."""

    code = "sso_account_inactive"


class MachineNotBoundToApplicationError(IdentityFederationError):
    """The service account we identify as is not bound to any app in assay (403 from the admin API. ADR-0040).

    ⚠ **Not an outage but "not set up yet".** assay decides whose roster to return from
    the calling service account, so this comes back every time until it is bound.
    """

    code = "machine_not_bound_to_application"


__all__ = [
    "IdentityFederationError",
    "IdentityProviderUnavailableError",
    "InvalidIdTokenError",
    "InvalidLogoutTokenError",
    "MachineNotBoundToApplicationError",
    "SsoAccountInactiveError",
    "SsoAccountNotLinkedError",
    "SsoAcrNotSatisfiedError",
    "SsoAlreadyLinkedError",
    "SsoEmailNotAllowedError",
    "SsoIdentityNotLinkedError",
    "SsoIdentityTakenError",
    "SsoLastEntranceError",
    "SsoLinkSessionMismatchError",
    "SsoLoginSessionNotFoundError",
    "SsoNotConfiguredError",
    "SsoTicketNotFoundError",
    "SsoUsernameUnavailableError",
]
