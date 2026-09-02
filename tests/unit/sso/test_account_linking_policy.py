"""既存の利用者へ寄せてよいかの判断。"""

from __future__ import annotations

import pytest

from bounded_contexts.identity_federation.domain.exceptions import (
    SsoEmailNotAllowedError,
)
from bounded_contexts.identity_federation.domain.value_objects.account_linking_policy import (
    AccountLinkingPolicy,
)
from bounded_contexts.identity_federation.domain.value_objects.federated_user import (
    FederatedUser,
)


def _user(email: str, *, verified: bool = True) -> FederatedUser:
    return FederatedUser(subject="s", email=email, display_name="名前", email_verified=verified)


def test_accepts_anyone_when_no_domain_is_configured() -> None:
    AccountLinkingPolicy().ensure_accepted(_user("a@example.com"))


@pytest.mark.parametrize("configured", ["example.com", "@example.com", "Example.COM"])
def test_accepts_a_listed_domain_however_it_was_written(configured: str) -> None:
    AccountLinkingPolicy(allowed_email_domains=(configured,)).ensure_accepted(_user("a@example.com"))


def test_rejects_a_domain_that_is_not_listed() -> None:
    policy = AccountLinkingPolicy(allowed_email_domains=("example.com",))

    with pytest.raises(SsoEmailNotAllowedError):
        policy.ensure_accepted(_user("a@other.example"))


def test_links_only_on_a_verified_address() -> None:
    """未検証のアドレスで寄せると、名乗るだけで他人のアカウントへ入れてしまう。"""
    policy = AccountLinkingPolicy()

    assert policy.may_link(_user("a@example.com")) is True
    assert policy.may_link(_user("a@example.com", verified=False)) is False
