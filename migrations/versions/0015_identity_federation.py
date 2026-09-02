"""identity federation

外部 IdP（OpenID Connect）でのログインに要る 3 つの表を足す（ADR-0029）。

- ``federated_identities`` — IdP のアカウントと利用者の結び付き。鍵は
  ``(issuer, subject)``。利用者側には一意制約を置かない（1 人が複数の IdP
  アカウントを持てる）。
- ``sso_login_sessions`` — 認可要求の控え。複数ワーカーでは送り出したプロセスと
  戻り先のプロセスが一致しないため DB に置く。
- ``sso_login_tickets`` — コールバックが発行する 1 回限りの引き換え券
  （ハッシュのみ保存）。

利用者が消えたら結び付きも券も残す意味が無いので ``ON DELETE CASCADE``。
既存の利用者には行が入らないので、このリビジョンの前後で見え方は変わらない。

定義の正本は
``bounded_contexts/identity_federation/infrastructure/identity_federation_models.py``。

Revision ID: identity_federation
Revises: family_rules
Create Date: 2026-09-02

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "identity_federation"
down_revision = "family_rules"
branch_labels = None
depends_on = None

_BIGINT = sa.BigInteger().with_variant(sa.Integer(), "sqlite")


def upgrade() -> None:
    op.create_table(
        "federated_identities",
        sa.Column("issuer", sa.String(255), primary_key=True),
        sa.Column("subject", sa.String(255), primary_key=True),
        sa.Column("user_id", _BIGINT, nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("last_login_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_federated_identities_user_id", "federated_identities", ["user_id"])

    op.create_table(
        "sso_login_sessions",
        sa.Column("state", sa.String(64), primary_key=True),
        sa.Column("nonce", sa.String(64), nullable=False),
        sa.Column("code_verifier", sa.String(128), nullable=False),
        sa.Column("binding_hash", sa.String(64), nullable=False),
        sa.Column("redirect_to", sa.String(255), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    # 期限切れの掃除が毎回の発行で走る。期限で引ける索引を置く。
    op.create_index("ix_sso_login_sessions_expires_at", "sso_login_sessions", ["expires_at"])

    op.create_table(
        "sso_login_tickets",
        sa.Column("ticket_hash", sa.String(64), primary_key=True),
        sa.Column("user_id", _BIGINT, nullable=False),
        sa.Column("redirect_to", sa.String(255), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_sso_login_tickets_user_id", "sso_login_tickets", ["user_id"])
    op.create_index("ix_sso_login_tickets_expires_at", "sso_login_tickets", ["expires_at"])


def downgrade() -> None:
    # 索引は表と一緒に消える。外部キーが使う索引を先に落とすと MariaDB が拒む
    # （CLAUDE.md「DDL 管理」）
    op.drop_table("sso_login_tickets")
    op.drop_table("sso_login_sessions")
    op.drop_table("federated_identities")
