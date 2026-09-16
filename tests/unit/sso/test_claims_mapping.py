"""ID トークンのクレーム -> 利用者の対応付け。"""

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
    """``"true"`` のような文字列を真として扱わない。

    検証済みかどうかは既存アカウントへ寄せてよいかの判断そのもの。IdP が
    文字列で返してきたときに黙って通すと、未検証のアドレスで他人のアカウントへ
    入れてしまう。
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
    """⚠ **メールアドレスは鍵ではない**（ADR-0038）。

    結び付きの鍵は ``sub`` なので、既に結び付いている相手はメールが無くても入れる。
    断るのは「初回に既存の利用者を探す」ときだけで、その判断は
    :class:`ResolveFederatedAccount` が持つ。
    """
    user = ClaimsMapping().apply({"sub": "s", "email": "   "})

    assert user.email is None
    assert user.email_domain == ""


def test_falls_back_to_the_subject_when_there_is_no_email_either() -> None:
    """名乗りの空いた利用者を作らないための最後の手（ADR-0038）。"""
    user = ClaimsMapping().apply({"sub": "idp-1"})

    assert user.display_name == "idp-1"


def test_reads_the_login_name_the_idp_uses() -> None:
    """口座を作るときの ``username`` の元（ADR-0041）。空白だけの値は「無い」と読む。"""
    named = ClaimsMapping().apply({"sub": "s", "preferred_username": " kyon "})
    blank = ClaimsMapping().apply({"sub": "s", "preferred_username": "  "})

    assert (named.preferred_username, blank.preferred_username) == ("kyon", None)
