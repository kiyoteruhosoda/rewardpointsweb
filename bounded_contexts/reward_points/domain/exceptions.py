"""Domain exceptions of the reward_points context.

The Presentation layer converts them to HTTP status + error code (conversion to display
text happens in the frontend; see the i18n section of CLAUDE.md).
"""

from __future__ import annotations


class RewardPointsError(Exception):
    """Base exception of this context. ``code`` becomes the API error code as-is."""

    code = "reward_points_error"


class FamilyNotFoundError(RewardPointsError):
    """The family itself does not exist.

    "Not a member" is :class:`FamilyAccessDeniedError`, not this. Processing stops as soon as
    the membership cannot be found, so callers cannot tell existence from non-membership.
    This one is raised only in the broken state where the membership was found but the
    family row is missing.
    """

    code = "family_not_found"


class FamilyAccessDeniedError(RewardPointsError):
    """A member of the family, but not in a role allowed to perform the operation."""

    code = "family_access_denied"


class MembershipNotFoundError(RewardPointsError):
    """The member does not exist (including when pointing at another family's member)."""

    code = "membership_not_found"


class LedgerNotFoundError(RewardPointsError):
    """The ledger does not exist, or the caller is not in a role allowed to view it."""

    code = "ledger_not_found"


class TransactionNotFoundError(RewardPointsError):
    """The transaction does not exist (including when pointing at another ledger's)."""

    code = "transaction_not_found"


class TransactionAlreadyReversedError(RewardPointsError):
    """Attempted to reverse a transaction that is already reversed."""

    code = "transaction_already_reversed"


class ReversalOfReversalError(RewardPointsError):
    """Attempted to reverse a reversal record itself (forbidden by ADR-0010)."""

    code = "reversal_of_reversal_not_allowed"


class CorrectionOfReversalError(RewardPointsError):
    """Attempted to correct a reversal record itself (ADR-0022).

    A correction is a "reverse and rewrite" operation, and neither can be applied to a
    reversal row. What one wants to fix is the reversed original row, which is already
    reversed, so the correct content is added as a new record.
    """

    code = "correction_of_reversal_not_allowed"


class IdempotencyKeyReusedError(RewardPointsError):
    """One idempotency key was also used for a different correction (ADR-0022).

    A correction writes two rows at once, so the key is split per step. Correcting a
    different record with the same key makes the split keys collide with the earlier
    correction's, leaving rows that were meant to be written unwritten. Rather than let it
    pass silently, the client is asked to generate a new key.
    """

    code = "idempotency_key_reused"


class InvitationNotFoundError(RewardPointsError):
    """The invitation code does not exist, has expired, or was already used.

    The three are not distinguished. Distinguishing them would give clues for brute-forcing
    valid codes.
    """

    code = "invitation_not_found"


class RoleNotInvitableError(RewardPointsError):
    """Specified a role that cannot be handed out by invitation (owner)."""

    code = "role_not_invitable"


class InvitationTargetUnavailableError(RewardPointsError):
    """The member the invitation points at is already linked to another account."""

    code = "invitation_target_unavailable"


class AccountAlreadyInFamilyError(RewardPointsError):
    """A member for that account already exists in the same family.

    The same invariant as ``UNIQUE (family_id, account_id)`` (ADR-0009).
    """

    code = "account_already_in_family"


class AlreadyBelongsToFamilyError(RewardPointsError):
    """An account already belonging to a family tried to create or join a family.

    An account can belong to at most one family (ADR-0013). Leave and return to the initial
    state first, then create a new one or accept an invitation again.
    """

    code = "already_belongs_to_family"


class ChildCannotLeaveFamilyError(RewardPointsError):
    """A ``role = child`` (guest) tried to leave the family on their own.

    Children cannot leave by themselves (ADR-0013). Changing the family's composition is the
    owner's job.
    """

    code = "child_cannot_leave_family"


class LastGuardianCannotLeaveError(RewardPointsError):
    """The last parent (owner / parent) tried to leave the family.

    Leaving is allowed only if another parent remains (ADR-0013). With no parents left,
    nobody could handle the remaining children's ledgers. A sole parent dissolves the family
    instead of leaving.
    """

    code = "last_guardian_cannot_leave"


class FamilyNotEmptyError(RewardPointsError):
    """Attempted to dissolve a family in which other members remain.

    A family cannot be dissolved while members (parents or children) remain (ADR-0013). No
    path may silently delete ledgers along with it (ADR-0010).
    """

    code = "family_not_empty"


class IndependenceNotProposedError(RewardPointsError):
    """A child tried to approve independence without it having been requested.

    Independence takes two steps: a request by a parent member and approval by the child
    (ADR-0014).
    """

    code = "independence_not_proposed"


class UsernameAlreadyTakenError(RewardPointsError):
    """The specified login ID is already in use."""

    code = "username_already_taken"


class ChildAccountRequiredError(RewardPointsError):
    """Attempted an operation only valid for ``role = child`` on a parent.

    Issuing temporary passwords (ADR-0011) and requesting independence (ADR-0014) are
    allowed only for child members.
    """

    code = "child_account_required"


class GuardianAccountRequiredError(RewardPointsError):
    """An account that cannot be a guardian (a child) tried to use a parent invitation.

    A child (guest role) joining as a parent would become a "guardian in name only": a parent
    in the family who can neither add children nor record points. A child becomes an adult
    via independence (ADR-0014) or an administrator's role change (ADR-0018).
    """

    code = "guardian_account_required"


