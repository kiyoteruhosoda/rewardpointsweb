"""Map the IdP's assertion to a user of this app.

In order, it tries

1. the user linked by ``(issuer, subject)``, if any
2. otherwise, merging into an existing user by **verified** email address (off by default. ADR-0033)
3. if neither, **creating an account** (ADR-0041)

. Step 3 creates one because **someone who came back from assay with a code = someone assigned
to use this app**. People without an assignment are stopped on assay's screen and never get
this far (idp ADR-0054). A record is left in ``federated_identities`` when linked, so
from the second time on it is decided by step 1.

⚠ **Refuse when it cannot be created.** An account with the same email address already exists
(``sso_account_not_linked``;
this includes accounts whose identifier (``username``) is that address),
or the ``username`` cannot be decided (``sso_username_unavailable``). Silently creating it with another value
in either case would give the same person two accounts, or an identifier the person does not know.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from bounded_contexts.identity_federation.application.dto.sso_dto import (
    ResolvedAccountDto,
)
from bounded_contexts.identity_federation.domain.entities.federated_account import (
    FederatedAccount,
)
from bounded_contexts.identity_federation.domain.entities.federated_identity import (
    FederatedIdentity,
)
from bounded_contexts.identity_federation.domain.exceptions import (
    SsoAccountInactiveError,
    SsoAccountNotLinkedError,
    SsoUsernameUnavailableError,
)
from bounded_contexts.identity_federation.domain.repositories.federated_identity_repository import (
    FederatedIdentityRepository,
)
from bounded_contexts.identity_federation.domain.repositories.federated_user_directory import (
    FederatedUserDirectory,
)
from bounded_contexts.identity_federation.domain.value_objects.account_linking_policy import (
    AccountLinkingPolicy,
)
from bounded_contexts.identity_federation.domain.value_objects.federated_user import (
    FederatedUser,
)
from shared.domain.auth.username import Username

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ResolveFederatedAccount:
    identities: FederatedIdentityRepository
    directory: FederatedUserDirectory
    policy: AccountLinkingPolicy

    def execute(self, *, issuer: str, user: FederatedUser) -> ResolvedAccountDto:
        self.policy.ensure_accepted(user)
        known = self._known_account(issuer, user.subject)
        if known is not None:
            _ensure_active(known)
            # ⚠ **The copy treats the IdP as the source of truth** (ADR-0038). Without overwriting here,
            #   renames or email changes over there would leave the display stale forever.
            self.directory.refresh_profile(known.user_id, email=user.email, display_name=user.display_name)
            return ResolvedAccountDto(user_id=known.user_id)
        return self._welcome(issuer, user)

    def _known_account(self, issuer: str, subject: str) -> FederatedAccount | None:
        identity = self.identities.find(issuer, subject)
        if identity is None:
            return None
        account = self.directory.find_by_id(identity.user_id)
        if account is None:
            # The user was deleted but the link remains. Hand it over to re-linking.
            return None
        self.identities.touch(identity)
        return account

    def _welcome(self, issuer: str, user: FederatedUser) -> ResolvedAccountDto:
        """A first-time user. Merge into an account if one can be merged, otherwise create one (ADR-0041).

        ⚠ **This is the only place that needs an email address** (ADR-0038). Users already
        linked can be found by ``sub``, so they can sign in without one.
        """
        existing = self._account_holding(user.email) if user.email else None
        if existing is not None:
            if not self.policy.may_link(user):
                # ⚠ **Refuse instead of creating** (ADR-0041). Creating would give the same person two accounts. Merging
                #   is off by default (ADR-0033), so the person signs in to that account and links it.
                raise SsoAccountNotLinkedError
            _ensure_active(existing)
            return self._link(issuer, user.subject, existing, provisioned=False)
        username = self._free_username(user)
        created = self.directory.provision(username=username, email=user.email, display_name=user.display_name)
        if created is None:
            # Between checking and creating, another round trip took the same value.
            logger.warning("sso_username_unavailable", extra={"reason": "raced"})
            raise SsoUsernameUnavailableError
        return self._link(issuer, user.subject, created, provisioned=True)

    def _account_holding(self, email: str) -> FederatedAccount | None:
        """The account with this email address: the ``email`` column, or an account whose identifier is that address.

        ⚠ **The ``email`` column alone misses some.** Accounts created by accepting an invitation have no
        ``email`` (ADR-0011), and many accounts use their email address as the identifier (so do migrated values).
        Searching by ``email`` alone creates a second account when that person first arrives via SSO,
        and they drop out of the family (happened in production on 2026-10-05).
        """
        holder = self.directory.find_by_email(email)
        if holder is not None:
            return holder
        try:
            username = Username(email).value
        except ValueError:
            return None
        return self.directory.find_by_username(username)

    def _free_username(self, user: FederatedUser) -> str:
        """Turn the IdP's ``preferred_username`` into this app's ``username``.

        ⚠ **If unusable, refuse. Do not silently add a sequence number or another value** (ADR-0041). Logs keep
        only which reason it was, not the value itself (PII).
        """
        if user.preferred_username is None:
            logger.warning("sso_username_unavailable", extra={"reason": "missing"})
            raise SsoUsernameUnavailableError
        try:
            username = Username(user.preferred_username).value
        except ValueError as error:
            logger.warning("sso_username_unavailable", extra={"reason": "invalid"})
            raise SsoUsernameUnavailableError from error
        if self.directory.find_by_username(username) is not None:
            logger.warning("sso_username_unavailable", extra={"reason": "taken"})
            raise SsoUsernameUnavailableError
        return username

    def _link(self, issuer: str, subject: str, account: FederatedAccount, *, provisioned: bool) -> ResolvedAccountDto:
        self.identities.link(FederatedIdentity(issuer=issuer, subject=subject, user_id=account.user_id))
        return ResolvedAccountDto(user_id=account.user_id, linked=True, provisioned=provisioned)


def _ensure_active(account: FederatedAccount) -> None:
    if not account.is_active:
        raise SsoAccountInactiveError


__all__ = ["ResolveFederatedAccount"]
