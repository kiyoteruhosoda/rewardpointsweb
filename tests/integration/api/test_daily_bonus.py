"""Daily bonus (ADR-0024).

The settings API is checked through the same path users take (HTTP). Granting is
invoked by the periodic runner, so we call the use case directly and pass ``now`` to
move the date.

Dates are built from the ``starts_on`` (first grant day) returned by the settings.
Relying on the calendar of the day the test runs would make it fail right as the
date changes.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from bounded_contexts.reward_points.application.use_cases.grant_due_daily_bonuses import (
    GrantDueDailyBonusesUseCase,
    GrantedDailyBonuses,
)
from bounded_contexts.reward_points.domain.repositories.daily_bonus_repository import DailyBonusDraft
from bounded_contexts.reward_points.domain.services.day_boundary import DayBoundary
from bounded_contexts.reward_points.infrastructure.reward_points_models import DailyBonusModel
from bounded_contexts.reward_points.infrastructure.sql_daily_bonus_repository import (
    SqlDailyBonusRepository,
)
from bounded_contexts.reward_points.infrastructure.sql_point_transaction_repository import (
    SqlPointTransactionRepository,
)
from shared.kernel.timestamps import utcnow
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
    """A parent and their child's ledger.

    Every test starts from "a parent touches the child's ledger", so they are bundled
    into one (also keeps the arguments at three. ADR-0016).
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


def _member_of(client: TestClient, home: Home, *, display_name: str) -> dict[str, Any]:
    response = client.get(f"/api/families/{home.ledger.family_id}", headers=home.headers)
    assert response.status_code == 200, response.text
    found: dict[str, Any] = next(
        member for member in response.json()["memberships"] if member["display_name"] == display_name
    )
    return found


def _sign_in_as(client: TestClient, home: Home, *, membership: dict[str, Any], username: str) -> dict[str, str]:
    """Let the child log in as themselves (invitation code. ADR-0011)."""
    invitation = issue_invitation(
        client,
        home.headers,
        home.ledger.family_id,
        role="child",
        target_membership_id=int(str(membership["id"])),
    )
    password = f"{username}-pass-123"
    redeemed = client.post(
        "/api/families/invitations/redeem",
        json={"code": invitation["code"], "username": username, "password": password},
    )
    assert redeemed.status_code == 201, redeemed.text
    return login(client, username=username, password=password)


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
    """Noon of that day (naive UTC datetime). A time safely away from the day boundary."""
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
    """One round of the periodic runner."""
    use_case = GrantDueDailyBonusesUseCase(
        bonuses=SqlDailyBonusRepository(db_session),
        transactions=SqlPointTransactionRepository(db_session),
        boundary=boundary or DayBoundary(UTC),
        max_catch_up_days=catch_up_days,
    )
    result = use_case.execute(now=now)
    db_session.commit()
    return result


# --- Settings --------------------------------------------------------------


def test_a_guardian_decides_how_many_points_arrive_each_day(client: TestClient, home: Home) -> None:
    bonus = _configure(client, home.headers, home.ledger, amount=10)

    assert bonus["amount"] == 10
    assert bonus["reason"] == "まいにちボーナス"
    assert bonus["granted_through"] is None
    # Setting it alone does not touch the ledger (grants happen at the date change)
    assert _view(client, home.headers, home.ledger)["balance"] == 0


def test_the_setting_comes_back_with_the_ledger(client: TestClient, home: Home) -> None:
    """Do not require 2 round trips just to show the settings."""
    assert _view(client, home.headers, home.ledger)["daily_bonus"] is None

    _configure(client, home.headers, home.ledger, amount=25)

    assert _view(client, home.headers, home.ledger)["daily_bonus"]["amount"] == 25


