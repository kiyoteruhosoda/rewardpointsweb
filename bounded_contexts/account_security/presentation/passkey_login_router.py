"""Passkey login API (callable unauthenticated).

Identity is verified with the authenticator's signature instead of a password. On successful verification,
the same token pair as a normal login is issued.

Failures are logged at WARNING. The default for 401 is INFO (since expired-token refreshes would flood it),
but operations want to see whether login failures keep happening (ADR-0012).
"""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from bounded_contexts.account_security.application.use_cases.authenticate_with_passkey import (
    CompletePasskeyAuthentication,
    StartPasskeyAuthentication,
)
from bounded_contexts.account_security.domain.exceptions import AccountSecurityError
from bounded_contexts.account_security.presentation import dependencies
from bounded_contexts.account_security.presentation.schemas import (
    PasskeyAuthenticationRequest,
    PasskeyChallengeResponse,
)
from presentation.fastapi.dependencies.auth import set_access_token_cookie
from presentation.fastapi.schemas.auth import TokenResponse
from presentation.fastapi.services.token_service import TokenService
from shared.infrastructure.models import User
from shared.kernel.database.session import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth/passkey", tags=["auth"])

DbDep = Annotated[Session, Depends(get_db)]


@router.post("/challenge", response_model=PasskeyChallengeResponse)
def create_login_challenge(
    use_case: Annotated[StartPasskeyAuthentication, Depends(dependencies.start_passkey_authentication)],
) -> PasskeyChallengeResponse:
    """Issue a login challenge (for ``navigator.credentials.get``).

    Who is logging in is not specified. By letting the authenticator pick a registered credential,
    login works without entering an email address.
    """
    challenge = use_case.execute()
    return PasskeyChallengeResponse(challenge_id=challenge.challenge_id, public_key=challenge.public_key)


@router.post("/login", response_model=TokenResponse)
def login_with_passkey(
    *,
    body: PasskeyAuthenticationRequest,
    response: Response,
    db: DbDep,
    use_case: Annotated[
        CompletePasskeyAuthentication,
        Depends(dependencies.complete_passkey_authentication),
    ],
) -> TokenResponse:
    try:
        user_id = use_case.execute(challenge_id=body.challenge_id, credential=body.credential)
    except AccountSecurityError as error:
        # Mapping to the response is left to the domain exception handler; here we only add logging.
        # Signature verification failures and expired challenges should also be visible as "login failures".
        logger.warning("passkey_login_failed: %s", error.code)
        raise

    user = db.get(User, user_id)
    if user is None or not user.is_active:
        # Log at WARNING like password login. The default for 401 is INFO,
        # but operations want to see whether login failures keep happening (ADR-0012).
        logger.warning("passkey_login_failed: invalid_credentials")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "invalid_credentials"},
        )

    pair = TokenService.create_token_pair(user)
    set_access_token_cookie(response, str(pair["access_token"]))
    logger.info("passkey_login_succeeded")
    return TokenResponse(**pair)  # type: ignore[arg-type]
