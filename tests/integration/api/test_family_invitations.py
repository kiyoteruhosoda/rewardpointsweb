"""招待による参加と、親からの一時パスワード発行（ADR-0011）。"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from shared.infrastructure.models import User
from shared.kernel.timestamps import utcnow
from tests.integration.api.family_support import (
    Account,
    add_child,
    create_account,
    create_family,
    issue_invitation,
    login,
)


@pytest.fixture
def parent(client: TestClient, admin_headers: dict[str, str]) -> Account:
    return create_account(client, admin_headers, username="dad", role="manager", display_name="おとうさん")


def _redeem(client: TestClient, code: object, *, username: str, password: str) -> dict[str, object]:
    response = client.post(
        "/api/families/invitations/redeem",
        json={"code": code, "username": username, "password": password},
    )
    assert response.status_code == 201, response.text
    body: dict[str, object] = response.json()
    return body


def test_child_creates_an_account_without_an_email(client: TestClient, parent: Account) -> None:
    family_id = create_family(client, parent.headers)
    child = add_child(client, parent.headers, family_id, display_name="たろう")
    invitation = issue_invitation(
        client, parent.headers, family_id, role="child", target_membership_id=int(str(child["id"]))
    )

    redeemed = _redeem(client, invitation["code"], username="Taro", password="taro-pass-123")
    assert redeemed["role"] == "child"
    # ログイン識別子は小文字へ正規化する
    assert redeemed["username"] == "taro"

    headers = login(client, username="taro", password="taro-pass-123")
    me = client.get("/api/auth/me", headers=headers).json()
    assert me["email"] is None

    # 参加者がアカウントと結び付く
    detail = client.get(f"/api/families/{family_id}", headers=parent.headers).json()
    linked = next(m for m in detail["memberships"] if m["id"] == child["id"])
    assert linked["is_linked"] is True
    assert linked["username"] == "taro"


def test_invitation_is_single_use(client: TestClient, parent: Account) -> None:
    family_id = create_family(client, parent.headers)
    child = add_child(client, parent.headers, family_id, display_name="たろう")
    invitation = issue_invitation(
        client, parent.headers, family_id, role="child", target_membership_id=int(str(child["id"]))
    )
    _redeem(client, invitation["code"], username="taro", password="taro-pass-123")

    again = client.post(
        "/api/families/invitations/redeem",
        json={"code": invitation["code"], "username": "taro2", "password": "taro2-pass-123"},
    )
    assert again.status_code == 404
    assert again.json()["detail"]["error"] == "invitation_not_found"


def test_unknown_code_does_not_create_an_account(client: TestClient, db_session: Session) -> None:
    response = client.post(
        "/api/families/invitations/redeem",
        json={"code": "NOPECODE1", "username": "ghost", "password": "ghost-pass-123"},
    )
    assert response.status_code == 404
    assert db_session.scalar(select(User).where(User.username == "ghost")) is None


def test_taken_username_is_rejected(client: TestClient, parent: Account) -> None:
    family_id = create_family(client, parent.headers)
    child = add_child(client, parent.headers, family_id, display_name="たろう")
    invitation = issue_invitation(
        client, parent.headers, family_id, role="child", target_membership_id=int(str(child["id"]))
    )

    response = client.post(
        "/api/families/invitations/redeem",
        json={"code": invitation["code"], "username": parent.username, "password": "whatever-123"},
    )
    assert response.status_code == 409
    assert response.json()["detail"]["error"] == "username_already_taken"


def test_invitation_for_a_linked_membership_is_refused(client: TestClient, parent: Account) -> None:
    family_id = create_family(client, parent.headers)
    child = add_child(client, parent.headers, family_id, display_name="たろう")
    first = issue_invitation(
        client, parent.headers, family_id, role="child", target_membership_id=int(str(child["id"]))
    )
    _redeem(client, first["code"], username="taro", password="taro-pass-123")

    response = client.post(
        f"/api/families/{family_id}/invitations",
        headers=parent.headers,
        json={"role": "child", "target_membership_id": child["id"]},
    )
    assert response.status_code == 409
    assert response.json()["detail"]["error"] == "invitation_target_unavailable"


def test_pending_invitations_never_expose_the_code(client: TestClient, parent: Account) -> None:
    family_id = create_family(client, parent.headers)
    child = add_child(client, parent.headers, family_id, display_name="たろう")
    issued = issue_invitation(
        client, parent.headers, family_id, role="child", target_membership_id=int(str(child["id"]))
    )
    assert issued["code"]

    listed = client.get(f"/api/families/{family_id}/invitations", headers=parent.headers).json()
    assert [i["code"] for i in listed] == [None]
    assert listed[0]["target_display_name"] == "たろう"


def test_revoked_invitation_cannot_be_redeemed(client: TestClient, parent: Account) -> None:
    family_id = create_family(client, parent.headers)
    child = add_child(client, parent.headers, family_id, display_name="たろう")
    invitation = issue_invitation(
        client, parent.headers, family_id, role="child", target_membership_id=int(str(child["id"]))
    )

    revoked = client.delete(f"/api/families/{family_id}/invitations/{invitation['id']}", headers=parent.headers)
    assert revoked.status_code == 204

    response = client.post(
        "/api/families/invitations/redeem",
        json={"code": invitation["code"], "username": "taro", "password": "taro-pass-123"},
    )
    assert response.status_code == 404


# --- 親による一時パスワードの発行 --------------------------------------------


def _linked_child(client: TestClient, parent: Account) -> tuple[int, int]:
    family_id = create_family(client, parent.headers)
    child = add_child(client, parent.headers, family_id, display_name="たろう")
    invitation = issue_invitation(
        client, parent.headers, family_id, role="child", target_membership_id=int(str(child["id"]))
    )
    _redeem(client, invitation["code"], username="taro", password="taro-pass-123")
    return family_id, int(str(child["id"]))


def test_parent_issues_a_temporary_password_and_child_must_change_it(client: TestClient, parent: Account) -> None:
    family_id, membership_id = _linked_child(client, parent)

    response = client.post(
        f"/api/families/{family_id}/memberships/{membership_id}/password-reset",
        headers=parent.headers,
    )
    assert response.status_code == 200, response.text
    issued = response.json()
    assert issued["username"] == "taro"

    # 古いパスワードは通らない
    assert client.post("/api/auth/login", json={"username": "taro", "password": "taro-pass-123"}).status_code == 401

    signed_in = client.post("/api/auth/login", json={"username": "taro", "password": issued["password"]})
    assert signed_in.status_code == 200
    assert signed_in.json()["must_change_password"] is True
    headers = {"Authorization": f"Bearer {signed_in.json()['access_token']}"}

    # 変更を終えるまで他の操作は通らない
    blocked = client.get("/api/families", headers=headers)
    assert blocked.status_code == 403
    assert blocked.json()["detail"]["error"] == "password_change_required"
    # 自分が誰かとパスワード変更だけは開いている
    assert client.get("/api/auth/me", headers=headers).json()["must_change_password"] is True

    changed = client.post(
        "/api/auth/change-password",
        headers=headers,
        json={"current_password": issued["password"], "new_password": "taro-new-pass-1"},
    )
    assert changed.status_code == 200
    assert client.get("/api/families", headers=headers).status_code == 200


def test_expired_temporary_password_is_refused(client: TestClient, parent: Account, db_session: Session) -> None:
    from datetime import timedelta

    family_id, membership_id = _linked_child(client, parent)
    issued = client.post(
        f"/api/families/{family_id}/memberships/{membership_id}/password-reset",
        headers=parent.headers,
    ).json()

    child = db_session.scalar(select(User).where(User.username == "taro"))
    assert child is not None
    child.temporary_password_expires_at = utcnow() - timedelta(seconds=1)
    db_session.commit()

    assert client.post("/api/auth/login", json={"username": "taro", "password": issued["password"]}).status_code == 401


def test_parent_cannot_reset_another_parent(client: TestClient, admin_headers: dict[str, str], parent: Account) -> None:
    other = create_account(client, admin_headers, username="mom", role="manager", display_name="おかあさん")
    family_id = create_family(client, parent.headers)
    invitation = issue_invitation(client, parent.headers, family_id, role="parent")
    accepted = client.post(
        "/api/families/invitations/accept",
        headers=other.headers,
        json={"code": invitation["code"], "display_name": "おかあさん"},
    )
    assert accepted.status_code == 200

    response = client.post(
        f"/api/families/{family_id}/memberships/{accepted.json()['membership_id']}/password-reset",
        headers=parent.headers,
    )
    assert response.status_code == 403
    assert response.json()["detail"]["error"] == "child_account_required"


def test_reset_needs_a_linked_account(client: TestClient, parent: Account) -> None:
    family_id = create_family(client, parent.headers)
    child = add_child(client, parent.headers, family_id, display_name="たろう")

    response = client.post(
        f"/api/families/{family_id}/memberships/{child['id']}/password-reset",
        headers=parent.headers,
    )
    assert response.status_code == 400
    assert response.json()["detail"]["error"] == "membership_not_linked"