def test_the_setting_comes_back_with_the_family(client: TestClient, home: Home) -> None:
    """It is set on the family settings screen, so it is also in the family details (ADR-0027).

    The amount may differ per child, so it belongs to each member, not the family.
    """
    hana = add_child(client, home.headers, home.ledger.family_id, display_name="はなこ")
    hana_ledger = Ledger(family_id=home.ledger.family_id, ledger_id=int(str(hana["ledger_id"])))
    _configure(client, home.headers, home.ledger, amount=25)
    _configure(client, home.headers, hana_ledger, amount=5)

    detail = client.get(f"/api/families/{home.ledger.family_id}", headers=home.headers)

    assert detail.status_code == 200, detail.text
    amounts = {
        member["display_name"]: (member["daily_bonus"] or {}).get("amount") for member in detail.json()["memberships"]
    }
    # Parents have no ledger, so they have no setting either
    assert amounts == {"おとうさん": None, "たろう": 25, "はなこ": 5}


def test_a_child_sees_only_their_own_setting_in_the_family(client: TestClient, home: Home) -> None:
    """Siblings' ledgers are not visible, so their settings are not returned either (ADR-0009)."""
    hana = add_child(client, home.headers, home.ledger.family_id, display_name="はなこ")
    hana_ledger = Ledger(family_id=home.ledger.family_id, ledger_id=int(str(hana["ledger_id"])))
    _configure(client, home.headers, home.ledger, amount=25)
    _configure(client, home.headers, hana_ledger, amount=5)
    taro = _member_of(client, home, display_name="たろう")
    child_headers = _sign_in_as(client, home, membership=taro, username="taro")

    detail = client.get(f"/api/families/{home.ledger.family_id}", headers=child_headers)

    assert detail.status_code == 200, detail.text
    bonuses = {member["display_name"]: member["daily_bonus"] is not None for member in detail.json()["memberships"]}
    assert bonuses == {"おとうさん": False, "たろう": True, "はなこ": False}


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
    """The request to stop is already satisfied."""
    assert client.delete(_bonus_path(home.ledger), headers=home.headers).status_code == 204


def test_a_bonus_that_takes_points_away_is_rejected(client: TestClient, home: Home) -> None:
    response = client.put(_bonus_path(home.ledger), headers=home.headers, json={"amount": -10, "reason": "ばつ"})

    assert response.status_code == 422


def test_a_child_cannot_decide_their_own_bonus(client: TestClient, home: Home) -> None:
    """A child cannot change it even on their own ledger (same scope as ``can_modify``)."""
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


# --- Granting --------------------------------------------------------------


def test_the_bonus_lands_once_a_day(client: TestClient, home: Home, db_session: Session) -> None:
    start = _starting_day(_configure(client, home.headers, home.ledger, amount=10))

    _grant(db_session, now=_noon(start))
    _grant(db_session, now=_noon(start, plus_days=1))

    body = _view(client, home.headers, home.ledger)
    assert body["balance"] == 20
    assert body["daily_bonus"]["granted_through"] == (start + timedelta(days=1)).isoformat()


def test_running_twice_in_the_same_day_adds_nothing(client: TestClient, home: Home, db_session: Session) -> None:
    """One row per day, even with multiple workers or a crash and restart midway."""
    start = _starting_day(_configure(client, home.headers, home.ledger, amount=10))

    _grant(db_session, now=datetime.combine(start, time(1, 0)))
    result = _grant(db_session, now=datetime.combine(start, time(23, 0)))

    assert result.granted == 0
    assert _view(client, home.headers, home.ledger)["balance"] == 10


def test_days_missed_while_the_app_was_down_are_caught_up(client: TestClient, home: Home, db_session: Session) -> None:
    start = _starting_day(_configure(client, home.headers, home.ledger, amount=10))
    _grant(db_session, now=_noon(start))

    # Started after being stopped for 3 days
    result = _grant(db_session, now=_noon(start, plus_days=3))

    assert result.granted == 3
    assert _view(client, home.headers, home.ledger)["balance"] == 40


def test_a_long_outage_is_capped_and_reported(client: TestClient, home: Home, db_session: Session) -> None:
    """Keep a ledger opened after a long time from being flooded with hundreds of bonus rows."""
    start = _starting_day(_configure(client, home.headers, home.ledger, amount=10))

    result = _grant(db_session, now=_noon(start, plus_days=51), catch_up_days=3)

    assert (result.granted, result.skipped) == (3, 49)
    assert _view(client, home.headers, home.ledger)["balance"] == 30


