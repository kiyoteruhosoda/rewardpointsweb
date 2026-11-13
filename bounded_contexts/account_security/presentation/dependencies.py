"""Assembly of use cases (factories for ``Depends()``).

Dependency creation is gathered here, and routers receive only finished use cases
(dependency injection per CLAUDE.md "Design principles"). Settings are read only via
``@property`` on ``settings``.
"""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from bounded_contexts.account_security.application.use_cases.authenticate_with_passkey import (
    CompletePasskeyAuthentication,
    StartPasskeyAuthentication,
)
from bounded_contexts.account_security.application.use_cases.manage_passkeys import (
    DeletePasskey,
    ListPasskeys,
)
from bounded_contexts.account_security.application.use_cases.manage_totp import (
    ConfirmTotpEnrollment,
    DisableTotp,
    GetTwoFactorStatus,
    StartTotpEnrollment,
)
from bounded_contexts.account_security.application.use_cases.register_passkey import (
    CompletePasskeyRegistration,
    StartPasskeyRegistration,
)
from bounded_contexts.account_security.application.use_cases.throttle_login import ThrottleLogin
from bounded_contexts.account_security.application.use_cases.verify_second_factor import (
    VerifySecondFactor,
)
from bounded_contexts.account_security.domain.entities.login_attempts import ThrottlePolicy
from bounded_contexts.account_security.domain.exceptions import (
    PasskeyConfigurationError,
)
from bounded_contexts.account_security.domain.services.relying_party_configuration import (
    validate_relying_party_configuration,
)
from bounded_contexts.account_security.domain.services.totp_authenticator import (
    TotpAuthenticator,
)
from bounded_contexts.account_security.domain.services.webauthn_relying_party import (
    WebAuthnRelyingParty,
)
from bounded_contexts.account_security.infrastructure.py_webauthn_relying_party import (
    PyWebAuthnRelyingParty,
)
from bounded_contexts.account_security.infrastructure.pyotp_totp_authenticator import (
    PyotpTotpAuthenticator,
)
from bounded_contexts.account_security.infrastructure.sql_login_attempt_repository import (
    SqlLoginAttemptRepository,
)
from bounded_contexts.account_security.infrastructure.sql_passkey_credential_repository import (
    SqlPasskeyCredentialRepository,
)
from bounded_contexts.account_security.infrastructure.sql_totp_secret_repository import (
    SqlTotpSecretRepository,
)
from bounded_contexts.account_security.infrastructure.sql_webauthn_challenge_repository import (
    SqlWebAuthnChallengeRepository,
)
from shared.kernel.database.db import get_session_factory
from shared.kernel.database.session import get_db
from shared.kernel.settings.settings import settings

logger = logging.getLogger(__name__)

DbDep = Annotated[Session, Depends(get_db)]


def build_totp_authenticator() -> TotpAuthenticator:
    return PyotpTotpAuthenticator(issuer=settings.totp_issuer, valid_window=settings.totp_valid_window)


def build_relying_party() -> WebAuthnRelyingParty:
    """Build the RP. If the settings violate WebAuthn rules, do not let it issue.

    If the RP ID and origin do not match, issuing the challenge succeeds and then
    the browser rejects it with ``SecurityError``. The cause would not be visible from the screen,
    so stop here and return an error code that shows it is a configuration mistake.

    Pass the **normalized values** returned by validation. Passing whitespace or a default port
    from the settings as is makes the ``rp.id`` and origin comparisons fail in the browser.
    """
    rp_id = settings.webauthn_rp_id
    origin = settings.webauthn_origin
    try:
        configuration = validate_relying_party_configuration(rp_id=rp_id, origin=origin)
    except PasskeyConfigurationError as error:
        # Log the values themselves. RP ID and origin are not secrets, and without them
        # the logs do not tell "which one to fix and how".
        logger.error("passkey_misconfigured: %s rp_id=%s origin=%s", error.code, rp_id, origin)
        raise
    return PyWebAuthnRelyingParty(
        rp_id=configuration.rp_id,
        rp_name=settings.webauthn_rp_name,
        origin=configuration.origin,
    )


# External pieces (TOTP implementation, WebAuthn library) are injected as dependencies. In tests
# they can be replaced with fakes via ``app.dependency_overrides``.
TotpAuthenticatorDep = Annotated[TotpAuthenticator, Depends(build_totp_authenticator)]
RelyingPartyDep = Annotated[WebAuthnRelyingParty, Depends(build_relying_party)]


