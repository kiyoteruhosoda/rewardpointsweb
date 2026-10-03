"""イベント（がんばりカード）を見る・作る・シールを貼る／はがす・消す（ADR-0042）。

見るのは台帳を見られる人（子ども本人も自分のカードを見る）。作る・貼る・はがす・
消すは台帳を変更できる人（親）だけ — 最後の 1 枚で台帳にポイントが入るので、
手で 1 行足せる人と同じ範囲に置く。

最後の 1 枚を貼ると、同じトランザクションで台帳へ達成の 1 行を足す。理由は
イベントの目標そのもの、記録した人は最後の 1 枚を貼った親。

期限（ADR-0043）の「今日」は家族の 1 日の区切り（毎日のボーナスと同じ
:class:`DayBoundary`）で決める。UTC の日付で切ると、日本の家族では朝 9 時に期限が切れる。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from bounded_contexts.reward_points.application.dto.reward_event_dto import (
    RewardEventBoardDTO,
    RewardEventDTO,
    to_dto,
)
from bounded_contexts.reward_points.application.family_access_resolver import FamilyAccessResolver
from bounded_contexts.reward_points.domain.entities.reward_event import RewardEvent
from bounded_contexts.reward_points.domain.exceptions import (
    MembershipNotFoundError,
    RewardEventCompletedError,
    RewardEventDeadlinePassedError,
    RewardEventNotFoundError,
)
from bounded_contexts.reward_points.domain.repositories.family_membership_repository import (
    IFamilyMembershipRepository,
)
from bounded_contexts.reward_points.domain.repositories.point_transaction_repository import (
    IPointTransactionRepository,
    NewTransaction,
)
from bounded_contexts.reward_points.domain.repositories.reward_event_repository import (
    IRewardEventRepository,
    NewRewardEvent,
)
from bounded_contexts.reward_points.domain.services import family_access_policy
from bounded_contexts.reward_points.domain.services.day_boundary import DayBoundary
from shared.kernel.timestamps import utcnow


class ViewRewardEventsUseCase:
    def __init__(
        self,
        *,
        access: FamilyAccessResolver,
        events: IRewardEventRepository,
        memberships: IFamilyMembershipRepository,
        boundary: DayBoundary,
    ) -> None:
        self._access = access
        self._events = events
        self._memberships = memberships
        self._boundary = boundary

    def execute(self, *, ledger_id: int, account_id: int) -> RewardEventBoardDTO:
        found = self._access.viewable_ledger(ledger_id=ledger_id, account_id=account_id)
        owner = self._memberships.find_by_id(found.ledger.membership_id)
        if owner is None:
            raise MembershipNotFoundError
        today = _today(self._boundary)
        return RewardEventBoardDTO(
            ledger_id=found.ledger.id,
            display_name=owner.display_name_value,
            can_modify=family_access_policy.can_modify_ledger(found.membership, found.ledger),
            events=tuple(to_dto(event, today=today) for event in self._events.list_by_ledger(found.ledger.id)),
        )


@dataclass(frozen=True, kw_only=True)
class CreateRewardEventCommand:
    ledger_id: int
    account_id: int
    title: str
    reward_points: int
    goal_count: int
    deadline: date | None


class CreateRewardEventUseCase:
    def __init__(self, access: FamilyAccessResolver, events: IRewardEventRepository, boundary: DayBoundary) -> None:
        self._access = access
        self._events = events
        self._boundary = boundary

    def execute(self, command: CreateRewardEventCommand) -> RewardEventDTO:
        found = self._access.modifiable_ledger(ledger_id=command.ledger_id, account_id=command.account_id)
        today = _today(self._boundary)
        _ensure_not_passed(command.deadline, today=today)
        event = self._events.add(
            NewRewardEvent(
                ledger_id=found.ledger.id,
                title=command.title,
                reward=command.reward_points,
                goal_count=command.goal_count,
                deadline=command.deadline,
            )
        )
        return to_dto(event, today=today)


@dataclass(frozen=True, kw_only=True)
class ChangeDeadlineCommand:
    ledger_id: int
    event_id: int
    account_id: int
    #: ``None`` で期限なし
    deadline: date | None


class ChangeRewardEventDeadlineUseCase:
    """期限を決め直す・外す。期限切れのカードも、延ばせばまた貼れる。

    達成したカードの期限は動かさない（もう期限の意味が無い）。
    """

    def __init__(self, access: FamilyAccessResolver, events: IRewardEventRepository, boundary: DayBoundary) -> None:
        self._access = access
        self._events = events
        self._boundary = boundary

    def execute(self, command: ChangeDeadlineCommand) -> RewardEventDTO:
        found = self._access.modifiable_ledger(ledger_id=command.ledger_id, account_id=command.account_id)
        event = _find(self._events, ledger_id=found.ledger.id, event_id=command.event_id)
        if event.is_completed:
            raise RewardEventCompletedError
        today = _today(self._boundary)
        _ensure_not_passed(command.deadline, today=today)
        self._events.change_deadline(event_id=event.id, deadline=command.deadline)
        return to_dto(_find(self._events, ledger_id=found.ledger.id, event_id=event.id), today=today)


@dataclass(frozen=True, kw_only=True)
class StickerCommand:
    ledger_id: int
    event_id: int
    account_id: int
    #: 貼る（はがす）シールの番号。1 から始まる
    number: int


class StickRewardEventStickerUseCase:
    """*number* 枚目を貼る。マスが埋まったら台帳へ達成の 1 行を足す。

    同じ番号がもう貼られていれば何もせず、今の姿を返す（同じ押下の再送）。
    """

    def __init__(
        self,
        *,
        access: FamilyAccessResolver,
        events: IRewardEventRepository,
        transactions: IPointTransactionRepository,
        boundary: DayBoundary,
    ) -> None:
        self._access = access
        self._events = events
        self._transactions = transactions
        self._boundary = boundary

    def execute(self, command: StickerCommand) -> RewardEventDTO:
        found = self._access.modifiable_ledger(ledger_id=command.ledger_id, account_id=command.account_id)
        event = _find(self._events, ledger_id=found.ledger.id, event_id=command.event_id)
        now = utcnow()
        today = self._boundary.day_of(now)
        if not event.should_stick(command.number, today=today):
            return to_dto(event, today=today)
        stuck = self._events.stick(
            event_id=event.id,
            number=command.number,
            stuck_at=now,
            stuck_by_membership_id=found.membership.id,
        )
        # 同じ番号を同時に貼った相手が勝っていれば、達成の後始末も向こうが行う
        if stuck and event.completes_with(command.number):
            awarded = self._transactions.append(
                NewTransaction(
                    ledger_id=found.ledger.id,
                    amount=event.reward.value,
                    reason=event.title.value,
                    granted_by_membership_id=found.membership.id,
                    occurred_at=now,
                    idempotency_key=event.award_key,
                )
            )
            self._events.mark_completed(event_id=event.id, completed_at=now, awarded_transaction_id=awarded.id)
        return to_dto(_find(self._events, ledger_id=found.ledger.id, event_id=event.id), today=today)


class PeelRewardEventStickerUseCase:
    """最後の 1 枚をはがす（押し間違いを戻す）。もう無い番号なら何もしない。"""

    def __init__(self, access: FamilyAccessResolver, events: IRewardEventRepository, boundary: DayBoundary) -> None:
        self._access = access
        self._events = events
        self._boundary = boundary

    def execute(self, command: StickerCommand) -> RewardEventDTO:
        found = self._access.modifiable_ledger(ledger_id=command.ledger_id, account_id=command.account_id)
        event = _find(self._events, ledger_id=found.ledger.id, event_id=command.event_id)
        if event.should_peel(command.number):
            self._events.peel(event_id=event.id, number=command.number)
            event = _find(self._events, ledger_id=found.ledger.id, event_id=event.id)
        return to_dto(event, today=_today(self._boundary))


class DeleteRewardEventUseCase:
    """イベントを消す。達成で足したポイントは台帳に残る（台帳は追記専用。ADR-0010）。

    もう無いイベントでも成功させる（消したいという求めは満たされている）。
    """

    def __init__(self, access: FamilyAccessResolver, events: IRewardEventRepository) -> None:
        self._access = access
        self._events = events

    def execute(self, *, ledger_id: int, event_id: int, account_id: int) -> None:
        found = self._access.modifiable_ledger(ledger_id=ledger_id, account_id=account_id)
        if self._events.find_in_ledger(ledger_id=found.ledger.id, event_id=event_id) is not None:
            self._events.delete(event_id)


def _today(boundary: DayBoundary) -> date:
    return boundary.day_of(utcnow())


def _ensure_not_passed(deadline: date | None, *, today: date) -> None:
    """過ぎた日は期限にできない（作った瞬間に期限切れのカードになる）。今日は良い。"""
    if deadline is not None and deadline < today:
        raise RewardEventDeadlinePassedError


def _find(events: IRewardEventRepository, *, ledger_id: int, event_id: int) -> RewardEvent:
    event = events.find_in_ledger(ledger_id=ledger_id, event_id=event_id)
    if event is None:
        raise RewardEventNotFoundError
    return event


__all__ = [
    "ChangeDeadlineCommand",
    "ChangeRewardEventDeadlineUseCase",
    "CreateRewardEventCommand",
    "CreateRewardEventUseCase",
    "DeleteRewardEventUseCase",
    "PeelRewardEventStickerUseCase",
    "StickRewardEventStickerUseCase",
    "StickerCommand",
    "ViewRewardEventsUseCase",
]
