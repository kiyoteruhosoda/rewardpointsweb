"""Authorization by position within the family (ADR-0009 authorization table)."""

from __future__ import annotations

from datetime import datetime

import pytest

from bounded_contexts.reward_points.domain.entities.family_membership import FamilyMembership
from bounded_contexts.reward_points.domain.entities.point_ledger import PointLedger
from bounded_contexts.reward_points.domain.services import family_access_policy
from bounded_contexts.reward_points.domain.value_objects.display_name import DisplayName
from bounded_contexts.reward_points.domain.value_objects.family_role import FamilyRole

_MOMENT = datetime(2026, 8, 1, 0, 0, 0)


def _membership(*, id: int, role: FamilyRole, family_id: int = 1, linked: bool = True) -> FamilyMembership:
    return FamilyMembership(
        id=id,
        family_id=family_id,
        account_id=id * 100 if linked else None,
        role=role,
        display_name=DisplayName("name"),
        created_at=_MOMENT,
    )


def _ledger(*, id: int, membership_id: int, family_id: int = 1) -> PointLedger:
    return PointLedger(id=id, family_id=family_id, membership_id=membership_id, created_at=_MOMENT)


@pytest.mark.parametrize("role", [FamilyRole.OWNER, FamilyRole.PARENT])
def test_guardians_see_and_modify_every_ledger(role: FamilyRole) -> None:
    guardian = _membership(id=1, role=role)
    ledger = _ledger(id=10, membership_id=2)

    assert family_access_policy.can_view_ledger(guardian, ledger)
    assert family_access_policy.can_modify_ledger(guardian, ledger)


def test_child_sees_only_its_own_ledger() -> None:
    child = _membership(id=2, role=FamilyRole.CHILD)

    assert family_access_policy.can_view_ledger(child, _ledger(id=10, membership_id=2))
    # A sibling's ledger is not visible
    assert not family_access_policy.can_view_ledger(child, _ledger(id=11, membership_id=3))


def test_child_never_modifies_a_ledger() -> None:
    child = _membership(id=2, role=FamilyRole.CHILD)

    assert not family_access_policy.can_modify_ledger(child, _ledger(id=10, membership_id=2))


def test_other_families_are_out_of_reach() -> None:
    owner = _membership(id=1, role=FamilyRole.OWNER, family_id=1)
    elsewhere = _ledger(id=10, membership_id=2, family_id=2)

    assert not family_access_policy.can_view_ledger(owner, elsewhere)
    assert not family_access_policy.can_modify_ledger(owner, elsewhere)


def test_only_the_owner_administers_the_family() -> None:
    assert family_access_policy.can_administer_family(_membership(id=1, role=FamilyRole.OWNER))
    assert not family_access_policy.can_administer_family(_membership(id=2, role=FamilyRole.PARENT))
    assert not family_access_policy.can_administer_family(_membership(id=3, role=FamilyRole.CHILD))


def test_both_guardians_create_children() -> None:
    for role in (FamilyRole.OWNER, FamilyRole.PARENT):
        assert family_access_policy.can_create_child(_membership(id=1, role=role))
    assert not family_access_policy.can_create_child(_membership(id=3, role=FamilyRole.CHILD))


def test_only_the_owner_invites_another_parent() -> None:
    """Bringing in a new adult "changes the family's makeup". Owner only, like removal."""
    assert family_access_policy.can_invite(_membership(id=1, role=FamilyRole.OWNER), FamilyRole.PARENT)
    assert not family_access_policy.can_invite(_membership(id=2, role=FamilyRole.PARENT), FamilyRole.PARENT)
    assert not family_access_policy.can_invite(_membership(id=3, role=FamilyRole.CHILD), FamilyRole.PARENT)


def test_both_guardians_hand_a_child_its_code() -> None:
    """A child invitation does not change who is in the family (ADR-0020). The parent who added them can give it."""
    for role in (FamilyRole.OWNER, FamilyRole.PARENT):
        assert family_access_policy.can_invite(_membership(id=1, role=role), FamilyRole.CHILD)
    assert not family_access_policy.can_invite(_membership(id=3, role=FamilyRole.CHILD), FamilyRole.CHILD)


def test_password_reset_targets_children_only() -> None:
    """Parent-to-parent resets are not allowed (ADR-0011)."""
    parent = _membership(id=1, role=FamilyRole.PARENT)
    child = _membership(id=2, role=FamilyRole.CHILD)
    other_parent = _membership(id=3, role=FamilyRole.OWNER)
    outsider = _membership(id=4, role=FamilyRole.CHILD, family_id=2)

    assert family_access_policy.can_reset_password_of(parent, child)
    assert not family_access_policy.can_reset_password_of(parent, other_parent)
    assert not family_access_policy.can_reset_password_of(parent, outsider)
    # A child cannot issue anyone's password
    assert not family_access_policy.can_reset_password_of(child, child)


def test_temporary_password_needs_an_account() -> None:
    """Even with the right position, there is nothing to issue to if the person has no account."""
    parent = _membership(id=1, role=FamilyRole.PARENT)
    unlinked = _membership(id=2, role=FamilyRole.CHILD, linked=False)

    assert family_access_policy.can_reset_password_of(parent, unlinked)
    assert not family_access_policy.can_issue_temporary_password_for(parent, unlinked)


def test_independence_targets_children_with_an_account() -> None:
    """Independence takes effect with the person's own approval. Children who cannot sign in are excluded (ADR-0014)."""
    parent = _membership(id=1, role=FamilyRole.PARENT)
    child = _membership(id=2, role=FamilyRole.CHILD)
    unlinked = _membership(id=3, role=FamilyRole.CHILD, linked=False)
    other_parent = _membership(id=4, role=FamilyRole.OWNER)

    assert family_access_policy.can_propose_independence_for(parent, child)
    assert not family_access_policy.can_propose_independence_for(parent, unlinked)
    assert not family_access_policy.can_propose_independence_for(parent, other_parent)
    assert not family_access_policy.can_propose_independence_for(child, child)


def test_removal_needs_the_owner_and_an_empty_ledger() -> None:
    """Participants with remaining records cannot be removed (ADR-0010). Nor can you remove yourself."""
    owner = _membership(id=1, role=FamilyRole.OWNER)
    parent = _membership(id=2, role=FamilyRole.PARENT)
    child = _membership(id=3, role=FamilyRole.CHILD)

    assert family_access_policy.can_remove_member(owner, child, ledger_is_empty=True)
    assert not family_access_policy.can_remove_member(owner, child, ledger_is_empty=False)
    assert not family_access_policy.can_remove_member(owner, owner, ledger_is_empty=True)
    assert not family_access_policy.can_remove_member(parent, child, ledger_is_empty=True)


def test_both_guardians_reorder_members() -> None:
    """Ordering is only about how things look, so any parent can change it."""
    for role in (FamilyRole.OWNER, FamilyRole.PARENT):
        assert family_access_policy.can_reorder_members(_membership(id=1, role=role))
    assert not family_access_policy.can_reorder_members(_membership(id=3, role=FamilyRole.CHILD))
