"""Whole-family archive — export and import (ADR-0026).

A backup is only worth something if it can be restored, so we check it with a round
trip. Import the exported JSON as is; the main criterion is that **exporting again
yields an archive identical to the original** (only the export time naturally
differs). Comparing individual fields alone would never catch a field that was left
out of the archive in the first place.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, time
from typing import Any

import pytest
from fastapi.testclient import TestClient
from httpx2 import Response
from sqlalchemy.orm import Session

from bounded_contexts.reward_points.application.use_cases.grant_due_daily_bonuses import (
    GrantDueDailyBonusesUseCase,
)
from bounded_contexts.reward_points.domain.services.day_boundary import DayBoundary
from bounded_contexts.reward_points.infrastructure.sql_daily_bonus_repository import (
    SqlDailyBonusRepository,
)
from bounded_contexts.reward_points.infrastructure.sql_point_transaction_repository import (
    SqlPointTransactionRepository,
)
from bounded_contexts.reward_points.presentation.schemas import MAX_ARCHIVED_TRANSACTIONS
from tests.integration.api.family_support import (
    Account,
    Ledger,
    add_child,
    create_account,
    create_family,
    issue_invitation,
)

Json = dict[str, Any]


def _export(client: TestClient, headers: dict[str, str], family_id: int) -> Json:
    response = client.get(f"/api/families/{family_id}/export", headers=headers)
    assert response.status_code == 200, response.text
    archive: Json = response.json()
    return archive


def _import(client: TestClient, headers: dict[str, str], archive: Json) -> Json:
    response = client.post("/api/families/import", headers=headers, json=archive)
    assert response.status_code == 201, response.text
    imported: Json = response.json()
    return imported


def _member(archive: Json, display_name: str) -> Json:
    found = [member for member in archive["members"] if member["display_name"] == display_name]
    assert len(found) == 1, archive["members"]
    entry: Json = found[0]
    return entry


@dataclass(frozen=True, kw_only=True)
class Backup:
    """An archive and the importer (a parent who does not belong to any family yet).

    Every import test starts from "this person imports this archive", so they are
    bundled into one (also keeps the arguments at three. ADR-0016).
    """

    client: TestClient
    guardian: Account
    archive: Json

    @property
    def headers(self) -> dict[str, str]:
        return self.guardian.headers

    def send(self, archive: Json | None = None) -> Response:
        return self.client.post(
            "/api/families/import", headers=self.headers, json=self.archive if archive is None else archive
        )

    def restore(self) -> Json:
        return _import(self.client, self.headers, self.archive)

    def view(self, family_id: int) -> Json:
        response = self.client.get(f"/api/families/{family_id}", headers=self.headers)
        assert response.status_code == 200, response.text
        detail: Json = response.json()
        return detail


@pytest.fixture
def guardian(client: TestClient, admin_headers: dict[str, str]) -> Account:
    """The importer. A parent who does not belong to any family yet."""
    return create_account(client, admin_headers, username="aunt", role="member", display_name="おば")


@pytest.fixture
def backup(client: TestClient, guardian: Account, family: Json) -> Backup:
    return Backup(client=client, guardian=guardian, archive=family)


@pytest.fixture
def family(client: TestClient, admin_headers: dict[str, str], db_session: Session) -> Json:
    """Archive of a family with 2 parents, 2 children and a full set of records.

    Includes reversals, corrections, the daily bonus and different recorders at once.
    If any one of them drops out of the archive, the round trip mismatches.
    """
    dad = create_account(client, admin_headers, username="dad", role="member", display_name="おとうさん")
    mom = create_account(client, admin_headers, username="mom", role="member", display_name="おかあさん")
    family_id = create_family(client, dad.headers, name="ほその家")

    rules = client.put(
        f"/api/families/{family_id}/rules",
        headers=dad.headers,
        json={"rules": "おてつだい 10 pt"},
    )
    assert rules.status_code == 200, rules.text

    invitation = issue_invitation(client, dad.headers, family_id, role="parent")
    accepted = client.post(
        "/api/families/invitations/accept",
        headers=mom.headers,
        json={"code": invitation["code"], "display_name": "おかあさん"},
    )
    assert accepted.status_code == 200, accepted.text

    taro = add_child(client, dad.headers, family_id, display_name="たろう")
    hana = add_child(client, dad.headers, family_id, display_name="はなこ")
    taro_ledger = Ledger(family_id=family_id, ledger_id=int(str(taro["ledger_id"])))
    hana_ledger = Ledger(family_id=family_id, ledger_id=int(str(hana["ledger_id"])))

    # Plain grants and spends, plus a reversal and a correction (ADR-0010 / ADR-0022)
    kept = taro_ledger.record(client, dad.headers, amount=10, reason="おてつだい", key="k1")
    taro_ledger.record(client, dad.headers, amount=-3, reason="おかし", key="k2")
    reversed_entry = taro_ledger.record(client, dad.headers, amount=50, reason="うちまちがい", key="k3")
    dropped = client.post(
        f"{taro_ledger.path()}/transactions/{reversed_entry['id']}/reversals",
        headers=dad.headers,
        json={"idempotency_key": "k4"},
    )
    assert dropped.status_code == 201, dropped.text
    corrected = client.post(
        f"{taro_ledger.path()}/transactions/{kept['id']}/corrections",
        headers=mom.headers,
        json={"amount": 20, "reason": "おてつだい（たくさん）", "idempotency_key": "k5"},
    )
    assert corrected.status_code == 201, corrected.text

    # The other child has a row by a different recorder and the daily bonus (ADR-0024)
    hana_ledger.record(client, mom.headers, amount=5, reason="おかたづけ", key="k6")
    bonus = client.put(
        f"{hana_ledger.path()}/daily-bonus",
        headers=mom.headers,
        json={"amount": 7, "reason": "まいにちボーナス"},
    )
    assert bonus.status_code == 200, bonus.text
    _grant_one_day(db_session, starts_on=date.fromisoformat(str(bonus.json()["starts_on"])))

    return _export(client, dad.headers, family_id)


def _grant_one_day(db_session: Session, *, starts_on: date) -> None:
    """Grant only the first day, so that ``granted_through`` appears in the archive."""
    use_case = GrantDueDailyBonusesUseCase(
        bonuses=SqlDailyBonusRepository(db_session),
        transactions=SqlPointTransactionRepository(db_session),
        boundary=DayBoundary(UTC),
        max_catch_up_days=31,
    )
    use_case.execute(now=datetime.combine(starts_on, time(12, 0)))
    db_session.commit()


# --- Export ----------------------------------------------------------------


def test_the_archive_holds_the_whole_family(family: Json) -> None:
    assert family["format"] == "rewardpointsweb.family"
    assert family["version"] == 2
    assert family["family_name"] == "ほその家"
    # The family's agreed rules are also in the archive (ADR-0027)
    assert family["family_rules"] == "おてつだい 10 pt"
    assert [member["role"] for member in family["members"]] == ["owner", "parent", "child", "child"]
    assert [member["display_name"] for member in family["members"]] == [
        "おとうさん",
        "おかあさん",
        "たろう",
        "はなこ",
    ]


def test_the_archive_holds_no_account(family: Json) -> None:
    """Neither login IDs, passwords nor invitation codes are included (ADR-0026)."""
    written = str(family)

    assert "dad" not in written
    assert "mom" not in written
    assert "password" not in written


def test_only_children_carry_a_ledger(family: Json) -> None:
    assert _member(family, "おとうさん")["ledger"] is None
    assert _member(family, "おかあさん")["ledger"] is None
    assert _member(family, "たろう")["ledger"] is not None


def test_the_ledger_keeps_who_recorded_each_entry(family: Json) -> None:
    entries = _member(family, "たろう")["ledger"]["transactions"]
    dad, mom = family["members"][0]["ref"], family["members"][1]["ref"]

    # Only the corrected row was written by mom
    assert [entry["granted_by"] for entry in entries] == [dad, dad, dad, dad, mom, mom]


def test_the_ledger_keeps_reversals_and_corrections_linked(family: Json) -> None:
    entries = _member(family, "たろう")["ledger"]["transactions"]
    by_ref = {entry["ref"]: entry for entry in entries}
    reversal = next(entry for entry in entries if entry["reverses"] and entry["amount"] == -50)
    correction = next(entry for entry in entries if entry["corrects"])

    # A reversal has the opposite sign and comes after the row it reverses
    assert by_ref[reversal["reverses"]]["amount"] == 50
    assert entries.index(reversal) > entries.index(by_ref[reversal["reverses"]])
    assert by_ref[correction["corrects"]]["reason"] == "おてつだい"
    assert correction["amount"] == 20


def test_the_daily_bonus_keeps_the_day_it_was_granted_through(family: Json) -> None:
    bonus = _member(family, "はなこ")["ledger"]["daily_bonus"]

    assert (bonus["amount"], bonus["reason"]) == (7, "まいにちボーナス")
    assert bonus["granted_through"] == bonus["starts_on"]


# --- Import ----------------------------------------------------------------


def test_importing_rebuilds_the_same_family(backup: Backup) -> None:
    imported = backup.restore()

    restored = _export(backup.client, backup.headers, imported["family_id"])
    assert restored == backup.archive | {"exported_at": restored["exported_at"]}


def test_importing_reports_what_came_back(backup: Backup) -> None:
    imported = backup.restore()

    assert imported["name"] == "ほその家"
    assert imported["member_count"] == 4
    # 6 rows for Taro + 2 rows for Hanako (1 manual row and 1 day of bonus)
    assert imported["transaction_count"] == 8


def test_the_importer_becomes_the_owner(backup: Backup) -> None:
    detail = backup.view(backup.restore()["family_id"])

    me = next(member for member in detail["memberships"] if member["is_me"])
    # Takes over the owner's display name from the archive (order returns to what it was at export)
    assert (me["role"], me["display_name"]) == ("owner", "おとうさん")


def test_the_restored_ledger_keeps_its_balance(backup: Backup) -> None:
    detail = backup.view(backup.restore()["family_id"])

    balances = {member["display_name"]: member["balance"] for member in detail["memberships"]}
    # Taro: 10 - 3 + 50 - 50 - 10 + 20, Hanako: 5 + bonus 7
    assert (balances["たろう"], balances["はなこ"]) == (17, 12)


def test_the_restored_history_still_shows_what_was_undone(backup: Backup) -> None:
    family_id = backup.restore()["family_id"]
    detail = backup.view(family_id)

    taro = next(member for member in detail["memberships"] if member["display_name"] == "たろう")
    ledger = backup.client.get(f"/api/families/{family_id}/ledgers/{taro['ledger_id']}", headers=backup.headers).json()
    undone = [entry for entry in ledger["transactions"] if entry["is_reversed"]]

    # The 2 reversed rows (the mistyped 50 and the 10 restated by the correction)
    assert sorted(entry["amount"] for entry in undone) == [10, 50]


def test_an_offset_in_the_archive_is_stored_as_the_same_instant(backup: Backup) -> None:
    """Even if archive timestamps carry an offset, the same instant is stored (HANDOVER §14).

    Export writes a trailing ``Z``, so parsing it naively yields a tz-aware value. If
    that were written without dropping the tz, a ``+09:00`` row would be stored as a
    wall clock shifted by 9 hours. This pins that the import path goes through ``as_naive_utc``.
    """
    entries = _member(backup.archive, "はなこ")["ledger"]["transactions"]
    hand_written = next(entry for entry in entries if entry["amount"] == 5)
    hand_written["occurred_at"] = "2026-08-09T21:00:00+09:00"  # = 2026-08-09T12:00:00Z

    family_id = backup.restore()["family_id"]
    detail = backup.view(family_id)
    hana = next(member for member in detail["memberships"] if member["display_name"] == "はなこ")
    ledger = backup.client.get(f"/api/families/{family_id}/ledgers/{hana['ledger_id']}", headers=backup.headers).json()

    restored = next(entry for entry in ledger["transactions"] if entry["amount"] == 5)
    assert restored["occurred_at"] == "2026-08-09T12:00:00Z"


def test_the_others_come_back_without_an_account(backup: Backup) -> None:
    """Accounts are not in the archive. The way for a person to rejoin is an invitation code (ADR-0011)."""
    detail = backup.view(backup.restore()["family_id"])

    linked = {member["display_name"]: member["is_linked"] for member in detail["memberships"]}

    assert linked == {"おとうさん": True, "おかあさん": False, "たろう": False, "はなこ": False}


def test_the_restored_daily_bonus_does_not_hand_out_the_same_day_twice(backup: Backup, db_session: Session) -> None:
    family_id = backup.restore()["family_id"]
    restored = _member(_export(backup.client, backup.headers, family_id), "はなこ")

    _grant_one_day(db_session, starts_on=date.fromisoformat(str(restored["ledger"]["daily_bonus"]["granted_through"])))

    hana = next(m for m in backup.view(family_id)["memberships"] if m["display_name"] == "はなこ")
    assert hana["balance"] == 12


def test_a_restored_member_can_be_invited_back_into_their_own_place(
    backup: Backup, admin_headers: dict[str, str]
) -> None:
    """An invitation can be issued **targeting** a restored member.

    Adding them anew would create one more member, and the ledger's "recorded by"
    would keep pointing at the original (unlinked) one. Targeting keeps the names in
    the history alive as they are.
    """
    family_id = backup.restore()["family_id"]
    mom = next(m for m in backup.view(family_id)["memberships"] if m["display_name"] == "おかあさん")
    invitation = issue_invitation(
        backup.client, backup.headers, family_id, role="parent", target_membership_id=int(str(mom["id"]))
    )
    newcomer = create_account(backup.client, admin_headers, username="mom2", role="member")

    accepted = backup.client.post(
        "/api/families/invitations/accept", headers=newcomer.headers, json={"code": invitation["code"]}
    )
    assert accepted.status_code == 200, accepted.text

    after = backup.view(family_id)["memberships"]
    assert [m["display_name"] for m in after] == ["おとうさん", "おかあさん", "たろう", "はなこ"]
    assert next(m for m in after if m["display_name"] == "おかあさん")["is_linked"] is True


# --- Refusals --------------------------------------------------------------


def test_a_child_cannot_export_the_family(client: TestClient, admin_headers: dict[str, str]) -> None:
    """A child can only see their own ledger (ADR-0009). The whole family's archive is not handed out."""
    dad = create_account(client, admin_headers, username="dad2", role="member")
    family_id = create_family(client, dad.headers)
    child = add_child(client, dad.headers, family_id, display_name="たろう")
    invitation = issue_invitation(
        client, dad.headers, family_id, role="child", target_membership_id=int(str(child["id"]))
    )
    redeemed = client.post(
        "/api/families/invitations/redeem",
        json={"code": invitation["code"], "username": "taro", "password": "taro-pass-123"},
    )
    assert redeemed.status_code == 201, redeemed.text
    child_headers = {
        "Authorization": "Bearer "
        + client.post("/api/auth/login", json={"username": "taro", "password": "taro-pass-123"}).json()["access_token"]
    }

    response = client.get(f"/api/families/{family_id}/export", headers=child_headers)

    assert response.status_code == 403
    assert response.json()["detail"]["error"] == "family_access_denied"


