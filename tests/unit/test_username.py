"""ログイン識別子の正規化と検証（ADR-0011）。"""

from __future__ import annotations

import pytest

from shared.domain.auth.username import MAX_LENGTH, Username, normalize_username


def test_case_is_not_significant() -> None:
    """``Taro`` と ``taro`` が別アカウントとして並ばないようにする。"""
    assert Username("Taro").value == "taro"
    assert normalize_username("  ADMIN@Example.COM ") == "admin@example.com"


def test_existing_email_values_are_valid_identifiers() -> None:
    """移行で ``username`` にメールアドレスが入る（ADR-0011）。"""
    assert Username("admin@example.com").value == "admin@example.com"


@pytest.mark.parametrize("raw", ["ab", "  a  "])
def test_too_short_is_rejected(raw: str) -> None:
    with pytest.raises(ValueError, match="at least"):
        Username(raw)


def test_too_long_is_rejected() -> None:
    with pytest.raises(ValueError, match="cannot exceed"):
        Username("a" * (MAX_LENGTH + 1))


@pytest.mark.parametrize("raw", ["ta ro", "taro!", "たろう", "taro/1"])
def test_confusing_characters_are_rejected(raw: str) -> None:
    with pytest.raises(ValueError, match="may only contain"):
        Username(raw)
