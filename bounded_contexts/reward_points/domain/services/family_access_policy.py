"""The single place deciding who reaches which ledger and which operation (ADR-0009).

To keep conditions from scattering across callers, every decision goes through the
functions in this module. Even if a requirement like "show only certain children to certain
members" arises, add a visibility table and change only the internals here.

A ledger is always tied one-to-one to a ``role = child`` member, so decisions depend on
just two things: "same family?" and "role".
"""

from __future__ import annotations

from bounded_contexts.reward_points.domain.entities.family_membership import FamilyMembership
from bounded_contexts.reward_points.domain.entities.point_ledger import PointLedger
from bounded_contexts.reward_points.domain.value_objects.family_role import FamilyRole


def can_view_ledger(membership: FamilyMembership, ledger: PointLedger) -> bool:
    """Parents and display devices can see every ledger of the family; a child only their own.

    Siblings cannot see each other's balances or history. Display devices only view (ADR-0047).
    """
    if not ledger.belongs_to_family(membership.family_id):
        return False
    if membership.role.sees_every_ledger:
        return True
    return ledger.membership_id == membership.id


def can_modify_ledger(membership: FamilyMembership, ledger: PointLedger) -> bool:
    """Whether one can add, spend and correct. A child cannot modify even their own ledger."""
    return ledger.belongs_to_family(membership.family_id) and membership.role.is_guardian


def can_administer_family(membership: FamilyMembership) -> bool:
    """Administering the family itself (renaming, removing members). Owner only."""
    return membership.role.can_administer_family


def can_edit_family_rules(membership: FamilyMembership) -> bool:
    """Whether one can rewrite the family rules (a memo of agreements). Parents can (ADR-0027).

    Unlike renaming or dissolving, it changes neither the family's composition nor ledgers.
    Rewriting daily agreements should not require calling the owner each time — it is
    treated like reordering children (:func:`can_reorder_members`), an operation that
    "tidies how the family looks".
    """
    return membership.role.is_guardian


def can_invite(membership: FamilyMembership, invited: FamilyRole) -> bool:
    """Whether one can issue an invitation code. Depends on the role being handed out (ADR-0020).

    **Invitations bringing a new person into the family (parent) are owner only.** The owner
    decides who joins this family, as it is an operation that "changes the family's
    composition", the counterpart of removal.

    **Invitations for an existing child can be issued by parents (owner / parent) too.** They
    only point at unlinked members the parents created themselves, so the line-up does not
    change — only "whether that child can log in as themselves" does. Parents are the ones
    who can create child memberships (:func:`can_create_child`), so if the creator could not
    hand over the login, the path would be broken.
    """
    if invited.has_own_ledger:
        return membership.role.is_guardian
    return membership.role.can_administer_family


def can_create_child(membership: FamilyMembership) -> bool:
    return membership.role.is_guardian


def can_reorder_members(membership: FamilyMembership) -> bool:
    """Whether one can change the members' order. Parents (owner / parent) can.

    Order is purely about appearance and changes neither composition nor ledgers. Counting it
    as "family administration" like removal or invitation would mean calling the owner just
    to tidy the everyday screen.
    """
    return membership.role.is_guardian


def can_propose_independence_for(actor: FamilyMembership, target: FamilyMembership) -> bool:
    """Whether one can request independence (ADR-0014).

    Only for children linked to an account. An unlinked child has no way to approve it, so
    that case is handled by :func:`can_remove_member` (removal).
    """
    return actor.role.is_guardian and target.role.has_own_ledger and target.is_linked


def can_remove_member(actor: FamilyMembership, target: FamilyMembership, *, ledger_is_empty: bool) -> bool:
    """Whether one can remove a member from the family.

    Only the owner can, and not themselves (nobody would be left to manage the family).
    Ledgers with records are never taken along (``ledger_not_empty``; ADR-0010), so an empty
    ledger is part of the condition — the UI never offers an operation refused after pressing.

    Display devices alone can be removed by any parent (owner / parent) (ADR-0047), so parents
    can see where their ledgers are shown and stop it on the spot.
    """
    if target.role.is_display:
        return can_detach_display(actor, target)
    return actor.role.can_administer_family and target.id != actor.id and ledger_is_empty


def can_detach_display(actor: FamilyMembership, target: FamilyMembership) -> bool:
    """Whether a display device can be detached from the family side. Parents of the same family can (ADR-0047)."""
    return actor.role.is_guardian and actor.family_id == target.family_id and target.role.is_display


def can_reset_password_of(actor: FamilyMembership, target: FamilyMembership) -> bool:
    """Whether one can issue a temporary password (ADR-0011).

    Parent-to-parent resets are not allowed. Limited to targets with ``role = child`` in the
    same family.
    """
    return (
        actor.role.is_guardian
        and actor.family_id == target.family_id
        and target.role.has_own_ledger
        and target.id != actor.id
    )


def can_issue_temporary_password_for(actor: FamilyMembership, target: FamilyMembership) -> bool:
    """Whether a temporary password can be issued right now (for UI display decisions).

    :func:`can_reset_password_of` plus "the person has an account". The role check (for whom
    it is allowed) and account presence (whether it is possible now) are refused for
    different reasons — the use case returns distinct error codes, and the UI shows the
    button only when both hold.
    """
    return can_reset_password_of(actor, target) and target.is_linked


__all__ = [
    "can_administer_family",
    "can_create_child",
    "can_detach_display",
    "can_edit_family_rules",
    "can_invite",
    "can_issue_temporary_password_for",
    "can_modify_ledger",
    "can_propose_independence_for",
    "can_remove_member",
    "can_reorder_members",
    "can_reset_password_of",
    "can_view_ledger",
]