class ChildInvitationRequiresSignupError(RewardPointsError):
    """Attempted to use a child invitation code via acceptance (accept) by an existing account.

    Child accounts are "newly born" when the invitation is redeemed (redeem — ADR-0011 /
    ADR-0018). Linking an existing account as a child would make the cleanup on removal
    (account deletion) take an independently existing account down with it.
    """

    code = "child_invitation_requires_signup"


class GuardianInvitationRequiresSignInError(RewardPointsError):
    """Attempted to use a parent invitation by creating a new account (redeem) when an IdP exists.

    With an IdP (SSO), an adult has only the one account created on IdP sign-in
    (ADR-0048). Creating another here leaves no clue to link it with the IdP account, so the
    same person would end up with two accounts. Parents sign in first and join via accept.
    """

    code = "guardian_invitation_requires_sign_in"


class DisplayNameRequiredError(RewardPointsError):
    """No display name was given for an invitation that needs one (not pointing at a member)."""

    code = "display_name_required"


class MembershipNotLinkedError(RewardPointsError):
    """An account-side operation was requested for a member not yet linked to an account."""

    code = "membership_not_linked"


class LedgerNotEmptyError(RewardPointsError):
    """Attempted to delete a member together with a ledger that still has records.

    Ledgers are append-only with no means of deletion (ADR-0010). Removing a member is also
    refused while records remain.
    """

    code = "ledger_not_empty"


class InvalidMemberOrderError(RewardPointsError):
    """The reorder request does not match the family's sortable members.

    Reordering only swaps positions; it neither adds nor removes members. A request with
    missing, duplicate or other-family members signals that the UI holds a stale list, so it
    is refused.
    """

    code = "invalid_member_order"


class InvalidFamilyArchiveError(RewardPointsError):
    """Attempted to import content that is inconsistent as an exported file (ADR-0026).

    The format itself (presence, types, lengths of fields) is rejected first by Pydantic.
    What is refused here is **internal consistency** — not exactly one owner, a ledger
    attached to a role without one, reversals/corrections pointing at records not yet
    written, and so on. The import is written in one transaction, so it is refused up front
    rather than noticed midway.

    Reasons are not broken down. People are not expected to fix broken files by hand, and
    even if split, the only remedy is "export again".
    """

    code = "invalid_family_archive"


class UnsupportedArchiveVersionError(RewardPointsError):
    """Attempted to import a file version this app cannot read (ADR-0026).

    Separate from :class:`InvalidFamilyArchiveError` because the remedy differs. It is not
    broken; it signals that **a file exported by a newer app was brought to an older app**,
    so what needs fixing is the app, not the file.
    """

    code = "unsupported_archive_version"


class UserStillOwnsFamiliesError(RewardPointsError):
    """An account still remaining as a family's owner cannot be deleted.

    Without the owner nobody could manage that family. Silently deleting it along with the
    account would lose the ledgers too, so the family must be dealt with first.
    """

    code = "user_still_owns_families"


class RewardEventNotFoundError(RewardPointsError):
    """The event does not exist (including when pointing at another ledger's; ADR-0042)."""

    code = "reward_event_not_found"


class RewardEventCompletedError(RewardPointsError):
    """Attempted to stick or peel a sticker on a completed event.

    On completion the points are already in the ledger. Moving stickers would not revert the
    ledger, so the card stays frozen as completed. To take points back, reverse the ledger
    record.
    """

    code = "reward_event_already_completed"


class RewardEventExpiredError(RewardPointsError):
    """Attempted to stick a sticker on an event past its deadline.

    To continue, a parent extends the deadline (once extended, stickers can be stuck again).
    """

    code = "reward_event_expired"


class RewardEventDeadlinePassedError(RewardPointsError):
    """Attempted to set a deadline that has already passed (today is allowed)."""

    code = "reward_event_deadline_passed"


class DisplayNotFoundError(RewardPointsError):
    """Display device not found (detached or unknown account; ADR-0047)."""

    code = "display_not_found"


class StickerOutOfOrderError(RewardPointsError):
    """Attempted to stick a sticker that is not the next number, or peel one that is not the last.

    The UI is looking at a stale state (e.g. stuck from another device). Reloading reveals the
    correct number.
    """

    code = "sticker_out_of_order"


__all__ = [
    "AccountAlreadyInFamilyError",
    "AlreadyBelongsToFamilyError",
    "ChildAccountRequiredError",
    "ChildCannotLeaveFamilyError",
    "ChildInvitationRequiresSignupError",
    "CorrectionOfReversalError",
    "DisplayNameRequiredError",
    "DisplayNotFoundError",
    "FamilyAccessDeniedError",
    "FamilyNotEmptyError",
    "FamilyNotFoundError",
    "GuardianAccountRequiredError",
    "GuardianInvitationRequiresSignInError",
    "IdempotencyKeyReusedError",
    "IndependenceNotProposedError",
    "InvalidFamilyArchiveError",
    "InvalidMemberOrderError",
    "InvitationNotFoundError",
    "InvitationTargetUnavailableError",
    "LastGuardianCannotLeaveError",
    "LedgerNotEmptyError",
    "LedgerNotFoundError",
    "MembershipNotFoundError",
    "MembershipNotLinkedError",
    "ReversalOfReversalError",
    "RewardEventCompletedError",
    "RewardEventDeadlinePassedError",
    "RewardEventExpiredError",
    "RewardEventNotFoundError",
    "RewardPointsError",
    "RoleNotInvitableError",
    "StickerOutOfOrderError",
    "TransactionAlreadyReversedError",
    "TransactionNotFoundError",
    "UnsupportedArchiveVersionError",
    "UserStillOwnsFamiliesError",
    "UsernameAlreadyTakenError",
]
