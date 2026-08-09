"""家族まるごとの控え — 書き出しと取り込み（ADR-0025）。

バックアップの値打ちは「戻せること」なので、確かめ方も往復で見る。書き出した
JSON をそのまま取り込み、**もう一度書き出した控えが元と一致する**ことを主な
基準にする（書き出した時刻だけは当然ずれる）。個々の項目を突き合わせるだけだと、
控えに載せ忘れた項目は最初から比較の対象にならない。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, time
from typing import Any

import pytest
from fastapi.testclient import TestClient
from httpx import Response
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
    """控えと、それを取り込む側（まだどの家族にも所属していない親）。

    取り込みのテストはどれも「この控えを、この人が取り込む」から始まるので
    1 つにまとめる（引数を 3 つに収める意味もある。ADR-0016）。
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
    """控えを取り込む側。まだどの家族にも所属していない親。"""
    return create_account(client, admin_headers, username="aunt", role="member", display_name="おば")


@pytest.fixture
def backup(client: TestClient, guardian: Account, family: Json) -> Backup:
    return Backup(client=client, guardian=guardian, archive=family)


@pytest.fixture
def family(client: TestClient, admin_headers: dict[str, str], db_session: Session) -> Json:
    """親 2 人・子 2 人と、ひととおりの記録が入った家族の控え。

    打ち消し・訂正・毎日のボーナス・記録した人の違いを一度に含める。どれか 1 つ
    でも控えから落ちれば往復で食い違う。
    """
    dad = create_account(client, admin_headers, username="dad", role="member", display_name="おとうさん")
    mom = create_account(client, admin_headers, username="mom", role="member", display_name="おかあさん")
    family_id = create_family(client, dad.headers, name="ほその家")

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

    # 素の加算・消費と、打ち消し・訂正（ADR-0010 / ADR-0022）
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

    # もう 1 人の子は、記録した人が違う行と毎日のボーナス（ADR-0024）を持つ
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
    """最初の 1 日分だけ配る。``granted_through`` が控えに載るようにするため。"""
    use_case = GrantDueDailyBonusesUseCase(
        bonuses=SqlDailyBonusRepository(db_session),
        transactions=SqlPointTransactionRepository(db_session),
        boundary=DayBoundary(UTC),
        max_catch_up_days=31,
    )
    use_case.execute(now=datetime.combine(starts_on, time(12, 0)))
    db_session.commit()


# --- 書き出し ----------------------------------------------------------------


def test_the_archive_holds_the_whole_family(family: Json) -> None:
    assert family["format"] == "rewardpointsweb.family"
    assert family["version"] == 1
    assert family["family_name"] == "ほその家"
    assert [member["role"] for member in family["members"]] == ["owner", "parent", "child", "child"]
    assert [member["display_name"] for member in family["members"]] == [
        "おとうさん",
        "おかあさん",
        "たろう",
        "はなこ",
    ]


def test_the_archive_holds_no_account(family: Json) -> None:
    """ログイン ID もパスワードも招待コードも載らない（ADR-0025）。"""
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

    # 訂正後の行だけ、書いたのはおかあさん
    assert [entry["granted_by"] for entry in entries] == [dad, dad, dad, dad, mom, mom]


def test_the_ledger_keeps_reversals_and_corrections_linked(family: Json) -> None:
    entries = _member(family, "たろう")["ledger"]["transactions"]
    by_ref = {entry["ref"]: entry for entry in entries}
    reversal = next(entry for entry in entries if entry["reverses"] and entry["amount"] == -50)
    correction = next(entry for entry in entries if entry["corrects"])

    # 打ち消しは逆符号で、相手より後ろに並ぶ
    assert by_ref[reversal["reverses"]]["amount"] == 50
    assert entries.index(reversal) > entries.index(by_ref[reversal["reverses"]])
    assert by_ref[correction["corrects"]]["reason"] == "おてつだい"
    assert correction["amount"] == 20


def test_the_daily_bonus_keeps_the_day_it_was_granted_through(family: Json) -> None:
    bonus = _member(family, "はなこ")["ledger"]["daily_bonus"]

    assert (bonus["amount"], bonus["reason"]) == (7, "まいにちボーナス")
    assert bonus["granted_through"] == bonus["starts_on"]


# --- 取り込み ----------------------------------------------------------------


def test_importing_rebuilds_the_same_family(backup: Backup) -> None:
    imported = backup.restore()

    restored = _export(backup.client, backup.headers, imported["family_id"])
    assert restored == backup.archive | {"exported_at": restored["exported_at"]}


