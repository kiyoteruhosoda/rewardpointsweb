"""表示端末コンテキストの SQLAlchemy モデル（ADR-0047）。

``migrations/env.py`` と ``tests/conftest.py`` がこのモジュールを import して
メタデータへ登録する（コンテキスト固有モデルの扱い。CLAUDE.md「DDL 管理」）。

確認コード・端末の秘密・端末の資格情報は、どれも SHA-256 のハッシュだけを置く。
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from shared.infrastructure.models.base import BigIntPk, utcnow
from shared.kernel.database.db import Base


class DisplayPairingRecord(Base):
    """ペアリング 1 回。期限切れの行は次に始めるときに消える（1 日残す）。"""

    __tablename__ = "display_pairings"

    id: Mapped[int] = mapped_column(BigIntPk, primary_key=True, autoincrement=True)
    user_code_hash: Mapped[str] = mapped_column(sa.String(64), unique=True, nullable=False)
    device_code_hash: Mapped[str] = mapped_column(sa.String(64), unique=True, nullable=False)
    expires_at = mapped_column(sa.DateTime(), nullable=False, index=True)
    created_at = mapped_column(sa.DateTime(), nullable=False, default=utcnow)
    # 承認で生まれた表示アカウント。承認前は NULL。アカウントが消えたら行も要らない
    approved_account_id: Mapped[int | None] = mapped_column(
        BigIntPk, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True
    )
    approved_at = mapped_column(sa.DateTime(), nullable=True)
    claimed_at = mapped_column(sa.DateTime(), nullable=True)


class DisplayCredentialRecord(Base):
    """端末の資格情報。1 表示アカウントに 1 つ。アカウントを消せば一緒に消える。"""

    __tablename__ = "display_credentials"

    account_id: Mapped[int] = mapped_column(BigIntPk, sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    credential_hash: Mapped[str] = mapped_column(sa.String(64), unique=True, nullable=False)
    created_at = mapped_column(sa.DateTime(), nullable=False, default=utcnow)
    last_used_at = mapped_column(sa.DateTime(), nullable=False, default=utcnow)


__all__ = ["DisplayCredentialRecord", "DisplayPairingRecord"]
