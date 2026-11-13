"""A family's lifecycle -- rename, leave, dissolve (ADR-0013).

- Only the owner can change the family name.
- A parent can leave if another parent remains, and afterwards is back to the initial state (can create a new family or accept an invitation again).
- When the owner leaves, the oldest parent takes over as owner.
- A child (guest) cannot leave on their own.
- Only the owner can dissolve, and only when there are no other members.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

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
def owner(client: TestClient, admin_headers: dict[str, str]) -> Account:
    return create_account(client, admin_headers, username="dad", role="member", display_name="おとうさん")


@pytest.fixture
def second_parent(client: TestClient, admin_headers: dict[str, str]) -> Account:
    return create_account(client, admin_headers, username="mom", role="member", display_name="おかあさん")


def _join_as_parent(client: TestClient, owner: Account, family_id: int, *, joiner: Account, name: str) -> int:
    invitation = issue_invitation(client, owner.headers, family_id, role="parent")
    response = client.post(
        "/api/families/invitations/accept",
        headers=joiner.headers,
        json={"code": invitation["code"], "display_name": name},
    )
    assert response.status_code == 200, response.text
    membership_id: int = response.json()["membership_id"]
    return membership_id


def _child_login(client: TestClient, owner: Account, family_id: int, *, username: str) -> dict[str, str]:
    child = add_child(client, owner.headers, family_id, display_name=username)
    invitation = issue_invitation(
        client, owner.headers, family_id, role="child", target_membership_id=int(str(child["id"]))
    )
    response = client.post(
        "/api/families/invitations/redeem",
        json={"code": invitation["code"], "username": username, "password": f"{username}-pass-123"},
    )
    assert response.status_code == 201, response.text
    return login(client, username=username, password=f"{username}-pass-123")


# --- Rename --------------------------------------------------------------------


def test_owner_renames_the_family(client: TestClient, owner: Account) -> None:
    family_id = create_family(client, owner.headers, name="ほその家")

    response = client.patch(f"/api/families/{family_id}", headers=owner.headers, json={"name": "あたらしい家"})
    assert response.status_code == 200, response.text
    assert response.json()["name"] == "あたらしい家"

    listed = client.get("/api/families", headers=owner.headers).json()
    assert [family["name"] for family in listed] == ["あたらしい家"]


def test_parent_cannot_rename_the_family(client: TestClient, owner: Account, second_parent: Account) -> None:
    family_id = create_family(client, owner.headers)
    _join_as_parent(client, owner, family_id, joiner=second_parent, name="おかあさん")

    response = client.patch(f"/api/families/{family_id}", headers=second_parent.headers, json={"name": "のっとり"})
    assert response.status_code == 403
    assert response.json()["detail"]["error"] == "family_access_denied"


def test_blank_family_name_is_rejected(client: TestClient, owner: Account) -> None:
    family_id = create_family(client, owner.headers)

    assert client.patch(f"/api/families/{family_id}", headers=owner.headers, json={"name": "  "}).status_code == 422


# --- Leave --------------------------------------------------------------------


def test_parent_leaves_and_returns_to_the_initial_state(
    client: TestClient, owner: Account, second_parent: Account
) -> None:
    family_id = create_family(client, owner.headers)
    _join_as_parent(client, owner, family_id, joiner=second_parent, name="おかあさん")

    left = client.post(f"/api/families/{family_id}/leave", headers=second_parent.headers)
    assert left.status_code == 204

    # Same as the initial state: no membership, and the old family is out of reach (the tie is cut)
    assert client.get("/api/families", headers=second_parent.headers).json() == []
    assert client.get(f"/api/families/{family_id}", headers=second_parent.headers).status_code == 403
    # Can create a new family, or accept an invitation again
    assert client.post("/api/families", headers=second_parent.headers, json={"name": "じぶんの家"}).status_code == 201


def test_leaving_parent_disappears_from_history_but_records_remain(
    client: TestClient, owner: Account, second_parent: Account
) -> None:
    family_id = create_family(client, owner.headers)
    _join_as_parent(client, owner, family_id, joiner=second_parent, name="おかあさん")
    child = add_child(client, owner.headers, family_id, display_name="たろう")
    ledger = Ledger(family_id=family_id, ledger_id=int(str(child["ledger_id"])))
    ledger.record(client, second_parent.headers, amount=10, reason="おてつだい", key="k1")

    assert client.post(f"/api/families/{family_id}/leave", headers=second_parent.headers).status_code == 204

    view = client.get(ledger.path(), headers=owner.headers).json()
    # The records stay as the ledger's, and only the reference to the operator is removed
    assert view["balance"] == 10
    assert [t["granted_by"] for t in view["transactions"]] == [None]


def test_leaving_owner_hands_the_family_to_the_oldest_parent(
    client: TestClient, owner: Account, second_parent: Account
) -> None:
    family_id = create_family(client, owner.headers)
    _join_as_parent(client, owner, family_id, joiner=second_parent, name="おかあさん")

    assert client.post(f"/api/families/{family_id}/leave", headers=owner.headers).status_code == 204

    detail = client.get(f"/api/families/{family_id}", headers=second_parent.headers).json()
    assert detail["my_role"] == "owner"
    assert [m["display_name"] for m in detail["memberships"]] == ["おかあさん"]


def test_owner_cannot_leave_when_the_other_parent_lost_their_account(
    *, client: TestClient, admin_headers: dict[str, str], owner: Account, second_parent: Account
) -> None:
    """A parent whose account is gone (an unlinked membership) does not count as a "remaining parent".

    Counting it would let the owner's leaving produce an owner nobody can sign in as, leaving the family
    impossible to manage or dissolve.
    """
    family_id = create_family(client, owner.headers)
    _join_as_parent(client, owner, family_id, joiner=second_parent, name="おかあさん")
    assert client.delete(f"/api/admin/users/{second_parent.user_id}", headers=admin_headers).status_code == 204

    response = client.post(f"/api/families/{family_id}/leave", headers=owner.headers)
    assert response.status_code == 409
    assert response.json()["detail"]["error"] == "last_guardian_cannot_leave"


def test_leaving_owner_skips_parents_without_an_account(
    *, client: TestClient, admin_headers: dict[str, str], owner: Account, second_parent: Account
) -> None:
    """The successor is narrowed by account linkage before age."""
    family_id = create_family(client, owner.headers)
    _join_as_parent(client, owner, family_id, joiner=second_parent, name="おかあさん")
    grandma = create_account(client, admin_headers, username="grandma", role="member")
    _join_as_parent(client, owner, family_id, joiner=grandma, name="おばあちゃん")
    assert client.delete(f"/api/admin/users/{second_parent.user_id}", headers=admin_headers).status_code == 204

    assert client.post(f"/api/families/{family_id}/leave", headers=owner.headers).status_code == 204

    # The older one (mom) has no account so is skipped, and grandma becomes the owner
    detail = client.get(f"/api/families/{family_id}", headers=grandma.headers).json()
    assert detail["my_role"] == "owner"


def test_the_last_parent_cannot_leave(client: TestClient, owner: Account) -> None:
    family_id = create_family(client, owner.headers)
    add_child(client, owner.headers, family_id, display_name="たろう")

    response = client.post(f"/api/families/{family_id}/leave", headers=owner.headers)
    assert response.status_code == 409
    assert response.json()["detail"]["error"] == "last_guardian_cannot_leave"


def test_child_cannot_leave_the_family(client: TestClient, owner: Account) -> None:
    family_id = create_family(client, owner.headers)
    child_headers = _child_login(client, owner, family_id, username="taro")

    response = client.post(f"/api/families/{family_id}/leave", headers=child_headers)
    assert response.status_code == 403
    assert response.json()["detail"]["error"] == "child_cannot_leave_family"


# --- Dissolve --------------------------------------------------------------------


def test_owner_alone_dissolves_the_family(client: TestClient, owner: Account) -> None:
    family_id = create_family(client, owner.headers)

    response = client.delete(f"/api/families/{family_id}", headers=owner.headers)
    assert response.status_code == 204

    # Same as the initial state: the list is empty, and a new family can be created
    assert client.get("/api/families", headers=owner.headers).json() == []
    assert client.post("/api/families", headers=owner.headers, json={"name": "つぎの家"}).status_code == 201


def test_family_with_a_member_cannot_be_dissolved(client: TestClient, owner: Account, second_parent: Account) -> None:
    family_id = create_family(client, owner.headers)
    _join_as_parent(client, owner, family_id, joiner=second_parent, name="おかあさん")

    response = client.delete(f"/api/families/{family_id}", headers=owner.headers)
    assert response.status_code == 409
    assert response.json()["detail"]["error"] == "family_not_empty"


def test_family_with_a_guest_cannot_be_dissolved(client: TestClient, owner: Account) -> None:
    """Cannot dissolve while a child (guest) remains. Do not create a path that deletes the ledger along with it."""
    family_id = create_family(client, owner.headers)
    add_child(client, owner.headers, family_id, display_name="たろう")

    response = client.delete(f"/api/families/{family_id}", headers=owner.headers)
    assert response.status_code == 409
    assert response.json()["detail"]["error"] == "family_not_empty"


def test_parent_cannot_dissolve_the_family(client: TestClient, owner: Account, second_parent: Account) -> None:
    family_id = create_family(client, owner.headers)
    _join_as_parent(client, owner, family_id, joiner=second_parent, name="おかあさん")

    response = client.delete(f"/api/families/{family_id}", headers=second_parent.headers)
    assert response.status_code == 403
    assert response.json()["detail"]["error"] == "family_access_denied"
