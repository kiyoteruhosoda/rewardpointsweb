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


def test_by_default_nothing_is_linked() -> None:
    """⚠ 既定は寄せない（ADR-0033）。

    条件の ``email_verified`` は、自前 idp (assay) では「テナント管理者がそう
    主張している」であって本人の証明ではない。既定で開けておくと、意味の食い違いが
    そのまま乗っ取りの経路になる。

    ⚠ **このアプリは SSO で利用者を作らない**ので、倒すと「まだ結び付いていない人は
    SSO で入れない」になる（パスワードでは入れる）。開けるかは運用で決める。
    """
    assert AccountLinkingPolicy().may_link(_user("a@example.com")) is False


def test_links_only_on_a_verified_address() -> None:
    """開けていても、未検証のアドレスでは寄せない。

    名乗るだけで他人のアカウントへ入れてしまうため。
    """
    policy = AccountLinkingPolicy(link_by_email=True)

    assert policy.may_link(_user("a@example.com")) is True
    assert policy.may_link(_user("a@example.com", verified=False)) is False
