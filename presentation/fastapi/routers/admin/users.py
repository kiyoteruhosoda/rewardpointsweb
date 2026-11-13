"""User management API (requires ``user:manage``).

Creating, changing and deleting accounts is written to the app log. These operations touch other
people's accounts, and it would be a problem not to be able to trace later "whose account changed
when". **Identifiers go into the message** — only items with columns go into the ``log`` table,
and the rest of ``extra`` appears only in the JSON on stdout. User names and email addresses are
not written (the logging section of CLAUDE.md).

The list also returns **"the ways this user can get in"** (``entrances``; ADR-0035). With two
authentication systems, the number of open ways in is only clear when listed side by side. The
data comes from **asking each context** — passwords from the ``users`` columns, TOTP and
passkeys from account_security, IdP links from identity_federation, display device
credentials from display_devices (ADR-0047).
"""

from __future__ import annotations

import logging
from collections.abc import Set
from dataclasses import dataclass
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session
from werkzeug.security import generate_password_hash

from bounded_contexts.account_security.application.use_cases.count_local_factors import (
    CountLocalFactors,
)
from bounded_contexts.account_security.domain.value_objects.local_factors import (
    LocalFactors,
)
from bounded_contexts.account_security.infrastructure.sql_local_factor_directory import (
    SqlLocalFactorDirectory,
)
from bounded_contexts.display_devices.application.use_cases.open_display_session import (
    DescribeDisplayCredentialsUseCase,
)
from bounded_contexts.display_devices.infrastructure.sql_display_repositories import (
    SqlDisplayCredentialRepository,
)
from bounded_contexts.identity_federation.application.use_cases.list_federated_issuers import (
    ListFederatedIssuers,
)
from bounded_contexts.identity_federation.infrastructure.sql_federated_issuer_directory import (
    SqlFederatedIssuerDirectory,
)
from bounded_contexts.reward_points.application.use_cases.ensure_user_can_be_deleted import (
    EnsureUserCanBeDeletedUseCase,
)
from bounded_contexts.reward_points.domain.exceptions import UserStillOwnsFamiliesError
from bounded_contexts.reward_points.presentation.dependencies import (
    get_ensure_user_can_be_deleted_use_case,
)
from presentation.fastapi.dependencies.auth import require_permission
from presentation.fastapi.schemas.admin import (
    SignInEntrances,
    UserCreateRequest,
    UserResponse,
    UserUpdateRequest,
)
from shared.application.authenticated_principal import AuthenticatedPrincipal
from shared.domain.auth.username import Username
from shared.infrastructure.models import Role, User
from shared.kernel.database.session import get_db

logger = logging.getLogger(__name__)

# The scope that opens this router itself. Changes that take it away from oneself are refused.
MANAGE_USERS = "user:manage"

router = APIRouter(
    prefix="/api/admin/users",
    tags=["admin"],
    dependencies=[Depends(require_permission(MANAGE_USERS))],
)

DbDep = Annotated[Session, Depends(get_db)]
DeletableDep = Annotated[EnsureUserCanBeDeletedUseCase, Depends(get_ensure_user_can_be_deleted_use_case)]
UserManagerDep = Annotated[AuthenticatedPrincipal, Depends(require_permission(MANAGE_USERS))]


@dataclass(frozen=True)
class _Inventory:
    """Data for the inventory. Fetched for everyone at once, not re-fetched per user."""

    factors: dict[int, LocalFactors]
    issuers: dict[int, tuple[str, ...]]
    display_devices: Set[int] = frozenset()

    @classmethod
    def of(cls, db: Session) -> _Inventory:
        return cls(
            factors=CountLocalFactors(SqlLocalFactorDirectory(db)).execute(),
            issuers=ListFederatedIssuers(SqlFederatedIssuerDirectory(db)).execute(),
            display_devices=DescribeDisplayCredentialsUseCase(SqlDisplayCredentialRepository(db)).holders(),
        )

    @classmethod
    def none(cls) -> _Inventory:
        """A just-created user. No second factor, links or devices yet."""
        return cls(factors={}, issuers={})

    def entrances_of(self, user: User) -> SignInEntrances:
        factors = self.factors.get(user.id, LocalFactors())
        return SignInEntrances(
            password=user.has_local_password,
            totp=factors.totp,
            passkeys=factors.passkeys,
            identity_providers=list(self.issuers.get(user.id, ())),
            display_device=user.id in self.display_devices,
        )


