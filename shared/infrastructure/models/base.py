"""Types and functions shared by models.

- ``BigInteger`` for primary keys etc. uses ``with_variant(sa.Integer(), "sqlite")``
  to stay compatible with SQLite tests (CLAUDE.md "DB modeling").
- Times are always UTC (stored as naive datetime). Creation goes through
  :func:`shared.kernel.timestamps.utcnow`.
"""

from __future__ import annotations

import sqlalchemy as sa

from shared.kernel.timestamps import utcnow

BigIntPk = sa.BigInteger().with_variant(sa.Integer(), "sqlite")


__all__ = ["BigIntPk", "utcnow"]
