"""IdP の名乗りを、このアプリの利用者へ落とすところ。

**このアプリは SSO で利用者を作らない**（ADR-0029）。ここが守っているのはその
一点で、既に居る利用者へ寄せられなければログインは通らない。
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

    def touch(self, identity: FederatedIdentity) -> None:
        self.touched.append((identity.issuer, identity.subject))


@dataclass
class FakeDirectory:
    """メールアドレスを持つ利用者だけを並べた名簿（``users`` の代わり）。"""

    by_email: dict[str, FederatedAccount] = field(default_factory=dict)

    def find_by_id(self, user_id: int) -> FederatedAccount | None:
        return next((a for a in self.by_email.values() if a.user_id == user_id), None)

    def find_by_email(self, email: str) -> FederatedAccount | None:
        return self.by_email.get(email)


def _user(*, subject: str = "idp-1", email: str = "parent@example.com", verified: bool = True) -> FederatedUser:
    return FederatedUser(subject=subject, email=email, display_name="親", email_verified=verified)


def _resolve(identities: FakeIdentities, directory: FakeDirectory) -> ResolveFederatedAccount:
    return ResolveFederatedAccount(
        identities=identities,
        directory=directory,
        policy=AccountLinkingPolicy(),
    )


def test_links_a_verified_address_to_the_existing_user() -> None:
    identities = FakeIdentities()
    directory = FakeDirectory({"parent@example.com": FederatedAccount(user_id=7, is_active=True)})

    resolved = _resolve(identities, directory).execute(issuer=ISSUER, user=_user())

    assert (resolved.user_id, resolved.linked) == (7, True)
    # 2 回目以降は (issuer, subject) で決まる
    assert identities.linked == {(ISSUER, "idp-1"): 7}


def test_a_known_identity_wins_even_after_the_address_changed() -> None:
    """結び付きの鍵は ``(issuer, subject)``。メールアドレスは変わり得る。"""
    identities = FakeIdentities({(ISSUER, "idp-1"): 7})
    directory = FakeDirectory({"parent@example.com": FederatedAccount(user_id=7, is_active=True)})

    resolved = _resolve(identities, directory).execute(issuer=ISSUER, user=_user(email="new@example.com"))

    assert (resolved.user_id, resolved.linked) == (7, False)
    assert identities.touched == [(ISSUER, "idp-1")]


def test_an_unknown_address_is_refused_instead_of_creating_a_user() -> None:
    identities = FakeIdentities()

    with pytest.raises(SsoAccountNotLinkedError):
        _resolve(identities, FakeDirectory()).execute(issuer=ISSUER, user=_user())

    assert identities.linked == {}


def test_an_unverified_address_is_refused_even_if_a_user_has_it() -> None:
    directory = FakeDirectory({"parent@example.com": FederatedAccount(user_id=7, is_active=True)})

    with pytest.raises(SsoAccountNotLinkedError):
        _resolve(FakeIdentities(), directory).execute(issuer=ISSUER, user=_user(verified=False))


def test_a_disabled_user_cannot_sign_in_through_the_idp() -> None:
    directory = FakeDirectory({"parent@example.com": FederatedAccount(user_id=7, is_active=False)})

    with pytest.raises(SsoAccountInactiveError):
        _resolve(FakeIdentities(), directory).execute(issuer=ISSUER, user=_user())


def test_a_link_to_a_deleted_user_is_rebuilt_not_trusted() -> None:
    """利用者が消され、同じアドレスで作り直された場合。

    結び付きだけが残っている状態では、その ``user_id`` を信用しない
    （消えた利用者の ID が別人へ再利用されることがある）。
    """
    identities = FakeIdentities({(ISSUER, "idp-1"): 99})
    directory = FakeDirectory({"parent@example.com": FederatedAccount(user_id=7, is_active=True)})

    resolved = _resolve(identities, directory).execute(issuer=ISSUER, user=_user())

    assert resolved.user_id == 7
    assert identities.linked[(ISSUER, "idp-1")] == 7