def test_importing_reports_what_came_back(backup: Backup) -> None:
    imported = backup.restore()

    assert imported["name"] == "ほその家"
    assert imported["member_count"] == 4
    # たろうの 6 行 ＋ はなこの 2 行（手で書いた 1 行とボーナス 1 日分）
    assert imported["transaction_count"] == 8


def test_the_importer_becomes_the_owner(backup: Backup) -> None:
    detail = backup.view(backup.restore()["family_id"])

    me = next(member for member in detail["memberships"] if member["is_me"])
    # 控えに載っていた owner の呼び名を継ぐ（並びが書き出したときと同じに戻る）
    assert (me["role"], me["display_name"]) == ("owner", "おとうさん")


def test_the_restored_ledger_keeps_its_balance(backup: Backup) -> None:
    detail = backup.view(backup.restore()["family_id"])

    balances = {member["display_name"]: member["balance"] for member in detail["memberships"]}
    # たろう: 10 - 3 + 50 - 50 - 10 + 20、はなこ: 5 + ボーナス 7
    assert (balances["たろう"], balances["はなこ"]) == (17, 12)


def test_the_restored_history_still_shows_what_was_undone(backup: Backup) -> None:
    family_id = backup.restore()["family_id"]
    detail = backup.view(family_id)

    taro = next(member for member in detail["memberships"] if member["display_name"] == "たろう")
    ledger = backup.client.get(f"/api/families/{family_id}/ledgers/{taro['ledger_id']}", headers=backup.headers).json()
    undone = [entry for entry in ledger["transactions"] if entry["is_reversed"]]

    # 打ち消された 2 行（打ち間違いの 50 と、訂正で言い直された 10）
    assert sorted(entry["amount"] for entry in undone) == [10, 50]


def test_the_others_come_back_without_an_account(backup: Backup) -> None:
    """控えにアカウントは入らない。本人が入り直す道は招待コード（ADR-0011）。"""
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
    """招待は戻ってきた参加者を **指して** 配れる。

    新しく入れ直すと参加者が 1 人増え、台帳の「記録した人」は元の（未紐付けの）
    方を指したままになる。指して配れば、履歴の名前がそのまま生き続ける。
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


# --- 断るとき ----------------------------------------------------------------


def test_a_child_cannot_export_the_family(client: TestClient, admin_headers: dict[str, str]) -> None:
    """子は自分の台帳しか見られない（ADR-0009）。家族全員分の控えは渡さない。"""
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


def test_some_other_json_is_refused(backup: Backup) -> None:
    response = backup.send(backup.archive | {"format": "something.else"})

    assert response.status_code == 400
    assert response.json()["detail"]["error"] == "invalid_family_archive"


def test_an_archive_beyond_the_transaction_cap_is_refused(backup: Backup) -> None:
    """上限は控え全体に掛かる。

    台帳ごとに掛けると、参加者を並べるだけで上限が掛け算で伸びる（100 人 ×
    20,000 行）。取り込みは 1 リクエストの中で 1 行ずつ書くので、通した分だけ
    DB とワーカーを占める。
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
            # 記録した人の欄に子（3 人目 = たろう）を置く。台帳へ書けるのは親だけ
            lambda archive: archive["members"][2]["ledger"]["transactions"][0].update(
                {"granted_by": archive["members"][2]["ref"]}
            ),
            id="recorded-by-a-child",
        ),
        pytest.param(
            # 訂正が伴っていた打ち消しを、ただの記録に変えてしまう
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
    """半端に作られた家族が残らない（取り込みは 1 つのトランザクション）。"""
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
    """子も記録も無い家族。作った直後でも控えとして成り立つ。"""
    dad = create_account(client, admin_headers, username="dad4", role="member", display_name="おとうさん")
    archive = _export(client, dad.headers, create_family(client, dad.headers, name="はじめの家"))

    imported = _import(client, guardian.headers, archive)

    assert (imported["name"], imported["member_count"], imported["transaction_count"]) == ("はじめの家", 1, 0)


# --- 控えに載らないもの ------------------------------------------------------


def test_pending_invitations_are_not_part_of_the_archive(client: TestClient, admin_headers: dict[str, str]) -> None:
    """未使用の招待は控えに入らない。

    コードのハッシュを持ち出しても復元先では意味を成さず、載せれば「そのうち
    使えるコードがある」という誤解だけが残る。
    """
    dad = create_account(client, admin_headers, username="dad3", role="member")
    family_id = create_family(client, dad.headers)
    child = add_child(client, dad.headers, family_id, display_name="たろう")
    issue_invitation(client, dad.headers, family_id, role="child", target_membership_id=int(str(child["id"])))

    archive = _export(client, dad.headers, family_id)

    assert "invitation" not in str(archive)
