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
    """メールアドレスを持つ利用者だけを並べた名簿（``users`` の代わり）。"""

    by_email: dict[str, FederatedAccount] = field(default_factory=dict)
    refreshed: list[tuple[int, str | None, str]] = field(default_factory=list)

    def find_by_id(self, user_id: int) -> FederatedAccount | None:
        return next((a for a in self.by_email.values() if a.user_id == user_id), None)

    def find_by_email(self, email: str) -> FederatedAccount | None:
        return self.by_email.get(email)

    def refresh_profile(self, user_id: int, *, email: str | None, display_name: str) -> None:
        self.refreshed.append((user_id, email, display_name))


def _user(
    *,
    subject: str = "idp-1",
    email: str | None = "parent@example.com",
    verified: bool = True,
    display_name: str = "親",
) -> FederatedUser:
    return FederatedUser(subject=subject, email=email, display_name=display_name, email_verified=verified)


def _resolve(identities: FakeIdentities, directory: FakeDirectory) -> ResolveFederatedAccount:
    """⚠ **寄せるのは既定ではない**（ADR-0033）。ここは結び付けの筋道を見たいので開ける。"""
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


def test_by_default_an_existing_user_is_not_linked() -> None:
    """⚠ 既定は寄せない（ADR-0033）。

    ⚠ **このアプリは SSO で利用者を作らない**ので、これが偽のあいだ
    **まだ結び付いていない人は SSO で入れない**（パスワードでは入れる）。
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


def test_the_profile_copy_is_rewritten_on_every_sign_in() -> None:
    """⚠ **写しは IdP を正とする**（ADR-0038）。

    上書きしないと、向こうで改名・メール変更をしても表示が永久に古いままになる。
    ぶつかる値を書かない判断は名簿（実装）の側が持つ。
    """
    identities = FakeIdentities({(ISSUER, "idp-1"): 7})
    directory = FakeDirectory({"parent@example.com": FederatedAccount(user_id=7, is_active=True)})

    _resolve(identities, directory).execute(issuer=ISSUER, user=_user(email="new@example.com", display_name="新"))

    assert directory.refreshed == [(7, "new@example.com", "新")]


def test_a_linked_user_signs_in_without_an_email_at_all() -> None:
    """鍵は ``(issuer, subject)`` なので、メールアドレスが無くても通る（ADR-0038）。"""
    identities = FakeIdentities({(ISSUER, "idp-1"): 7})
    directory = FakeDirectory({"parent@example.com": FederatedAccount(user_id=7, is_active=True)})

    resolved = _resolve(identities, directory).execute(issuer=ISSUER, user=_user(email=None))

    assert (resolved.user_id, resolved.linked) == (7, False)
    # ⚠ **名乗っていない項目は消さない。** ``None`` は「空にしてほしい」ではない。
    assert directory.refreshed == [(7, None, "親")]


def test_a_first_visit_without_an_email_is_refused() -> None:
    """初回は寄せる先を探せない。⚠ **理由は結び付く利用者が無いときと同じにする。**"""
    identities = FakeIdentities()
    directory = FakeDirectory({"parent@example.com": FederatedAccount(user_id=7, is_active=True)})

    with pytest.raises(SsoAccountNotLinkedError):
        _resolve(identities, directory).execute(issuer=ISSUER, user=_user(email=None))

    assert identities.linked == {}
