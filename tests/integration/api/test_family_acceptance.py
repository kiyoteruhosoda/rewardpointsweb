"""受け入れ基準のうち、他のファイルの主題から外れるもの。

家族・台帳・子アカウントの「境界」を確かめる（複数家族・冪等キーの必須化・
理由の候補・ログに秘密が出ないこと・OpenAPI への反映）。
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import inspect, select
from sqlalchemy.orm import Session

from bounded_contexts.reward_points.infrastructure.reward_points_models import (
    FamilyInvitationModel,
    PointLedgerModel,
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


@pytest.fixture
def parent(client: TestClient, admin_headers: dict[str, str]) -> Account:
    return create_account(client, admin_headers, username="dad", role="manager", display_name="おとうさん")


@pytest.fixture
def ledger(client: TestClient, parent: Account) -> Ledger:
    family_id = create_family(client, parent.headers)
    child = add_child(client, parent.headers, family_id, display_name="たろう")
    return Ledger(family_id=family_id, ledger_id=int(str(child["ledger_id"])))


# --- 家族 --------------------------------------------------------------------


def test_account_cannot_join_the_same_family_twice(client: TestClient, parent: Account) -> None:
    """DB の UNIQUE 制約に頼らず、アプリケーション層でも断る。"""
    family_id = create_family(client, parent.headers)
    invitation = issue_invitation(client, parent.headers, family_id, role="parent")

    response = client.post(
        "/api/families/invitations/accept",
        headers=parent.headers,
        json={"code": invitation["code"], "display_name": "おとうさん"},
    )
    assert response.status_code == 409
    assert response.json()["detail"]["error"] == "account_already_in_family"


def test_account_can_belong_to_several_families(
    client: TestClient, admin_headers: dict[str, str], parent: Account
) -> None:
    other_owner = create_account(client, admin_headers, username="grandma", role="manager")
    first = create_family(client, parent.headers, name="ほその家")
    second = create_family(client, other_owner.headers, name="となりの家")
    add_child(client, parent.headers, first, display_name="たろう")
    add_child(client, other_owner.headers, second, display_name="はなこ")

    invitation = issue_invitation(client, other_owner.headers, second, role="parent")
    joined = client.post(
        "/api/families/invitations/accept",
        headers=parent.headers,
        json={"code": invitation["code"], "display_name": "おとうさん"},
    )
    assert joined.status_code == 200

    listed = client.get("/api/families", headers=parent.headers).json()
    # 先の家族の参加はそのまま残り、家族ごとに区別して並ぶ
    assert {family["id"]: family["name"] for family in listed} == {first: "ほその家", second: "となりの家"}
    assert {family["id"]: family["my_role"] for family in listed} == {first: "owner", second: "parent"}


def test_one_ledger_per_child(client: TestClient, parent: Account, db_session: Session) -> None:
    family_id = create_family(client, parent.headers)
    child = add_child(client, parent.headers, family_id, display_name="たろう")

    ledgers = db_session.scalars(select(PointLedgerModel).where(PointLedgerModel.membership_id == child["id"])).all()
    assert len(ledgers) == 1


def test_account_outside_any_family_reaches_no_ledger(
    client: TestClient, admin_headers: dict[str, str], parent: Account, ledger: Ledger
) -> None:
    outsider = create_account(client, admin_headers, username="outsider", role="manager")

    assert client.get("/api/families", headers=outsider.headers).json() == []
    assert client.get(ledger.path(), headers=outsider.headers).status_code == 403


@dataclass(frozen=True, kw_only=True)
class LedgerCall:
    """台帳を対象とする 1 つの入口（閲覧・記録・訂正）。"""

    suffix: str
    body: dict[str, object] | None = None

    def send(self, client: TestClient, ledger: Ledger, headers: dict[str, str]) -> httpx.Response:
        url = f"{ledger.path()}{self.suffix}"
        if self.body is None:
            return client.get(url, headers=headers)
        return client.post(url, headers=headers, json=self.body)


@pytest.mark.parametrize(
    "call",
    [
        LedgerCall(suffix=""),
        LedgerCall(suffix="/transactions", body={"amount": 10, "reason": "x", "idempotency_key": "k"}),
        LedgerCall(suffix="/transactions/1/reversals", body={"idempotency_key": "k"}),
    ],
    ids=["view", "record", "reverse"],
)
def test_every_ledger_endpoint_blocks_other_families(
    client: TestClient,
    admin_headers: dict[str, str],
    ledger: Ledger,
    call: LedgerCall,
) -> None:
    """他家族の親が台帳 ID を直接指定しても、どの入口も通らない。"""
    stranger = create_account(client, admin_headers, username="stranger", role="manager")
    create_family(client, stranger.headers, name="よその家")

    response = call.send(client, ledger, stranger.headers)
    assert response.status_code == 403
    assert response.json()["detail"]["error"] == "family_access_denied"


# --- 台帳 --------------------------------------------------------------------


def test_ledger_table_holds_no_balance_column() -> None:
    """残高は導出値。列として持つと加算との不整合が起こりうる（ADR-0010）。"""
    columns = {column.name for column in inspect(PointLedgerModel).columns}
    assert columns == {"id", "family_id", "membership_id", "created_at"}


def test_idempotency_key_is_required(client: TestClient, parent: Account, ledger: Ledger) -> None:
    response = client.post(
        f"{ledger.path()}/transactions",
        headers=parent.headers,
        json={"amount": 10, "reason": "おてつだい"},
    )
    assert response.status_code == 422


def test_history_is_newest_first(client: TestClient, parent: Account, ledger: Ledger) -> None:
    old = client.post(
        f"{ledger.path()}/transactions",
        headers=parent.headers,
        json={
            "amount": 10,
            "reason": "せんげつ",
            "idempotency_key": "k1",
            "occurred_at": "2026-07-01T00:00:00Z",
        },
    ).json()
    new = client.post(
        f"{ledger.path()}/transactions",
        headers=parent.headers,
        json={
            "amount": 20,
            "reason": "きょう",
            "idempotency_key": "k2",
            "occurred_at": "2026-08-01T00:00:00Z",
        },
    ).json()
    same_moment = client.post(
        f"{ledger.path()}/transactions",
        headers=parent.headers,
        json={
            "amount": 30,
            "reason": "きょう（あと）",
            "idempotency_key": "k3",
            "occurred_at": "2026-08-01T00:00:00Z",
        },
    ).json()

    view = client.get(ledger.path(), headers=parent.headers).json()
    # occurred_at の降順。同値なら id の降順
    assert [t["id"] for t in view["transactions"]] == [same_moment["id"], new["id"], old["id"]]


def test_backdated_record_keeps_its_creation_time(client: TestClient, parent: Account, ledger: Ledger) -> None:
    recorded = client.post(
        f"{ledger.path()}/transactions",
        headers=parent.headers,
        json={
            "amount": 10,
            "reason": "せんしゅう",
            "idempotency_key": "k1",
            "occurred_at": "2026-07-20T00:00:00Z",
        },
    ).json()

    assert recorded["occurred_at"].startswith("2026-07-20")
    assert not recorded["created_at"].startswith("2026-07-20")


def test_reason_suggestions_are_per_family_and_by_frequency(
    client: TestClient, admin_headers: dict[str, str], parent: Account, ledger: Ledger
) -> None:
    ledger.record(client, parent.headers, amount=10, reason="おてつだい", key="k1")
    ledger.record(client, parent.headers, amount=10, reason="おてつだい", key="k2")
    ledger.record(client, parent.headers, amount=10, reason="そうじ", key="k3")

    other = create_account(client, admin_headers, username="grandma", role="manager")
    other_family = create_family(client, other.headers, name="となりの家")
    other_child = add_child(client, other.headers, other_family, display_name="はなこ")
    Ledger(family_id=other_family, ledger_id=int(str(other_child["ledger_id"]))).record(
        client, other.headers, amount=10, reason="よそのりゆう", key="k4"
    )

    suggestions = client.get(f"/api/families/{ledger.family_id}/reason-suggestions", headers=parent.headers).json()
    assert suggestions == ["おてつだい", "そうじ"]


def test_reversal_does_not_inflate_reason_suggestions(client: TestClient, parent: Account, ledger: Ledger) -> None:
    """打ち消しは元の理由を引き継ぐため、数えると同じ言葉が二重に効いてしまう。"""
    once = ledger.record(client, parent.headers, amount=10, reason="いちど", key="k1")
    ledger.record(client, parent.headers, amount=10, reason="ふたつ", key="k2")
    ledger.record(client, parent.headers, amount=10, reason="ふたつ", key="k3")
    client.post(
        f"{ledger.path()}/transactions/{once['id']}/reversals",
        headers=parent.headers,
        json={"idempotency_key": "k4"},
    )

    suggestions = client.get(f"/api/families/{ledger.family_id}/reason-suggestions", headers=parent.headers).json()
    assert suggestions == ["ふたつ", "いちど"]


def test_reason_suggestions_are_closed_to_children(client: TestClient, parent: Account, ledger: Ledger) -> None:
    child = add_child(client, parent.headers, ledger.family_id, display_name="はなこ")
    invitation = issue_invitation(
        client, parent.headers, ledger.family_id, role="child", target_membership_id=int(str(child["id"]))
    )
    client.post(
        "/api/families/invitations/redeem",
        json={"code": invitation["code"], "username": "hanako", "password": "hanako-pass-1"},
    )
    headers = login(client, username="hanako", password="hanako-pass-1")

    # 理由の文言は他の子の記録から来ることがある（兄弟間の非公開）
    assert client.get(f"/api/families/{ledger.family_id}/reason-suggestions", headers=headers).status_code == 403


# --- 招待・ログ・OpenAPI -----------------------------------------------------


def test_invitation_code_is_never_stored_in_the_clear(client: TestClient, parent: Account, db_session: Session) -> None:
    family_id = create_family(client, parent.headers)
    issued = issue_invitation(client, parent.headers, family_id, role="parent")

    stored = db_session.scalars(select(FamilyInvitationModel)).all()
    assert len(stored) == 1
    assert stored[0].code_hash != issued["code"]
    assert str(issued["code"]) not in stored[0].code_hash


def test_temporary_password_issue_is_logged_without_the_password(
    client: TestClient, parent: Account, caplog: pytest.LogCaptureFixture
) -> None:
    family_id = create_family(client, parent.headers)
    child = add_child(client, parent.headers, family_id, display_name="たろう")
    invitation = issue_invitation(
        client, parent.headers, family_id, role="child", target_membership_id=int(str(child["id"]))
    )
    client.post(
        "/api/families/invitations/redeem",
        json={"code": invitation["code"], "username": "taro", "password": "taro-pass-123"},
    )

    with caplog.at_level(logging.INFO):
        issued = client.post(
            f"/api/families/{family_id}/memberships/{child['id']}/password-reset",
            headers=parent.headers,
        ).json()

    records = [record for record in caplog.records if record.message == "temporary_password_issued"]
    assert len(records) == 1
    # 発行者・対象・日時（レコードの時刻）が残る
    issued_log = vars(records[0])
    assert issued_log["issued_by_membership_id"] == 1
    assert issued_log["membership_id"] == child["id"]
    assert issued_log["family_id"] == family_id
    assert records[0].created > 0
    # 平文はどのログにも出さない
    assert all(issued["password"] not in record.getMessage() for record in caplog.records)
    assert all(issued["password"] not in json.dumps(vars(record), default=str) for record in caplog.records)


def test_secrets_never_reach_the_log(
    client: TestClient, admin_headers: dict[str, str], caplog: pytest.LogCaptureFixture
) -> None:
    """パスワード・招待コード・トークンをログに残さない。

    ログは JSON で stdout と ``log`` テーブルの両方へ出るため、1 度混ざると
    取り消せない。
    """
    password = "logging-check-123"
    with caplog.at_level(logging.INFO):
        create_account(client, admin_headers, username="logcheck", role="manager")
        parent = create_account(client, admin_headers, username="dad2", role="manager")
        family_id = create_family(client, parent.headers)
        issued = issue_invitation(client, parent.headers, family_id, role="parent")
        signed_in = client.post("/api/auth/login", json={"username": "logcheck", "password": "logcheck-pass-123"})
        client.post("/api/auth/login", json={"username": "logcheck", "password": password})

    token = str(signed_in.json()["access_token"])
    secrets = [str(issued["code"]), token, password, "logcheck-pass-123"]
    logged = "\n".join(json.dumps(vars(record), default=str) for record in caplog.records)
    for secret in secrets:
        assert secret not in logged


def test_ledger_changes_are_traceable_by_request_id(
    client: TestClient, parent: Account, ledger: Ledger, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.INFO):
        ledger.record(client, parent.headers, amount=10, reason="おてつだい", key="k1")

    recorded = [r for r in caplog.records if r.message == "point_transaction_recorded"]
    assert len(recorded) == 1
    # 同じ requestId で API リクエストの行と突き合わせられる
    request_id = vars(recorded[0])["request_id"]
    assert request_id
    assert any(r.message == "http_request" and vars(r).get("request_id") == request_id for r in caplog.records)


def test_new_endpoints_appear_in_the_openapi_document(client: TestClient) -> None:
    paths = client.get("/openapi.json").json()["paths"]

    expected = {
        "/api/families",
        "/api/families/{family_id}",
        "/api/families/{family_id}/memberships",
        "/api/families/{family_id}/memberships/{membership_id}",
        "/api/families/{family_id}/memberships/{membership_id}/password-reset",
        "/api/families/{family_id}/invitations",
        "/api/families/{family_id}/invitations/{invitation_id}",
        "/api/families/invitations/accept",
        "/api/families/invitations/redeem",
        "/api/families/{family_id}/reason-suggestions",
        "/api/families/{family_id}/ledgers/{ledger_id}",
        "/api/families/{family_id}/ledgers/{ledger_id}/transactions",
        "/api/families/{family_id}/ledgers/{ledger_id}/transactions/{transaction_id}/reversals",
        "/api/auth/me",
    }
    assert expected <= set(paths)
