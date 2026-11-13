"""Mapping the IdP's identity claims onto a user of this app.

A first-time visitor gets an account created for them (ADR-0041). What this guards is **not silently creating
it in some other form when it cannot be created** -- an account with the same email exists, or ``username`` is unusable.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from bounded_contexts.identity_federation.application.use_cases.resolve_federated_account import (
    ResolveFederatedAccount,
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
from bounded_contexts.identity_federation.domain.value_objects.account_linking_policy import (
    AccountLinkingPolicy,
)
from bounded_contexts.identity_federation.domain.value_objects.federated_user import (
    FederatedUser,
)

ISSUER = "https://idp.example"


@dataclass
class FakeIdentities:
    linked: dict[tuple[str, str], int] = field(default_factory=dict)
    touched: list[tuple[str, str]] = field(default_factory=list)

    def find(self, issuer: str, subject: str) -> FederatedIdentity | None:
        user_id = self.linked.get((issuer, subject))
        return None if user_id is None else FederatedIdentity(issuer, subject, user_id)

    def link(self, identity: FederatedIdentity) -> FederatedIdentity:
        self.linked[(identity.issuer, identity.subject)] = identity.user_id
        return identity

    def find_for_user(self, issuer: str, user_id: int) -> FederatedIdentity | None:
        for (row_issuer, subject), owner in self.linked.items():
            if row_issuer == issuer and owner == user_id:
                return FederatedIdentity(row_issuer, subject, owner)
        return None

    def unlink(self, identity: FederatedIdentity) -> None:
        self.linked.pop((identity.issuer, identity.subject), None)

    def touch(self, identity: FederatedIdentity) -> None:
        self.touched.append((identity.issuer, identity.subject))

    def list_for_issuer(self, issuer: str) -> list[FederatedIdentity]:
        return [FederatedIdentity(i, s, u) for (i, s), u in self.linked.items() if i == issuer]


@dataclass
class FakeDirectory:
    """A roster listing only users with an email address (stands in for ``users``)."""

    by_email: dict[str, FederatedAccount] = field(default_factory=dict)
    refreshed: list[tuple[int, str | None, str]] = field(default_factory=list)
    usernames: set[str] = field(default_factory=set)
    created: list[tuple[str, str | None, str]] = field(default_factory=list)
    #: If true, another round trip took the same value after the check (creating would collide on a unique column).
    overtaken: bool = False

    def find_by_id(self, user_id: int) -> FederatedAccount | None:
        return next((a for a in self.by_email.values() if a.user_id == user_id), None)

    def find_by_email(self, email: str) -> FederatedAccount | None:
        return self.by_email.get(email)

    def find_by_username(self, username: str) -> FederatedAccount | None:
        return FederatedAccount(user_id=1, is_active=True) if username in self.usernames else None

    def provision(self, *, username: str, email: str | None, display_name: str) -> FederatedAccount | None:
        if self.overtaken:
            return None
        self.created.append((username, email, display_name))
        return FederatedAccount(user_id=100 + len(self.created), is_active=True)

    def refresh_profile(self, user_id: int, *, email: str | None, display_name: str) -> None:
        self.refreshed.append((user_id, email, display_name))


def _user(
    *,
    subject: str = "idp-1",
    email: str | None = "parent@example.com",
    verified: bool = True,
    display_name: str = "親",
    preferred_username: str | None = "parent",
) -> FederatedUser:
    return FederatedUser(
        subject=subject,
        email=email,
        display_name=display_name,
        email_verified=verified,
        preferred_username=preferred_username,
    )


def _resolve(identities: FakeIdentities, directory: FakeDirectory) -> ResolveFederatedAccount:
    """⚠ **Linking by email is not the default** (ADR-0033). Enabled here because we want to see the linking path."""
    return ResolveFederatedAccount(
        identities=identities,
        directory=directory,
        policy=AccountLinkingPolicy(link_by_email=True),
    )


def test_links_a_verified_address_to_the_existing_user() -> None:
    identities = FakeIdentities()
    directory = FakeDirectory({"parent@example.com": FederatedAccount(user_id=7, is_active=True)})

    resolved = _resolve(identities, directory).execute(issuer=ISSUER, user=_user())

    assert (resolved.user_id, resolved.linked) == (7, True)
    # From the second time on it is resolved by (issuer, subject)
    assert identities.linked == {(ISSUER, "idp-1"): 7}


def test_a_known_identity_wins_even_after_the_address_changed() -> None:
    """The linking key is ``(issuer, subject)``. The email address may change."""
    identities = FakeIdentities({(ISSUER, "idp-1"): 7})
    directory = FakeDirectory({"parent@example.com": FederatedAccount(user_id=7, is_active=True)})

    resolved = _resolve(identities, directory).execute(issuer=ISSUER, user=_user(email="new@example.com"))

    assert (resolved.user_id, resolved.linked) == (7, False)
    assert identities.touched == [(ISSUER, "idp-1")]


def test_an_unknown_address_gets_a_new_account() -> None:
    """Whoever comes back from assay is someone assigned to the app (ADR-0041)."""
    identities = FakeIdentities()
    directory = FakeDirectory()

    resolved = _resolve(identities, directory).execute(issuer=ISSUER, user=_user(preferred_username="Parent"))

    assert (resolved.user_id, resolved.linked, resolved.provisioned) == (101, True, True)
    # ⚠ ``username`` is normalized by the identifier rules (lowercase)
    assert directory.created == [("parent", "parent@example.com", "親")]
    assert identities.linked == {(ISSUER, "idp-1"): 101}


def test_an_unverified_address_is_refused_even_if_a_user_has_it() -> None:
    directory = FakeDirectory({"parent@example.com": FederatedAccount(user_id=7, is_active=True)})

    with pytest.raises(SsoAccountNotLinkedError):
        _resolve(FakeIdentities(), directory).execute(issuer=ISSUER, user=_user(verified=False))

    # ⚠ Being unable to link by email is no reason to create a second account
    assert directory.created == []


def test_a_disabled_user_cannot_sign_in_through_the_idp() -> None:
    directory = FakeDirectory({"parent@example.com": FederatedAccount(user_id=7, is_active=False)})

    with pytest.raises(SsoAccountInactiveError):
        _resolve(FakeIdentities(), directory).execute(issuer=ISSUER, user=_user())


def test_a_link_to_a_deleted_user_is_rebuilt_not_trusted() -> None:
    """When the user was deleted and recreated with the same address.

    While only the link remains, its ``user_id`` is not trusted
    (a deleted user's ID can be reused for someone else).
    """
    identities = FakeIdentities({(ISSUER, "idp-1"): 99})
    directory = FakeDirectory({"parent@example.com": FederatedAccount(user_id=7, is_active=True)})

    resolved = _resolve(identities, directory).execute(issuer=ISSUER, user=_user())

    assert resolved.user_id == 7
    assert identities.linked[(ISSUER, "idp-1")] == 7


def test_by_default_an_existing_user_is_neither_linked_nor_duplicated() -> None:
    """⚠ Not linked by email by default (ADR-0033). ⚠ **And not created either** (ADR-0041).

    Creating one would give the same person two accounts. The person signs in to that account and links it (ADR-0036).
    """
    identities = FakeIdentities()
    directory = FakeDirectory({"parent@example.com": FederatedAccount(user_id=7, is_active=True)})
    use_case = ResolveFederatedAccount(
        identities=identities,
        directory=directory,
        policy=AccountLinkingPolicy(),
    )

    with pytest.raises(SsoAccountNotLinkedError):
        use_case.execute(issuer=ISSUER, user=_user())

    assert (identities.linked, directory.created) == ({}, [])


def test_an_account_whose_username_is_the_address_is_not_duplicated() -> None:
    """⚠ Accounts created by invitation have no ``email``, and their identifier is often an email address (ADR-0011).

    Searching only the ``email`` column misses it, creates a second account, and drops the person out of their family.
    """
    identities = FakeIdentities()
    directory = FakeDirectory(usernames={"parent@example.com"})
    use_case = ResolveFederatedAccount(
        identities=identities,
        directory=directory,
        policy=AccountLinkingPolicy(),
    )

    with pytest.raises(SsoAccountNotLinkedError):
        use_case.execute(issuer=ISSUER, user=_user(email="Parent@example.com"))

    assert (identities.linked, directory.created) == ({}, [])


def test_an_account_whose_username_is_the_address_can_be_linked() -> None:
    """With linking by email enabled, link to the account whose identifier is that address (ADR-0033)."""
    identities = FakeIdentities()
    directory = FakeDirectory(usernames={"parent@example.com"})

    resolved = _resolve(identities, directory).execute(issuer=ISSUER, user=_user())

    assert (resolved.user_id, directory.created) == (1, [])
    assert identities.linked[(ISSUER, "idp-1")] == 1


def test_the_profile_copy_is_rewritten_on_every_sign_in() -> None:
    """⚠ **The copy treats the IdP as the source of truth** (ADR-0038).

    Without overwriting, a rename or email change over there would leave the display stale forever.
    The decision not to write colliding values belongs to the roster (the implementation).
    """
    identities = FakeIdentities({(ISSUER, "idp-1"): 7})
    directory = FakeDirectory({"parent@example.com": FederatedAccount(user_id=7, is_active=True)})

    _resolve(identities, directory).execute(issuer=ISSUER, user=_user(email="new@example.com", display_name="新"))

    assert directory.refreshed == [(7, "new@example.com", "新")]


def test_a_linked_user_signs_in_without_an_email_at_all() -> None:
    """The key is ``(issuer, subject)``, so it works without an email address (ADR-0038)."""
    identities = FakeIdentities({(ISSUER, "idp-1"): 7})
    directory = FakeDirectory({"parent@example.com": FederatedAccount(user_id=7, is_active=True)})

    resolved = _resolve(identities, directory).execute(issuer=ISSUER, user=_user(email=None))

    assert (resolved.user_id, resolved.linked) == (7, False)
    # ⚠ **Do not erase fields that were not claimed.** ``None`` does not mean "please clear it".
    assert directory.refreshed == [(7, None, "親")]


def test_a_first_visit_without_an_email_still_gets_an_account() -> None:
    """The email address is not the key (ADR-0038). What creation needs is ``username``."""
    identities = FakeIdentities()
    directory = FakeDirectory({"parent@example.com": FederatedAccount(user_id=7, is_active=True)})

    resolved = _resolve(identities, directory).execute(issuer=ISSUER, user=_user(email=None, preferred_username="kid"))

    assert resolved.provisioned
    assert directory.created == [("kid", None, "親")]


@pytest.mark.parametrize("preferred_username", [None, "ab", "名前", "has space"])
def test_an_unusable_username_is_refused(preferred_username: str | None) -> None:
    """Missing, too short, or not matching the rules. ⚠ **Do not silently assign another value** (ADR-0041)."""
    identities = FakeIdentities()
    directory = FakeDirectory()

    with pytest.raises(SsoUsernameUnavailableError):
        _resolve(identities, directory).execute(issuer=ISSUER, user=_user(preferred_username=preferred_username))

    assert (identities.linked, directory.created) == ({}, [])


def test_a_taken_username_is_refused_instead_of_numbered() -> None:
    """⚠ **On a collision, refuse instead of creating** (ADR-0041). Do not append a number like ``parent2``."""
    directory = FakeDirectory(usernames={"parent"})

    with pytest.raises(SsoUsernameUnavailableError):
        _resolve(FakeIdentities(), directory).execute(issuer=ISSUER, user=_user(preferred_username="Parent"))

    assert directory.created == []


def test_an_account_taken_while_creating_is_refused_too() -> None:
    """Another round trip took the same value between the check and the creation. Leave no link behind."""
    identities = FakeIdentities()

    with pytest.raises(SsoUsernameUnavailableError):
        _resolve(identities, FakeDirectory(overtaken=True)).execute(issuer=ISSUER, user=_user())

    assert identities.linked == {}
