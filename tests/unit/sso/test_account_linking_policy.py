"""Deciding whether it is OK to merge into an existing user."""

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
    """⚠ Not merged by default (ADR-0033).

    The ``email_verified`` condition, with our own idp (assay), means "the tenant admin
    claims so", not proof from the person. Leaving it open by default turns the mismatch in meaning
    straight into a takeover path.

    ⚠ **This app does not create users via SSO**, so turning it off means "people not yet linked
    cannot sign in via SSO" (they can with a password). Whether to open it is an operational decision.
    """
    assert AccountLinkingPolicy().may_link(_user("a@example.com")) is False


def test_links_only_on_a_verified_address() -> None:
    """Even when open, unverified addresses are not merged.

    Otherwise just claiming an address would let you into someone else's account.
    """
    policy = AccountLinkingPolicy(link_by_email=True)

    assert policy.may_link(_user("a@example.com")) is True
    assert policy.may_link(_user("a@example.com", verified=False)) is False