def _to_response(user: User, inventory: _Inventory) -> UserResponse:
    return UserResponse(
        id=user.id,
        username=user.username,
        email=user.email,
        display_name=user.display_name,
        is_active=user.is_active,
        must_change_password=user.must_change_password,
        roles=sorted(r.name for r in user.roles),
        permissions=sorted(user.permission_codes),
        entrances=inventory.entrances_of(user),
    )


def _changed_fields(body: UserUpdateRequest) -> list[str]:
    """List only the names of changed fields (values are not recorded)."""
    candidates = (
        ("display_name", body.display_name),
        ("is_active", body.is_active),
        ("roles", body.roles),
        ("password", body.password),
    )
    return [name for name, value in candidates if value is not None]


def _resolve_roles(db: Session, names: list[str]) -> list[Role]:
    roles = db.scalars(select(Role).where(Role.name.in_(names))).all()
    missing = set(names) - {r.name for r in roles}
    if missing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "unknown_roles", "roles": sorted(missing)},
        )
    return list(roles)


def _reject_self_lockout(principal: AuthenticatedPrincipal, user: User, roles: list[Role]) -> None:
    """Refuse changes that take the user management scope away from oneself.

    In the UI, changing roles is a single checkbox toggle. If the last administrator removes their
    own admin role, all admin functions including this API close and cannot be restored from the
    UI (it takes direct DB access or reseeding the master data). Changes to others are not
    blocked — they are needed for handovers, and the actor keeps their access.
    """
    if user.id != principal.user_id:
        return
    if any(permission.code == MANAGE_USERS for role in roles for permission in role.permissions):
        return
    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail={"error": "cannot_revoke_own_user_manage"},
    )


@router.get("", response_model=list[UserResponse])
def list_users(db: DbDep) -> list[UserResponse]:
    users = db.scalars(select(User).order_by(User.id)).all()
    inventory = _Inventory.of(db)
    return [_to_response(u, inventory) for u in users]


@router.post("", status_code=status.HTTP_201_CREATED, response_model=UserResponse)
def create_user(body: UserCreateRequest, db: DbDep) -> UserResponse:
    try:
        username = Username(body.username).value
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "invalid_username"},
        ) from error
    if db.scalar(select(User).where(User.username == username)):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"error": "username_already_taken"},
        )
    if body.email and db.scalar(select(User).where(User.email == body.email)):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"error": "email_already_exists"},
        )
    user = User(
        username=username,
        email=body.email,
        display_name=body.display_name,
        password_hash=generate_password_hash(body.password),
        is_active=True,
    )
    user.roles = _resolve_roles(db, body.roles)
    db.add(user)
    db.flush()
    logger.info("admin_user_created: user_id=%s", user.id)
    return _to_response(user, _Inventory.none())


@router.put("/{user_id}", response_model=UserResponse)
def update_user(user_id: int, body: UserUpdateRequest, db: DbDep, *, principal: UserManagerDep) -> UserResponse:
    """Change an account.

    ``roles`` is **the full set after the change**, not a diff (roles are untouched when omitted).
    Permissions come only via roles (the permissions section of CLAUDE.md), so to change what
    the person can do, reassign roles.
    """
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"error": "user_not_found"})
    if body.display_name is not None:
        user.display_name = body.display_name
    if body.is_active is not None:
        user.is_active = body.is_active
    if body.roles is not None:
        roles = _resolve_roles(db, body.roles)
        _reject_self_lockout(principal, user, roles)
        user.roles = roles
    if body.password is not None:
        user.password_hash = generate_password_hash(body.password)
    db.flush()
    logger.info("admin_user_updated: user_id=%s fields=%s", user_id, ",".join(_changed_fields(body)) or "none")
    if body.roles is not None:
        # Record roles as "the state after the change". A diff alone cannot reconstruct later
        # who could do what at that point (same reason as the permission log in roles.py).
        logger.info(
            "admin_user_roles_changed: user_id=%s roles=%s",
            user_id,
            ",".join(sorted(r.name for r in user.roles)) or "none",
        )
    return _to_response(user, _Inventory.of(db))


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(user_id: int, db: DbDep, deletable: DeletableDep) -> None:
    """Delete an account.

    An account still registered as a family owner cannot be deleted (409). To merely disable it,
    set `is_active` to false. Family memberships and ledger actors follow the foreign keys'
    `ON DELETE` when the account is deleted (ADR-0009).
    """
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"error": "user_not_found"})
    try:
        deletable.execute(user_id=user_id)
    except UserStillOwnsFamiliesError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail={"error": error.code}) from error
    user.roles = []
    db.delete(user)
    logger.info("admin_user_deleted: user_id=%s", user_id)
