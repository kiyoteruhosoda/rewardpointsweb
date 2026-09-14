"""link round trip (連携の往復であることを控えに持たせる)

``sso_login_sessions`` に ``link_user_id`` を足す（ADR-0036）。入っていれば
**既に入っている利用者へ結び付けるための往復**、入っていなければログインの往復。

⚠ **外部キーは張らない。** この表は短命な控えで、利用者を消したときに道連れに
する対象ではない（消えた利用者の控えは期限で消える）。

⚠ **移行より前に始まった往復は ``NULL`` になる。** それはログインの往復なので
正しい ——連携が入る前の往復は必ずログインである。

Revision ID: link_round_trip
Revises: password_is_optional
Create Date: 2026-09-14

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "link_round_trip"
down_revision = "password_is_optional"
branch_labels = None
depends_on = None

_LINK_USER_ID = sa.Column(
    "link_user_id",
    sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
    nullable=True,
)


def upgrade() -> None:
    op.add_column("sso_login_sessions", _LINK_USER_ID)


def downgrade() -> None:
    op.drop_column("sso_login_sessions", "link_user_id")