def test_an_outsider_cannot_export_the_family(backup: Backup, admin_headers: dict[str, str]) -> None:
    other = create_family(backup.client, backup.headers, name="よその家")
    stranger = create_account(backup.client, admin_headers, username="stranger", role="member")

    response = backup.client.get(f"/api/families/{other}/export", headers=stranger.headers)

    assert response.status_code == 403


def test_importing_needs_to_start_from_no_family(backup: Backup) -> None:
    create_family(backup.client, backup.headers, name="いまの家")

    response = backup.send()

    assert response.status_code == 409
    assert response.json()["detail"]["error"] == "already_belongs_to_family"


def test_an_archive_from_a_newer_app_is_refused(backup: Backup) -> None:
    response = backup.send(backup.archive | {"version": 99})

    assert response.status_code == 400
    assert response.json()["detail"]["error"] == "unsupported_archive_version"


def test_an_archive_from_before_the_family_rules_still_restores(backup: Backup) -> None:
    """A version 1 archive (without rules) can still be imported (ADR-0027).

    The only added field is one the family can be rebuilt without, so archives people
    already have must stay readable.
    """
    older = {key: value for key, value in backup.archive.items() if key != "family_rules"}

    imported = _import(backup.client, backup.headers, older | {"version": 1})

    detail = backup.view(imported["family_id"])
    assert detail["rules"] is None
    assert imported["member_count"] == 4


