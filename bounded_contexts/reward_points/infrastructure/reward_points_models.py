"""SQLAlchemy models of the reward_points context.

Imported from ``migrations/env.py`` so that Alembic can see them.
Roles are stored without a DB-native ENUM, using ``native_enum=False`` (VARCHAR with a
CHECK constraint) (see the DB modeling section of CLAUDE.md).

``point_transactions`` is append-only (ADR-0010). It has no ``updated_at`` so the schema
itself shows that updates are not expected. Input mistakes are expressed with two rows:
``reversal_of_id`` (reversal) and ``corrects_id`` (the corrected restatement)
(ADR-0022).
"""

from __future__ import annotations

from datetime import date

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from shared.infrastructure.models.base import BigIntPk, utcnow
from shared.kernel.database.db import Base

FAMILY_ROLE = sa.Enum("owner", "parent", "child", "display", name="family_role", native_enum=False)


class FamilyModel(Base):
    __tablename__ = "families"

    id: Mapped[int] = mapped_column(BigIntPk, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(sa.String(100), nullable=False)
    # Rules agreed in the family (ADR-0027). NULL if unwritten (never an empty string)
    rules: Mapped[str | None] = mapped_column(sa.Text(), nullable=True)
    created_at = mapped_column(sa.DateTime(), nullable=False, default=utcnow)
    updated_at = mapped_column(sa.DateTime(), nullable=False, default=utcnow, onupdate=utcnow)


class FamilyMembershipModel(Base):
    __tablename__ = "family_memberships"
    __table_args__ = (
        # One membership per account within a Family (ADR-0009).
        # account_id may be NULL (a child just created by a parent is not linked yet).
        # NULLs do not collide, so any number of unlinked members can coexist.
        sa.UniqueConstraint("family_id", "account_id", name="uq_family_memberships_family_account"),
    )

    id: Mapped[int] = mapped_column(BigIntPk, primary_key=True, autoincrement=True)
    family_id: Mapped[int] = mapped_column(
        BigIntPk, sa.ForeignKey("families.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Keep the membership and ledger even if the account is deleted (only the login link goes)
    account_id: Mapped[int | None] = mapped_column(
        BigIntPk, sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    role: Mapped[str] = mapped_column(FAMILY_ROLE, nullable=False)
    display_name: Mapped[str] = mapped_column(sa.String(100), nullable=False)
    # When a parent member requested independence (ADR-0014). Established on the child's approval.
    # Always NULL unless role = child.
    independence_proposed_at = mapped_column(sa.DateTime(), nullable=True)
    # Sort order chosen by the family (smaller first). Effective only within the same role
    display_order: Mapped[int] = mapped_column(sa.Integer(), nullable=False, default=0, server_default="0")
    created_at = mapped_column(sa.DateTime(), nullable=False, default=utcnow)
    updated_at = mapped_column(sa.DateTime(), nullable=False, default=utcnow, onupdate=utcnow)


class PointLedgerModel(Base):
    __tablename__ = "point_ledgers"

    id: Mapped[int] = mapped_column(BigIntPk, primary_key=True, autoincrement=True)
    family_id: Mapped[int] = mapped_column(
        BigIntPk, sa.ForeignKey("families.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # One-to-one with a role = child membership (ADR-0009)
    membership_id: Mapped[int] = mapped_column(
        BigIntPk,
        sa.ForeignKey("family_memberships.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    created_at = mapped_column(sa.DateTime(), nullable=False, default=utcnow)


class PointTransactionModel(Base):
    __tablename__ = "point_transactions"
    __table_args__ = (
        # A double tap on the submit button must not register twice (ADR-0010)
        sa.UniqueConstraint("ledger_id", "idempotency_key", name="uq_point_transactions_idempotency"),
        # Prevent reversing the same record twice with a DB constraint
        sa.UniqueConstraint("reversal_of_id", name="uq_point_transactions_reversal_of"),
        # Do not let the same record be restated twice. A correction always comes with a
        # reversal so the UNIQUE above already stops it, but the table itself keeps it 1:1
        sa.UniqueConstraint("corrects_id", name="uq_point_transactions_corrects"),
        sa.CheckConstraint("amount <> 0", name="ck_point_transactions_amount_nonzero"),
        sa.Index("ix_point_transactions_ledger_occurred", "ledger_id", "occurred_at", "id"),
    )

    id: Mapped[int] = mapped_column(BigIntPk, primary_key=True, autoincrement=True)
    ledger_id: Mapped[int] = mapped_column(
        BigIntPk, sa.ForeignKey("point_ledgers.id", ondelete="CASCADE"), nullable=False
    )
    # Signed. Additions are positive, spending negative
    amount: Mapped[int] = mapped_column(sa.Integer(), nullable=False)
    reason: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    # Keep records even if the acting member leaves the family (history belongs to the ledger)
    granted_by_membership_id: Mapped[int | None] = mapped_column(
        BigIntPk, sa.ForeignKey("family_memberships.id", ondelete="SET NULL"), nullable=True
    )
    # The event time (can be entered retroactively) differs from the record creation time
    occurred_at = mapped_column(sa.DateTime(), nullable=False)
    created_at = mapped_column(sa.DateTime(), nullable=False, default=utcnow)
    reversal_of_id: Mapped[int | None] = mapped_column(BigIntPk, sa.ForeignKey("point_transactions.id"), nullable=True)
    # For a corrected row, the ID of the row it restates (ADR-0022). ON DELETE SET NULL so
    # deleting a whole ledger (independence; ADR-0014) is not refused due to deletion order.
    corrects_id: Mapped[int | None] = mapped_column(
        BigIntPk, sa.ForeignKey("point_transactions.id", ondelete="SET NULL"), nullable=True
    )
    idempotency_key: Mapped[str] = mapped_column(sa.String(64), nullable=False)


class DailyBonusModel(Base):
    """An arrangement to add to a ledger daily (ADR-0024).

    One per ledger. Deleted along with the ledger (family dissolution, member removal,
    independence). The last granted day is kept in ``granted_through``, so days when the
    app was down are caught up in bulk the next time it runs.
    """

    __tablename__ = "daily_bonuses"
    __table_args__ = (
        # A setting that decreases daily is not a "bonus" (spending is recorded by hand)
        sa.CheckConstraint("amount > 0", name="ck_daily_bonuses_amount_positive"),
    )

    id: Mapped[int] = mapped_column(BigIntPk, primary_key=True, autoincrement=True)
    ledger_id: Mapped[int] = mapped_column(
        BigIntPk,
        sa.ForeignKey("point_ledgers.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    amount: Mapped[int] = mapped_column(sa.Integer(), nullable=False)
    reason: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    # First day to grant (the day after it was set). Never goes back before this
    starts_on: Mapped[date] = mapped_column(sa.Date(), nullable=False)
    # Last day granted. NULL if not a single day has been granted yet
    granted_through: Mapped[date | None] = mapped_column(sa.Date(), nullable=True)
    created_at = mapped_column(sa.DateTime(), nullable=False, default=utcnow)
    updated_at = mapped_column(sa.DateTime(), nullable=False, default=utcnow, onupdate=utcnow)


class RewardEventModel(Base):
    """Effort card (ADR-0042).

    Any number per ledger. Deleted along with the ledger (family dissolution, member
    removal, independence). Once the slots are filled it holds ``completed_at`` and the row
    added to the ledger.
    """

    __tablename__ = "reward_events"
    __table_args__ = (
        sa.CheckConstraint("reward_points > 0", name="ck_reward_events_reward_positive"),
        sa.CheckConstraint("goal_count >= 1", name="ck_reward_events_goal_count_positive"),
    )

    id: Mapped[int] = mapped_column(BigIntPk, primary_key=True, autoincrement=True)
    ledger_id: Mapped[int] = mapped_column(
        BigIntPk, sa.ForeignKey("point_ledgers.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(sa.String(100), nullable=False)
    reward_points: Mapped[int] = mapped_column(sa.Integer(), nullable=False)
    goal_count: Mapped[int] = mapped_column(sa.Integer(), nullable=False)
    # Completed if filled by the end of this day (counted by the family's day boundary). NULL if none
    deadline: Mapped[date | None] = mapped_column(sa.Date(), nullable=True)
    completed_at = mapped_column(sa.DateTime(), nullable=True)
    # Ledger row added on completion. SET NULL because independence deletes ledger rows first
    awarded_transaction_id: Mapped[int | None] = mapped_column(
        BigIntPk, sa.ForeignKey("point_transactions.id", ondelete="SET NULL"), nullable=True
    )
    created_at = mapped_column(sa.DateTime(), nullable=False, default=utcnow)


class RewardEventStickerModel(Base):
    """One sticker stuck on an event (ADR-0042).

    ``number`` is a sequence number starting at 1. The same number cannot be stuck twice,
    so the same tap arriving twice results in only one sticker.
    """

    __tablename__ = "reward_event_stickers"
    __table_args__ = (
        sa.UniqueConstraint("event_id", "number", name="uq_reward_event_stickers_number"),
        sa.CheckConstraint("number >= 1", name="ck_reward_event_stickers_number_positive"),
    )

    id: Mapped[int] = mapped_column(BigIntPk, primary_key=True, autoincrement=True)
    event_id: Mapped[int] = mapped_column(
        BigIntPk, sa.ForeignKey("reward_events.id", ondelete="CASCADE"), nullable=False
    )
    number: Mapped[int] = mapped_column(sa.Integer(), nullable=False)
    stuck_at = mapped_column(sa.DateTime(), nullable=False)
    # Keep the sticker even if the member who stuck it leaves the family
    stuck_by_membership_id: Mapped[int | None] = mapped_column(
        BigIntPk, sa.ForeignKey("family_memberships.id", ondelete="SET NULL"), nullable=True
    )


class FamilyInvitationModel(Base):
    __tablename__ = "family_invitations"

    id: Mapped[int] = mapped_column(BigIntPk, primary_key=True, autoincrement=True)
    family_id: Mapped[int] = mapped_column(
        BigIntPk, sa.ForeignKey("families.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Plaintext is not stored (returned only once at issuance)
    code_hash: Mapped[str] = mapped_column(sa.String(64), unique=True, nullable=False)
    role: Mapped[str] = mapped_column(FAMILY_ROLE, nullable=False)
    # For role = child invitations, points at the member a parent created beforehand
    target_membership_id: Mapped[int | None] = mapped_column(
        BigIntPk, sa.ForeignKey("family_memberships.id", ondelete="CASCADE"), nullable=True
    )
    expires_at = mapped_column(sa.DateTime(), nullable=False)
    used_at = mapped_column(sa.DateTime(), nullable=True)
    created_at = mapped_column(sa.DateTime(), nullable=False, default=utcnow)


__all__ = [
    "FAMILY_ROLE",
    "DailyBonusModel",
    "FamilyInvitationModel",
    "FamilyMembershipModel",
    "FamilyModel",
    "PointLedgerModel",
    "PointTransactionModel",
    "RewardEventModel",
    "RewardEventStickerModel",
]
