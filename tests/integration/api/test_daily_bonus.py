"""毎日のボーナス（ADR-0024）。

設定の API は利用者と同じ道（HTTP）で確かめる。配る側は定期実行から呼ばれる
ものなので、ユースケースを直接呼び、``now`` を渡して日付を動かす。

日付は設定が返す ``starts_on``（決めた日）を基点に組み立てる。実行した日の
暦に寄りかかると、日が変わった瞬間に落ちるテストになる。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from bounded_contexts.reward_points.application.use_cases.grant_due_daily_bonuses import (
    GrantDueDailyBonusesUseCase,
    GrantedDailyBonuses,
)
from bounded_contexts.reward_points.domain.services.day_boundary import DayBoundary
from bounded_contexts.reward_points.infrastructure.sql_daily_bonus_repository import (
    SqlDailyBonusRepository,
)
from bounded_contexts.reward_points.infrastructure.sql_point_transaction_repository import (
    SqlPointTransactionRepository,
)
from tests.integration.api.family_support import (
    Account,
    Ledger,
    add_child,
    create_account,
    create_family,
    issue_invitation,
    login,
)

_TOKYO = ZoneInfo("Asia/Tokyo")


@dataclass(frozen=True, kw_only=True)
class Home:
    """親と、その子の台帳。

    どのテストも「親が子の台帳を触る」ところから始まるので 1 つにまとめる
    （引数を 3 つに収める意味もある。ADR-0016）。
    """

    parent: Account
    ledger: Ledger

    @property
    def headers(self) -> dict[str, str]:
        return self.parent.headers


@pytest.fixture
def home(client: TestClient, admin_headers: dict[str, str]) -> Home:
    parent = create_account(client, admin_headers, username="dad", role="member", display_name="おとうさん")
    family_id = create_family(client, parent.headers)
    child = add_child(client, parent.headers, family_id, display_name="たろう")
    return Home(parent=parent, ledger=Ledger(family_id=family_id, ledger_id=int(str(child["ledger_id"]))))


def _bonus_path(ledger: Ledger) -> str:
    return f"{ledger.path()}/daily-bonus"


def _configure(
    client: TestClient,
    headers: dict[str, str],
    ledger: Ledger,
    *,
    amount: int = 10,
    reason: str = "まいにちボーナス",
) -> dict[str, Any]:
    response = client.put(_bonus_path(ledger), headers=headers, json={"amount": amount, "reason": reason})
    assert response.status_code == 200, response.text
    body: dict[str, Any] = response.json()
    return body


def _starting_day(bonus: dict[str, Any]) -> date:
    return date.fromisoformat(str(bonus["starts_on"]))


def _noon(day: date, *, plus_days: int = 0) -> datetime:
    """その日の昼（UTC の naive datetime）。区切りをまたぐ心配のない時刻。"""
    return datetime.combine(day + timedelta(days=plus_days), time(12, 0))


def _view(client: TestClient, headers: dict[str, str], ledger: Ledger) -> dict[str, Any]:
    response = client.get(ledger.path(), headers=headers)
    assert response.status_code == 200, response.text
    body: dict[str, Any] = response.json()
    return body


def _grant(
    db_session: Session,
    *,
    now: datetime,
    catch_up_days: int = 31,
    boundary: DayBoundary | None = None,
) -> GrantedDailyBonuses:
    """定期実行の 1 周分。"""
    use_case = GrantDueDailyBonusesUseCase(
        bonuses=SqlDailyBonusRepository(db_session),
        transactions=SqlPointTransactionRepository(db_session),
        boundary=boundary or DayBoundary(UTC),
        max_catch_up_days=catch_up_days,
    )
    result = use_case.execute(now=now)
    db_session.commit()
    return result


# --- 設定 --------------------------------------------------------------------


def test_a_guardian_decides_how_many_points_arrive_each_day(client: TestClient, home: Home) -> None:
    bonus = _configure(client, home.headers, home.ledger, amount=10)

    assert bonus["amount"] == 10
    assert bonus["reason"] == "まいにちボーナス"
    assert bonus["granted_through"] is None
    # 決めただけでは台帳は動かない（配るのは日付の変わり目）
    assert _view(client, home.headers, home.ledger)["balance"] == 0


def test_the_setting_comes_back_with_the_ledger(client: TestClient, home: Home) -> None:
    """設定を出すためだけに 2 往復させない。"""
    assert _view(client, home.headers, home.ledger)["daily_bonus"] is None

    _configure(client, home.headers, home.ledger, amount=25)

    assert _view(client, home.headers, home.ledger)["daily_bonus"]["amount"] == 25


def test_deciding_again_replaces_the_amount(client: TestClient, home: Home) -> None:
    _configure(client, home.headers, home.ledger, amount=10)

    updated = _configure(client, home.headers, home.ledger, amount=30, reason="おこづかい")

    assert (updated["amount"], updated["reason"]) == (30, "おこづかい")
    assert _view(client, home.headers, home.ledger)["daily_bonus"]["amount"] == 30


def test_stopping_leaves_the_points_already_given(client: TestClient, home: Home, db_session: Session) -> None:
    start = _starting_day(_configure(client, home.headers, home.ledger, amount=10))
    _grant(db_session, now=_noon(start))

    response = client.delete(_bonus_path(home.ledger), headers=home.headers)

    assert response.status_code == 204
    body = _view(client, home.headers, home.ledger)
    assert body["daily_bonus"] is None
    assert body["balance"] == 10


def test_stopping_a_bonus_that_was_never_set_succeeds(client: TestClient, home: Home) -> None:
    """やめたいという求めはすでに満たされている。"""
    assert client.delete(_bonus_path(home.ledger), headers=home.headers).status_code == 204


def test_a_bonus_that_takes_points_away_is_rejected(client: TestClient, home: Home) -> None:
    response = client.put(_bonus_path(home.ledger), headers=home.headers, json={"amount": -10, "reason": "ばつ"})

    assert response.status_code == 422


def test_a_child_cannot_decide_their_own_bonus(client: TestClient, home: Home) -> None:
    """子は自分の台帳でも変更できない（``can_modify`` と同じ範囲）。"""
    child = add_child(client, home.headers, home.ledger.family_id, display_name="はなこ")
    invitation = issue_invitation(
        client,
        home.headers,
        home.ledger.family_id,
        role="child",
        target_membership_id=int(str(child["id"])),
    )
    redeemed = client.post(
        "/api/families/invitations/redeem",
        json={
            "code": invitation["code"],
            "username": "hanako",
            "password": "hanako-pass-123",
            "display_name": "はなこ",
        },
    )
    assert redeemed.status_code == 201, redeemed.text
    headers = login(client, username="hanako", password="hanako-pass-123")
    theirs = Ledger(family_id=home.ledger.family_id, ledger_id=int(str(child["ledger_id"])))

    response = client.put(_bonus_path(theirs), headers=headers, json={"amount": 100, "reason": "じぶんで"})

    assert response.status_code == 403


def test_another_familys_ledger_is_out_of_reach(client: TestClient, home: Home, admin_headers: dict[str, str]) -> None:
    outsider = create_account(client, admin_headers, username="mom", role="member")
    create_family(client, outsider.headers, name="よその家")

    response = client.put(_bonus_path(home.ledger), headers=outsider.headers, json={"amount": 10, "reason": "よそから"})

    assert response.status_code == 403


# --- 配る --------------------------------------------------------------------


def test_the_bonus_lands_once_a_day(client: TestClient, home: Home, db_session: Session) -> None:
    start = _starting_day(_configure(client, home.headers, home.ledger, amount=10))

    _grant(db_session, now=_noon(start))
    _grant(db_session, now=_noon(start, plus_days=1))

    body = _view(client, home.headers, home.ledger)
    assert body["balance"] == 20
    assert body["daily_bonus"]["granted_through"] == (start + timedelta(days=1)).isoformat()


def test_running_twice_in_the_same_day_adds_nothing(client: TestClient, home: Home, db_session: Session) -> None:
    """ワーカーが複数あっても、途中で落ちて再開しても 1 日 1 行。"""
    start = _starting_day(_configure(client, home.headers, home.ledger, amount=10))

    _grant(db_session, now=datetime.combine(start, time(1, 0)))
    result = _grant(db_session, now=datetime.combine(start, time(23, 0)))

    assert result.granted == 0
    assert _view(client, home.headers, home.ledger)["balance"] == 10


def test_days_missed_while_the_app_was_down_are_caught_up(client: TestClient, home: Home, db_session: Session) -> None:
    start = _starting_day(_configure(client, home.headers, home.ledger, amount=10))
    _grant(db_session, now=_noon(start))

    # 3 日止まってから起動した
    result = _grant(db_session, now=_noon(start, plus_days=3))

    assert result.granted == 3
    assert _view(client, home.headers, home.ledger)["balance"] == 40


def test_a_long_outage_is_capped_and_reported(client: TestClient, home: Home, db_session: Session) -> None:
    """久しぶりに開いた台帳が何百行ものボーナスで埋まらないようにする。"""
    start = _starting_day(_configure(client, home.headers, home.ledger, amount=10))

    result = _grant(db_session, now=_noon(start, plus_days=51), catch_up_days=3)

    assert (result.granted, result.skipped) == (3, 49)
    assert _view(client, home.headers, home.ledger)["balance"] == 30


def test_the_entry_says_nobody_recorded_it(client: TestClient, home: Home, db_session: Session) -> None:
    """誰の操作でもないので記録者は空。画面には「—」で並ぶ。"""
    start = _starting_day(_configure(client, home.headers, home.ledger, amount=10))
    _grant(db_session, now=_noon(start))

    entry = _view(client, home.headers, home.ledger)["transactions"][0]

    assert entry["granted_by"] is None
    assert entry["reason"] == "まいにちボーナス"
    # 出来事はその日の始まりに置く（追いついた分もそれぞれの日付に収まる）
    assert entry["occurred_at"] == f"{start.isoformat()}T00:00:00"


def test_a_stopped_bonus_stops_arriving(client: TestClient, home: Home, db_session: Session) -> None:
    start = _starting_day(_configure(client, home.headers, home.ledger, amount=10))
    _grant(db_session, now=_noon(start))
    assert client.delete(_bonus_path(home.ledger), headers=home.headers).status_code == 204

    result = _grant(db_session, now=_noon(start, plus_days=1))

    assert result.granted == 0
    assert _view(client, home.headers, home.ledger)["balance"] == 10


def test_changing_the_amount_does_not_re_give_the_days_already_granted(
    client: TestClient, home: Home, db_session: Session
) -> None:
    start = _starting_day(_configure(client, home.headers, home.ledger, amount=10))
    _grant(db_session, now=_noon(start))

    _configure(client, home.headers, home.ledger, amount=50)
    result = _grant(db_session, now=datetime.combine(start, time(20, 0)))

    assert result.granted == 0
    assert _view(client, home.headers, home.ledger)["balance"] == 10


def test_removing_the_child_takes_the_setting_with_it(client: TestClient, home: Home, db_session: Session) -> None:
    """台帳が消えれば設定も消える（残ると宛先の無い付与が回り続ける）。"""
    child = add_child(client, home.headers, home.ledger.family_id, display_name="じろう")
    theirs = Ledger(family_id=home.ledger.family_id, ledger_id=int(str(child["ledger_id"])))
    start = _starting_day(_configure(client, home.headers, theirs, amount=10))

    removed = client.delete(f"/api/families/{home.ledger.family_id}/memberships/{child['id']}", headers=home.headers)

    assert removed.status_code == 204
    assert _grant(db_session, now=_noon(start)).granted == 0


def test_the_day_boundary_follows_the_configured_time_zone(client: TestClient, home: Home, db_session: Session) -> None:
    """東京では、UTC の 15:30 はもう翌日。"""
    start = _starting_day(_configure(client, home.headers, home.ledger, amount=10))

    _grant(db_session, now=datetime.combine(start, time(15, 30)), boundary=DayBoundary(_TOKYO))

    granted_through = _view(client, home.headers, home.ledger)["daily_bonus"]["granted_through"]
    assert granted_through == (start + timedelta(days=1)).isoformat()


def test_nothing_arrives_before_the_day_it_was_decided(client: TestClient, home: Home, db_session: Session) -> None:
    """設定した日より前へは遡らない。"""
    start = _starting_day(_configure(client, home.headers, home.ledger, amount=10))

    assert _grant(db_session, now=_noon(start, plus_days=-1)).granted == 0