def test_some_other_json_is_refused(backup: Backup) -> None:
    response = backup.send(backup.archive | {"format": "something.else"})

    assert response.status_code == 400
    assert response.json()["detail"]["error"] == "invalid_family_archive"


def test_an_archive_beyond_the_transaction_cap_is_refused(backup: Backup) -> None:
    """The cap applies to the archive as a whole.

    A per-ledger cap would multiply just by listing more members (100 members ×
    20,000 rows). Import writes rows one by one within a single request, so whatever
    is let through occupies the DB and a worker.
    """
    backup.archive["members"][2]["ledger"]["transactions"] = [
        {
            "ref": f"t{index}",
            "amount": 1,
            "reason": "おてつだい",
            "occurred_at": "2026-08-09T12:00:00",
            "granted_by": None,
            "reverses": None,
            "corrects": None,
        }
        for index in range(MAX_ARCHIVED_TRANSACTIONS + 1)
    ]

    response = backup.send()

    assert response.status_code == 422
    assert response.json()["detail"]["error"] == "validation_error"


@pytest.mark.parametrize(
    "break_it",
    [
        pytest.param(lambda archive: archive["members"].append(archive["members"][0]), id="two-owners"),
        pytest.param(lambda archive: archive["members"].pop(0), id="no-owner"),
        pytest.param(
            lambda archive: archive["members"][0].update({"ledger": {"transactions": []}}),
            id="a-parent-with-a-ledger",
        ),
        pytest.param(lambda archive: archive["members"][2].update({"ledger": None}), id="a-child-without-a-ledger"),
        pytest.param(
            lambda archive: archive["members"][2]["ledger"]["transactions"][0].update({"reverses": "t9"}),
            id="undoing-a-row-that-is-not-there",
        ),
        pytest.param(
            lambda archive: archive["members"][2]["ledger"]["transactions"][1].update({"reverses": "t1"}),
            id="undoing-with-the-wrong-amount",
        ),
        pytest.param(
            lambda archive: archive["members"][2]["ledger"]["transactions"][0].update({"granted_by": "m9"}),
            id="recorded-by-someone-outside-the-family",
        ),
        pytest.param(
            lambda archive: archive["members"][2]["ledger"]["transactions"][1].update({"ref": "t1"}),
            id="the-same-name-used-twice",
        ),
        pytest.param(
            # Put a child (the 3rd member = Taro) in the recorder field. Only parents can write to a ledger
            lambda archive: archive["members"][2]["ledger"]["transactions"][0].update(
                {"granted_by": archive["members"][2]["ref"]}
            ),
            id="recorded-by-a-child",
        ),
        pytest.param(
            # Turn a reversal that came with a correction into a plain record
            lambda archive: archive["members"][2]["ledger"]["transactions"][4].update({"reverses": None}),
            id="a-correction-without-the-undo",
        ),
        pytest.param(
            lambda archive: archive["members"][3]["ledger"]["daily_bonus"].update({"granted_through": "2020-01-01"}),
            id="a-bonus-granted-before-it-starts",
        ),
    ],
)
def test_an_archive_that_does_not_add_up_is_refused(backup: Backup, break_it: Any) -> None:
    break_it(backup.archive)

    response = backup.send()

    assert response.status_code == 400, response.text
    assert response.json()["detail"]["error"] == "invalid_family_archive"


