"""Issuing and verifying JWTs (two tokens: access / refresh).

- The scope claim stays within the user's permissions. Unspecified / empty = no permissions.
- ``fed_iss`` / ``fed_sub`` / ``sid`` / ``fed_iat`` are the address and **start time** of a
  session that began via the IdP (ADR-0032). **Every verification checks "has it been
  stopped"** — the server keeps no record of sessions, so a received stop can only be
  enforced here. Not included in tokens issued for local login.
- The verification result is returned as ``AuthenticatedPrincipal``.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from sqlalchemy.orm import Session

from bounded_contexts.identity_federation.application.use_cases.check_session_revocation import (
    CheckSessionRevocation,
)
from bounded_contexts.identity_federation.domain.value_objects.federated_login import (
    FederatedLogin,
)
from bounded_contexts.identity_federation.domain.value_objects.federated_session import (
    FederatedSession,
)
from bounded_contexts.identity_federation.infrastructure.sql_session_revocation_repository import (
    SqlSessionRevocationRepository,
)
from shared.application.authenticated_principal import AuthenticatedPrincipal
from shared.infrastructure.models import User
from shared.kernel.settings.settings import settings

_ALGORITHM = "HS256"
TYPE_ACCESS = "access"
TYPE_REFRESH = "refresh"
# Address of the IdP-side session (ADR-0032). Only ``sid`` uses the same spelling as OIDC
# (so it is readable as a value copied from the ID token).
CLAIM_FEDERATED_ISSUER = "fed_iss"
CLAIM_FEDERATED_SUBJECT = "fed_sub"
CLAIM_SESSION_ID = "sid"
# Time the session started (microseconds since the epoch). ``iat`` has only second precision and
# would also catch a user who signed in again in the same second right after a stop, so keep it separately.
CLAIM_FEDERATED_ISSUED_AT = "fed_iat"
# Present only when the entry point is a display device (ADR-0047). Value is :data:`VIA_DISPLAY_DEVICE`
CLAIM_VIA = "via"
VIA_DISPLAY_DEVICE = "display_device"


@dataclass(frozen=True)
class RefreshedSession:
    """What is being refreshed. **The entry point (``federated_login``) is returned with it** (ADR-0032).

    If it were dropped, the IdP session address would vanish on every refresh, and **a single
    token refresh would be enough to slip past stop propagation**.
    """

    user: User
    federated_login: FederatedLogin | None


class TokenService:
    @staticmethod
    def create_token_pair(
        user: User,
        scopes: list[str] | None = None,
        *,
        federated_login: FederatedLogin | None = None,
    ) -> dict[str, object]:
        """Issue access / refresh tokens.

        Even when ``scopes`` is given, it is trimmed to the intersection with held permissions.
        Pass ``federated_login`` only for sessions that started via SSO (ADR-0032).

        ⚠ **No refresh token is issued for logins via SSO** (``refresh_token`` is ``None``; ADR-0058).
        When it expires, the UI asks the IdP in a hidden frame and signs in again if the IdP login is alive.
        """
        granted = user.permission_codes
        effective = sorted(granted if scopes is None else granted & set(scopes))
        now = datetime.now(UTC)
        base_claims = {
            "sub": str(user.id),
            "iss": settings.access_token_issuer,
            "aud": settings.access_token_audience,
            "iat": now,
            **_federation_claims(federated_login),
        }
        access = jwt.encode(
            {
                **base_claims,
                "type": TYPE_ACCESS,
                "scope": effective,
                "username": user.username,
                # ⚠ **Verification does not hit the DB, so everything the principal needs goes here**
                #   (ADR-0037). Anything left out ends up empty on that path only.
                "email": user.email,
                "display_name": user.display_name,
                "must_change_password": user.must_change_password,
                "exp": now + timedelta(seconds=settings.access_token_expires_seconds),
            },
            settings.jwt_secret_key,
            algorithm=_ALGORITHM,
        )
        refresh = (
            None
            if federated_login is not None
            else jwt.encode(
                {
                    **base_claims,
                    "type": TYPE_REFRESH,
                    "exp": now + timedelta(seconds=settings.refresh_token_expires_seconds),
                },
                settings.jwt_secret_key,
                algorithm=_ALGORITHM,
            )
        )
        return {
            "access_token": access,
            "refresh_token": refresh,
            "token_type": "bearer",
            "expires_in": settings.access_token_expires_seconds,
        }

    @staticmethod
    def create_display_access_token(user: User) -> dict[str, object]:
        """Access token for a display device (ADR-0047). **No refresh token is issued.**

        The device credential (``/api/display/session``) acts as the refresh token.
        The ``via`` claim is used to refuse credential-changing paths (:func:`get_person_principal`).
        """
        now = datetime.now(UTC)
        access = jwt.encode(
            {
                "sub": str(user.id),
                "iss": settings.access_token_issuer,
                "aud": settings.access_token_audience,
                "iat": now,
                "type": TYPE_ACCESS,
                "scope": sorted(user.permission_codes),
                "username": user.username,
                "email": user.email,
                "display_name": user.display_name,
                "must_change_password": False,
                CLAIM_VIA: VIA_DISPLAY_DEVICE,
                "exp": now + timedelta(seconds=settings.access_token_expires_seconds),
            },
            settings.jwt_secret_key,
            algorithm=_ALGORITHM,
        )
        return {"access_token": access, "expires_in": settings.access_token_expires_seconds}

    @staticmethod
    def _decode(token: str) -> tuple[dict[str, Any] | None, str | None]:
        try:
            claims = jwt.decode(
                token,
                settings.jwt_secret_key,
                algorithms=[_ALGORITHM],
                audience=settings.access_token_audience,
                issuer=settings.access_token_issuer,
            )
            return claims, None
        except jwt.ExpiredSignatureError:
            return None, "token_expired"
        except jwt.InvalidTokenError:
            return None, "token_invalid"

    @classmethod
    def verify_access_token_with_reason(cls, token: str) -> tuple[AuthenticatedPrincipal | None, str | None]:
        """Verify an access token by **signature and claims only** (ADR-0037).

        ⚠ **Does not hit the DB.** Disabled users, removed permissions, stops from the IdP and
        the temporary-password flag set by a parent are not visible here. **They are noticed
        when the next new token is issued**, so the token lifetime (default 5 minutes) is the upper bound.

        ⚠ **Credential-changing paths are the exception** (ADR-0011).
        :func:`get_settled_principal` re-reads the row — if 2FA or passkeys could be swapped right
        after a temporary password was set, setting it would be pointless.
        """
        claims, reason = cls._decode(token)
        if claims is None:
            return None, reason
        if claims.get("type") != TYPE_ACCESS:
            return None, "not_access_token"
        try:
            user_id = int(claims.get("sub", ""))
        except ValueError:
            return None, "token_invalid"
        return (
            AuthenticatedPrincipal(
                user_id=user_id,
                username=str(claims.get("username") or ""),
                display_name=str(claims.get("display_name") or ""),
                email=claims.get("email"),
                permissions=frozenset(claims.get("scope") or ()),
                must_change_password=bool(claims.get("must_change_password")),
                via_display_device=claims.get(CLAIM_VIA) == VIA_DISPLAY_DEVICE,
            ),
            None,
        )

    @classmethod
    def verify_refresh_token(cls, token: str, *, session: Session) -> RefreshedSession | None:
        claims, _ = cls._decode(token)
        if claims is None or claims.get("type") != TYPE_REFRESH:
            return None
        user = cls._load_active_user(claims, session)
        if user is None:
            return None
        if _session_revoked(claims, session):
            return None
        return RefreshedSession(user=user, federated_login=_federated_login_of(claims))

    @classmethod
    def federated_login_of(cls, token: str) -> FederatedLogin | None:
        """Read the IdP-side session from a verified access token.

        For endpoints that reissue tokens to carry it over (without that, the session falls out of
        stop propagation the moment a token is reissued).
        """
        claims, _ = cls._decode(token)
        if claims is None or claims.get("type") != TYPE_ACCESS:
            return None
        return _federated_login_of(claims)

    @classmethod
    def load_active_user(cls, user_id: int, *, session: Session) -> User | None:
        """Row of a user who is not disabled. ⚠ **Use only on reissue and credential-changing paths.**"""
        user = session.get(User, user_id)
        if user is None or not user.is_active:
            return None
        return user

    @staticmethod
    def _load_active_user(claims: dict[str, Any], session: Session) -> User | None:
        try:
            user_id = int(claims.get("sub", ""))
        except ValueError:
            return None
        user = session.get(User, user_id)
        if user is None or not user.is_active:
            return None
        return user


def _federation_claims(federated_login: FederatedLogin | None) -> dict[str, object]:
    """Copy the IdP-side session into claims. Adds nothing for local logins."""
    if federated_login is None:
        return {}
    claims: dict[str, object] = {
        CLAIM_FEDERATED_ISSUER: federated_login.session.issuer,
        CLAIM_FEDERATED_SUBJECT: federated_login.session.subject,
        CLAIM_FEDERATED_ISSUED_AT: _to_microseconds(federated_login.started_at),
    }
    if federated_login.session.session_id is not None:
        claims[CLAIM_SESSION_ID] = federated_login.session.session_id
    return claims


#: How far back the continuation round trip reads the user from an expired SSO access token (ADR-0058).
#: Matches the longest IdP login state (30 days). Older tokens are not read (treated as a new login)
RENEWAL_CARRY_SECONDS = 30 * 24 * 3600


def continued_user_of(token: str) -> int | None:
    """Whose login an expired SSO access token belonged to (ADR-0058).

    ⚠ **This is not authentication.** Used only to see whether **the same person** came back from
    the IdP. Signature, issuer and audience are checked; expiry is tolerated up to
    :data:`RENEWAL_CARRY_SECONDS`. Tokens not from an SSO login are not read (nor display device tokens).
    """
    try:
        claims = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[_ALGORITHM],
            audience=settings.access_token_audience,
            issuer=settings.access_token_issuer,
            leeway=timedelta(seconds=RENEWAL_CARRY_SECONDS),
        )
    except jwt.InvalidTokenError:
        return None
    if claims.get("type") != TYPE_ACCESS or _federated_login_of(claims) is None:
        return None
    try:
        return int(claims.get("sub", ""))
    except ValueError:
        return None


def _federated_login_of(claims: dict[str, Any]) -> FederatedLogin | None:
    """Read the IdP-side session from claims. ``None`` if absent."""
    issuer = claims.get(CLAIM_FEDERATED_ISSUER)
    subject = claims.get(CLAIM_FEDERATED_SUBJECT)
    started_at = claims.get(CLAIM_FEDERATED_ISSUED_AT)
    if not isinstance(issuer, str) or not isinstance(subject, str) or not isinstance(started_at, int):
        return None
    session_id = claims.get(CLAIM_SESSION_ID)
    return FederatedLogin(
        session=FederatedSession(
            issuer=issuer,
            subject=subject,
            session_id=session_id if isinstance(session_id, str) else None,
        ),
        started_at=_from_microseconds(started_at),
    )


def _to_microseconds(moment: datetime) -> int:
    """Naive UTC to microseconds since the epoch (the time contract in CLAUDE.md)."""
    return int(moment.replace(tzinfo=UTC).timestamp() * 1_000_000)


def _from_microseconds(value: int) -> datetime:
    return datetime.fromtimestamp(value / 1_000_000, UTC).replace(tzinfo=None)


def _session_revoked(claims: dict[str, Any], session: Session) -> bool:
    """Whether this token's session has been stopped on the IdP side (ADR-0032)."""
    check = CheckSessionRevocation(revocations=SqlSessionRevocationRepository(session))
    return check.execute(_federated_login_of(claims))


__all__ = [
    "CLAIM_FEDERATED_ISSUED_AT",
    "CLAIM_FEDERATED_ISSUER",
    "CLAIM_FEDERATED_SUBJECT",
    "CLAIM_SESSION_ID",
    "CLAIM_VIA",
    "RENEWAL_CARRY_SECONDS",
    "TYPE_ACCESS",
    "TYPE_REFRESH",
    "VIA_DISPLAY_DEVICE",
    "RefreshedSession",
    "TokenService",
    "continued_user_of",
]
