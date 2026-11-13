"""ID token claims -> user mapping."""

from __future__ import annotations

import pytest

from bounded_contexts.identity_federation.domain.exceptions import (
    InvalidIdTokenError,
)
from bounded_contexts.identity_federation.domain.value_objects.claims_mapping import (
    ClaimsMapping,
)


def test_reads_the_configured_claims() -> None:
    user = ClaimsMapping().apply({"sub": "idp-1", "email": "Parent@Example.com", "email_verified": True, "name": "親"})

    assert (user.subject, user.email, user.display_name) == ("idp-1", "parent@example.com", "親")
    assert user.email_verified is True


def test_email_verified_must_be_the_boolean_true() -> None:
    """Do not treat a string like ``"true"`` as true.

    Whether it is verified is the very decision of whether to merge into an existing account. If the IdP
    returns it as a string and it is silently accepted, an unverified address would get into someone
    else's account.
    """
    user = ClaimsMapping().apply({"sub": "idp-1", "email": "a@example.com", "email_verified": "true"})

    assert user.email_verified is False


def test_falls_back_to_other_name_claims_then_to_the_local_part() -> None:
    with_nickname = ClaimsMapping().apply({"sub": "s", "email": "a@example.com", "nickname": "ニック"})
    without_any = ClaimsMapping().apply({"sub": "s", "email": "someone@example.com"})

    assert with_nickname.display_name == "ニック"
    assert without_any.display_name == "someone"


def test_claim_names_can_be_remapped() -> None:
    mapping = ClaimsMapping(email_claim="mail", display_name_claim="full_name")

    user = mapping.apply({"sub": "s", "mail": "a@example.com", "full_name": "フル ネーム"})

    assert (user.email, user.display_name) == ("a@example.com", "フル ネーム")


def test_rejects_a_token_without_a_subject() -> None:
    with pytest.raises(InvalidIdTokenError):
        ClaimsMapping().apply({"email": "a@example.com"})


def test_an_absent_email_is_not_a_failure() -> None:
    """⚠ **The email address is not the key** (ADR-0038).

    The link key is ``sub``, so someone already linked can get in without an email.
    It is refused only when "looking up an existing user the first time", and that decision
    belongs to :class:`ResolveFederatedAccount`.
    """
    user = ClaimsMapping().apply({"sub": "s", "email": "   "})

    assert user.email is None
    assert user.email_domain == ""


def test_falls_back_to_the_subject_when_there_is_no_email_either() -> None:
    """The last resort against creating a user with no name (ADR-0038)."""
    user = ClaimsMapping().apply({"sub": "idp-1"})

    assert user.display_name == "idp-1"


def test_reads_the_login_name_the_idp_uses() -> None:
    """The source of ``username`` when creating an account (ADR-0041). A whitespace-only value is read as "none"."""
    named = ClaimsMapping().apply({"sub": "s", "preferred_username": " kyon "})
    blank = ClaimsMapping().apply({"sub": "s", "preferred_username": "  "})

    assert (named.preferred_username, blank.preferred_username) == ("kyon", None)