def test_nothing_is_written_when_the_archive_is_refused(backup: Backup) -> None:
    """No half-built family is left behind (import is a single transaction)."""
    backup.archive["members"][2]["ledger"]["transactions"][0]["reverses"] = "t9"

    assert backup.send().status_code == 400

    mine = backup.client.get("/api/families", headers=backup.headers)
    assert mine.json() == []


def test_a_family_can_be_imported_after_the_refusal(backup: Backup) -> None:
    assert backup.send(backup.archive | {"version": 99}).status_code == 400

    imported = backup.restore()

    assert imported["member_count"] == 4


def test_the_archive_of_a_family_without_children_round_trips(
    client: TestClient, guardian: Account, admin_headers: dict[str, str]
) -> None:
    """A family with no children and no records. Valid as an archive even right after creation."""
    dad = create_account(client, admin_headers, username="dad4", role="member", display_name="おとうさん")
    archive = _export(client, dad.headers, create_family(client, dad.headers, name="はじめの家"))

    imported = _import(client, guardian.headers, archive)

    assert (imported["name"], imported["member_count"], imported["transaction_count"]) == ("はじめの家", 1, 0)


# --- What the archive leaves out --------------------------------------------


def test_pending_invitations_are_not_part_of_the_archive(client: TestClient, admin_headers: dict[str, str]) -> None:
    """Unused invitations are not in the archive.

    A code hash means nothing at the restore target, and including it would only
    leave the false impression that "there is a code that will work some day".
    """
    dad = create_account(client, admin_headers, username="dad3", role="member")
    family_id = create_family(client, dad.headers)
    child = add_child(client, dad.headers, family_id, display_name="たろう")
    issue_invitation(client, dad.headers, family_id, role="child", target_membership_id=int(str(child["id"])))

    archive = _export(client, dad.headers, family_id)

    assert "invitation" not in str(archive)
