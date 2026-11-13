"""SQLAlchemy models specific to the example context.

Context-specific tables live in each context's infrastructure, not in
shared. Add an import to ``migrations/env.py`` so that Alembic can
detect them.
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from shared.infrastructure.models.base import BigIntPk
from shared.kernel.database.db import Base


class ItemModel(Base):
    __tablename__ = "items"

    id: Mapped[int] = mapped_column(BigIntPk, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(sa.String(255), nullable=False)


__all__ = ["ItemModel"]
