"""The whole flow up to a complete family (E2E).

Other tests check each entry point in detail. What this one checks is the **connections** --
from an admin creating a member to a child viewing their own points,
run once in the order a real user would go through it.

    The system admin creates a member
      -> the member logs in, creates a family and adds the first child
      -> the member invites another parent
      -> the invited parent creates an account with the code and joins the family
      -> the invited parent adds a second child and gives points to the first child
      -> the invited parent hands an invitation link to the first child
      -> the first child creates an account with the code, logs in and views their own balance

It is built with the API only, without peeking at intermediate state in the DB. If there is a path
a real user cannot get through, it fails here.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from tests.integration.api.family_support import Account, create_account, login

_FIRST_CHILD = "はなこ"
_SECOND_CHILD = "たろう"
_POINTS = 30


@pytest.fixture
def member(client: TestClient, admin_headers: dict[str, str]) -> Account:
    """The system admin creates a member (parent) account."""
    return create_account(client, admin_headers, username="dad", role="member", display_name="おとうさん")


def _start_a_family(client: TestClient, member: Account) -> tuple[int, dict[str, object]]:
    """The member creates a family and adds the first child."""
    created = client.post("/api/families", headers=member.headers, json={"name": "ほその家"})
    assert created.status_code == 201, created.text
    family_id = int(str(created.json()["id"]))
    assert created.json()["my_role"] == "owner"

    child = client.post(
        f"/api/families/{family_id}/memberships",
        headers=member.headers,
        json={"display_name": _FIRST_CHILD},
    )
    assert child.status_code == 201, child.text
    # The ledger is created on add. The child cannot log in yet
    assert child.json()["ledger_id"] is not None
    assert child.json()["is_linked"] is False
    return family_id, child.json()


def _invite(
    client: TestClient,
    inviter: Account,
    family_id: int,
    *,
    role: str,
    target_membership_id: int | None = None,
) -> str:
    """Issue an invitation code. Only this response returns the plaintext code."""
    issued = client.post(
        f"/api/families/{family_id}/invitations",
        headers=inviter.headers,
        json={"role": role, "target_membership_id": target_membership_id},
    )
    assert issued.status_code == 201, issued.text
    code: str = str(issued.json()["code"])
    return code


def _sign_up_with(client: TestClient, code: str, *, username: str, display_name: str) -> Account:
    """Create an account with the invitation code, join the family and log in."""
    password = f"{username}-pass-123"
    signed_up = client.post(
        "/api/families/invitations/redeem",
        json={
            "code": code,
            "username": username,
            "password": password,
            "display_name": display_name,
        },
    )
    assert signed_up.status_code == 201, signed_up.text
    return Account(
        user_id=0,
        username=username,
        password=password,
        headers=login(client, username=username, password=password),
    )


def _member_of(client: TestClient, viewer: Account, family_id: int, *, name: str) -> dict[str, object]:
    detail = client.get(f"/api/families/{family_id}", headers=viewer.headers)
    assert detail.status_code == 200, detail.text
    found: dict[str, object] = next(m for m in detail.json()["memberships"] if m["display_name"] == name)
    return found


def test_a_family_comes_together_from_scratch(client: TestClient, member: Account) -> None:
    family_id, first_child = _start_a_family(client, member)

    # --- Invite another parent ---------------------------------------------
    parent_code = _invite(client, member, family_id, role="parent")
    invited = _sign_up_with(client, parent_code, username="mom", display_name="おかあさん")

    joined = client.get(f"/api/families/{family_id}", headers=invited.headers)
    assert joined.status_code == 200, joined.text
    assert joined.json()["my_role"] == "parent"

    # --- The invited parent grows the family --------------------------------
    second = client.post(
        f"/api/families/{family_id}/memberships",
        headers=invited.headers,
        json={"display_name": _SECOND_CHILD},
    )
    assert second.status_code == 201, second.text

    ledger_id = int(str(first_child["ledger_id"]))
    recorded = client.post(
        f"/api/families/{family_id}/ledgers/{ledger_id}/transactions",
        headers=invited.headers,
        json={"amount": _POINTS, "reason": "おてつだい", "idempotency_key": "e2e-1"},
    )
    assert recorded.status_code == 201, recorded.text

    # --- Let the child log in ----------------------------------------------
    child_code = _invite(
        client,
        invited,
        family_id,
        role="child",
        target_membership_id=int(str(first_child["id"])),
    )
    child = _sign_up_with(client, child_code, username="hanako", display_name=_FIRST_CHILD)

    # --- The child views their own points ----------------------------------
    ledger = client.get(f"/api/families/{family_id}/ledgers/{ledger_id}", headers=child.headers)
    assert ledger.status_code == 200, ledger.text
    assert ledger.json()["balance"] == _POINTS
    assert [row["reason"] for row in ledger.json()["transactions"]] == ["おてつだい"]
    # They can only see it; they cannot change it themselves (ADR-0007)
    assert ledger.json()["can_modify"] is False

    # Siblings' balances are not visible. They are listed, but there is no way into their ledger (ADR-0009)
    sibling = _member_of(client, child, family_id, name=_SECOND_CHILD)
    assert sibling["ledger_id"] is None
    assert sibling["balance"] is None