# --- TOTP ---------------------------------------------------------------


def get_two_factor_status(db: DbDep) -> GetTwoFactorStatus:
    return GetTwoFactorStatus(repository=SqlTotpSecretRepository(db))


def start_totp_enrollment(db: DbDep, authenticator: TotpAuthenticatorDep) -> StartTotpEnrollment:
    return StartTotpEnrollment(repository=SqlTotpSecretRepository(db), authenticator=authenticator)


def confirm_totp_enrollment(db: DbDep, authenticator: TotpAuthenticatorDep) -> ConfirmTotpEnrollment:
    return ConfirmTotpEnrollment(repository=SqlTotpSecretRepository(db), authenticator=authenticator)


def disable_totp(db: DbDep, authenticator: TotpAuthenticatorDep) -> DisableTotp:
    return DisableTotp(repository=SqlTotpSecretRepository(db), authenticator=authenticator)


def verify_second_factor(db: DbDep, authenticator: TotpAuthenticatorDep) -> VerifySecondFactor:
    return VerifySecondFactor(repository=SqlTotpSecretRepository(db), authenticator=authenticator)


def throttle_policy() -> ThrottlePolicy:
    """Window, limit and refusal length. **Settings are read on every call** (so no restart is needed)."""
    return ThrottlePolicy(
        max_failures=settings.login_max_failures,
        window=timedelta(seconds=settings.login_failure_window_seconds),
        lock_duration=timedelta(seconds=settings.login_lock_seconds),
    )


def throttle_login() -> ThrottleLogin:
    # ⚠ Do not pass the request's session. Recording a failure goes back with a 401 (exits via
    # an exception), so with the request's session it would be lost on rollback. Records are committed in
    # a short session of their own (ADR-0055)
    return ThrottleLogin(SqlLoginAttemptRepository(get_session_factory()), throttle_policy())


# --- Passkeys -----------------------------------------------------------


def list_passkeys(db: DbDep) -> ListPasskeys:
    return ListPasskeys(repository=SqlPasskeyCredentialRepository(db))


def delete_passkey(db: DbDep) -> DeletePasskey:
    return DeletePasskey(repository=SqlPasskeyCredentialRepository(db))


def start_passkey_registration(db: DbDep, relying_party: RelyingPartyDep) -> StartPasskeyRegistration:
    return StartPasskeyRegistration(
        credentials=SqlPasskeyCredentialRepository(db),
        challenges=SqlWebAuthnChallengeRepository(db),
        relying_party=relying_party,
        challenge_ttl_seconds=settings.webauthn_challenge_ttl_seconds,
    )


def complete_passkey_registration(db: DbDep, relying_party: RelyingPartyDep) -> CompletePasskeyRegistration:
    return CompletePasskeyRegistration(
        credentials=SqlPasskeyCredentialRepository(db),
        challenges=SqlWebAuthnChallengeRepository(db),
        relying_party=relying_party,
    )


def start_passkey_authentication(db: DbDep, relying_party: RelyingPartyDep) -> StartPasskeyAuthentication:
    return StartPasskeyAuthentication(
        challenges=SqlWebAuthnChallengeRepository(db),
        relying_party=relying_party,
        challenge_ttl_seconds=settings.webauthn_challenge_ttl_seconds,
    )


def complete_passkey_authentication(db: DbDep, relying_party: RelyingPartyDep) -> CompletePasskeyAuthentication:
    return CompletePasskeyAuthentication(
        credentials=SqlPasskeyCredentialRepository(db),
        challenges=SqlWebAuthnChallengeRepository(db),
        relying_party=relying_party,
    )


__all__ = [
    "RelyingPartyDep",
    "TotpAuthenticatorDep",
    "build_relying_party",
    "build_totp_authenticator",
    "complete_passkey_authentication",
    "complete_passkey_registration",
    "confirm_totp_enrollment",
    "delete_passkey",
    "disable_totp",
    "get_two_factor_status",
    "list_passkeys",
    "start_passkey_authentication",
    "start_passkey_registration",
    "start_totp_enrollment",
    "throttle_login",
    "throttle_policy",
    "verify_second_factor",
]
