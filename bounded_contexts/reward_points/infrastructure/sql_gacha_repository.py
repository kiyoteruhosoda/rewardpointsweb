"""SQLAlchemy implementations of the gacha repositories (ADR-0060).

A draw locks the ledger row with ``SELECT ... FOR UPDATE`` before reading the balance, and
reads the balance and earlier draws with locking reads too. On MariaDB (InnoDB, REPEATABLE
READ) a locking read sees the latest committed rows rather than the transaction's snapshot,
so a second draw waiting on the lock sees the first one's spending once it commits. SQLite
ignores ``FOR UPDATE``; it serialises writers on its own.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from bounded_contexts.reward_points.domain.entities.gacha import Gacha, GachaDesign, GachaDraw, GachaPrize
from bounded_contexts.reward_points.domain.repositories.gacha_repository import (
    IGachaDrawRepository,
    IGachaRepository,
    NewGachaDraw,
)
from bounded_contexts.reward_points.infrastructure.reward_points_models import (
    GachaDrawModel,
    GachaModel,
    GachaPrizeModel,
    PointLedgerModel,
    PointTransactionModel,
)


class SqlGachaRepository(IGachaRepository):
    def __init__(self, session: Session) -> None:
        self._session = session

    def list_by_ledger(self, ledger_id: int) -> list[Gacha]:
        rows = self._session.scalars(
            select(GachaModel).where(GachaModel.ledger_id == ledger_id).order_by(GachaModel.id)
        ).all()
        return self._to_gachas(rows)

    def find_in_ledger(self, *, ledger_id: int, gacha_id: int) -> Gacha | None:
        row = self._session.scalar(
            select(GachaModel).where(GachaModel.id == gacha_id, GachaModel.ledger_id == ledger_id)
        )
        return self._to_gachas([row])[0] if row else None

    def add(self, *, ledger_id: int, design: GachaDesign) -> Gacha:
        row = GachaModel(ledger_id=ledger_id, name=design.name, price=design.price)
        self._session.add(row)
        self._session.flush()
        self._write_prizes(row.id, design)
        return self._to_gachas([row])[0]

    def replace_design(self, *, gacha_id: int, design: GachaDesign) -> None:
        row = self._session.get(GachaModel, gacha_id)
        if row is None:
            return
        row.name = design.name
        row.price = design.price
        self._session.execute(delete(GachaPrizeModel).where(GachaPrizeModel.gacha_id == gacha_id))
        self._write_prizes(gacha_id, design)

    def delete(self, gacha_id: int) -> None:
        self._session.execute(delete(GachaModel).where(GachaModel.id == gacha_id))

    def _write_prizes(self, gacha_id: int, design: GachaDesign) -> None:
        self._session.add_all(
            GachaPrizeModel(
                gacha_id=gacha_id, position=position, name=prize.name, weight=prize.weight, is_miss=prize.is_miss
            )
            for position, prize in enumerate(design.prizes)
        )
        self._session.flush()

    def _to_gachas(self, rows: Sequence[GachaModel]) -> list[Gacha]:
        """Fetch prizes in one query regardless of the number of machines."""
        prizes: dict[int, list[GachaPrize]] = defaultdict(list)
        if rows:
            for prize in self._session.scalars(
                select(GachaPrizeModel)
                .where(GachaPrizeModel.gacha_id.in_([row.id for row in rows]))
                .order_by(GachaPrizeModel.gacha_id, GachaPrizeModel.position)
            ):
                prizes[prize.gacha_id].append(GachaPrize(name=prize.name, weight=prize.weight, is_miss=prize.is_miss))
        return [
            Gacha(
                id=row.id,
                ledger_id=row.ledger_id,
                design=GachaDesign(name=row.name, price=row.price, prizes=tuple(prizes[row.id])),
                created_at=row.created_at,
            )
            for row in rows
        ]


class SqlGachaDrawRepository(IGachaDrawRepository):
    def __init__(self, session: Session) -> None:
        self._session = session

    def lock_ledger_balance(self, ledger_id: int) -> int:
        self._session.execute(select(PointLedgerModel.id).where(PointLedgerModel.id == ledger_id).with_for_update())
        # Sum in Python: a locking read is what sees the latest rows, and FOR UPDATE does not
        # combine with aggregates on every database
        amounts = self._session.scalars(
            select(PointTransactionModel.amount).where(PointTransactionModel.ledger_id == ledger_id).with_for_update()
        ).all()
        return sum(amounts)

    def find_by_key(self, *, ledger_id: int, idempotency_key: str) -> GachaDraw | None:
        row = self._session.scalar(
            select(GachaDrawModel)
            .where(GachaDrawModel.ledger_id == ledger_id, GachaDrawModel.idempotency_key == idempotency_key)
            .with_for_update()
        )
        return _to_draw(row) if row else None

    def add(self, new_draw: NewGachaDraw) -> GachaDraw:
        row = GachaDrawModel(
            ledger_id=new_draw.ledger_id,
            gacha_id=new_draw.gacha_id,
            gacha_name=new_draw.gacha_name,
            prize_name=new_draw.prize_name,
            is_miss=new_draw.is_miss,
            price=new_draw.price,
            idempotency_key=new_draw.idempotency_key,
            transaction_id=new_draw.transaction_id,
            drawn_by_membership_id=new_draw.drawn_by_membership_id,
            drawn_at=new_draw.drawn_at,
        )
        self._session.add(row)
        self._session.flush()
        return _to_draw(row)

    def list_recent(self, *, ledger_id: int, limit: int) -> list[GachaDraw]:
        rows = self._session.scalars(
            select(GachaDrawModel)
            .where(GachaDrawModel.ledger_id == ledger_id)
            .order_by(GachaDrawModel.drawn_at.desc(), GachaDrawModel.id.desc())
            .limit(limit)
        ).all()
        return [_to_draw(row) for row in rows]

    def find_in_ledger(self, *, ledger_id: int, draw_id: int) -> GachaDraw | None:
        row = self._session.scalar(
            select(GachaDrawModel).where(GachaDrawModel.id == draw_id, GachaDrawModel.ledger_id == ledger_id)
        )
        return _to_draw(row) if row else None

    def set_handed_over(self, *, draw_id: int, handed_over_at: datetime | None, by_membership_id: int | None) -> None:
        row = self._session.get(GachaDrawModel, draw_id)
        if row is None:
            return
        row.handed_over_at = handed_over_at
        row.handed_over_by_membership_id = by_membership_id
        self._session.flush()


def _to_draw(row: GachaDrawModel) -> GachaDraw:
    return GachaDraw(
        id=row.id,
        ledger_id=row.ledger_id,
        gacha_id=row.gacha_id,
        gacha_name=row.gacha_name,
        prize_name=row.prize_name,
        is_miss=row.is_miss,
        price=row.price,
        drawn_at=row.drawn_at,
        handed_over_at=row.handed_over_at,
    )


__all__ = ["SqlGachaDrawRepository", "SqlGachaRepository"]
