"""reward_points の値オブジェクトが守る不変条件。"""

from __future__ import annotations

import pytest

from bounded_contexts.reward_points.domain.value_objects.display_name import DisplayName
from bounded_contexts.reward_points.domain.value_objects.family_name import FamilyName
from bounded_contexts.reward_points.domain.value_objects.family_role import FamilyRole
from bounded_contexts.reward_points.domain.value_objects.idempotency_key import IdempotencyKey
from bounded_contexts.reward_points.domain.value_objects.point_amount import MAX_MAGNITUDE, PointAmount
from bounded_contexts.reward_points.domain.value_objects.transaction_reason import TransactionReason


@pytest.mark.parametrize("amount", [1, -1, MAX_MAGNITUDE, -MAX_MAGNITUDE])
def test_non_zero_amounts_are_accepted(amount: int) -> None:
    assert PointAmount(amount).value == amount


def test_zero_is_rejected() -> None:
    """0 は台帳に意味を持たない（``CHECK (amount <> 0)`` と同じ規則）。"""
    with pytest.raises(ValueError, match="must not be zero"):
        PointAmount(0)


@pytest.mark.parametrize("amount", [MAX_MAGNITUDE + 1, -MAX_MAGNITUDE - 1])
def test_absurd_amounts_are_rejected(amount: int) -> None:
    with pytest.raises(ValueError, match="magnitude"):
        PointAmount(amount)


def test_negation_produces_the_opposite_sign() -> None:
    assert PointAmount(100).negated.value == -100
    assert PointAmount(-100).negated.value == 100


@pytest.mark.parametrize("factory", [FamilyName, DisplayName, TransactionReason, IdempotencyKey])
def test_blank_text_is_rejected(factory: type) -> None:
    with pytest.raises(ValueError, match="cannot be empty"):
        factory("   ")


def test_guardian_roles_are_owner_and_parent() -> None:
    assert FamilyRole.OWNER.is_guardian
    assert FamilyRole.PARENT.is_guardian
    assert not FamilyRole.CHILD.is_guardian


def test_only_children_own_a_ledger() -> None:
    assert FamilyRole.CHILD.has_own_ledger
    assert not FamilyRole.OWNER.has_own_ledger
    assert not FamilyRole.PARENT.has_own_ledger