def test_the_entry_says_nobody_recorded_it(client: TestClient, home: Home, db_session: Session) -> None:
    """Nobody performed it, so the recorder is empty. The screen shows "—"."""
    start = _starting_day(_configure(client, home.headers, home.ledger, amount=10))
    _grant(db_session, now=_noon(start))

    entry = _view(client, home.headers, home.ledger)["transactions"][0]

    assert entry["granted_by"] is None
    assert entry["reason"] == "まいにちボーナス"
    # The event is placed at the start of its day (catch-up rows also land on their own dates).
    # The trailing Z is part of the contract (HANDOVER §14). Without it the browser reads local time.
    assert entry["occurred_at"] == f"{start.isoformat()}T00:00:00Z"


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
    """When the ledger goes, the setting goes too (otherwise grants with no target keep running)."""
    child = add_child(client, home.headers, home.ledger.family_id, display_name="じろう")
    theirs = Ledger(family_id=home.ledger.family_id, ledger_id=int(str(child["ledger_id"])))
    start = _starting_day(_configure(client, home.headers, theirs, amount=10))

    removed = client.delete(f"/api/families/{home.ledger.family_id}/memberships/{child['id']}", headers=home.headers)

    assert removed.status_code == 204
    assert _grant(db_session, now=_noon(start)).granted == 0


def test_the_day_boundary_follows_the_configured_time_zone(client: TestClient, home: Home, db_session: Session) -> None:
    """In Tokyo, 15:30 UTC is already the next day."""
    start = _starting_day(_configure(client, home.headers, home.ledger, amount=10))

    _grant(db_session, now=datetime.combine(start, time(15, 30)), boundary=DayBoundary(_TOKYO))

    granted_through = _view(client, home.headers, home.ledger)["daily_bonus"]["granted_through"]
    assert granted_through == (start + timedelta(days=1)).isoformat()


def test_nothing_arrives_before_the_starting_day(client: TestClient, home: Home, db_session: Session) -> None:
    """Never goes back before the start date."""
    start = _starting_day(_configure(client, home.headers, home.ledger, amount=10))

    assert _grant(db_session, now=_noon(start, plus_days=-1)).granted == 0


def test_nothing_arrives_on_the_day_it_was_decided(client: TestClient, home: Home, db_session: Session) -> None:
    """Nothing is granted on the day it is set.

    Granting from that day would make the outcome depend on the time of setting (set
    it late at night and 2 days' worth appear within minutes). It would also contradict
    the screen's "from the next date change".

    Checked with the real clock — only here we need "today as seen at the moment of
    setting", which built dates cannot reproduce.
    """
    decided_at = utcnow()
    _configure(client, home.headers, home.ledger, amount=10)

    assert _grant(db_session, now=decided_at).granted == 0


def test_a_row_made_outside_this_request_is_replaced_not_duplicated(
    client: TestClient, home: Home, db_session: Session
) -> None:
    """Even if a row already exists via another path, ``PUT`` goes through as a replacement.

    There is one per ledger (``UNIQUE (ledger_id)``), so trying to add a 2nd would hit
    the unique constraint. Losing the race when two first ``PUT`` requests arrive at once
    hits the same constraint; there ``SqlDailyBonusRepository._add_row`` re-reads the
    winning row and updates it (in-memory SQLite has only one connection, so that race
    itself cannot be reproduced here).
    """
    SqlDailyBonusRepository(db_session).save(
        DailyBonusDraft(ledger_id=home.ledger.ledger_id, amount=5, reason="さきに", starts_on=date(2026, 1, 1))
    )
    db_session.commit()

    saved = _configure(client, home.headers, home.ledger, amount=30, reason="あとから")

    assert (saved["amount"], saved["reason"]) == (30, "あとから")
    # The start date stays (fixing the amount must not move the starting point of grants)
    assert saved["starts_on"] == "2026-01-01"
    assert db_session.scalar(select(func.count()).select_from(DailyBonusModel)) == 1
