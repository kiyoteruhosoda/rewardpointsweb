"""The order of members, and whether each operation is available to the screen (`can_*`).

There is one order per family, shown the same way to everyone. The `can_*` flags exist so that "operations
that would be refused after pressing are not shown", so they must agree with whether the server actually
refuses -- here both are compared.
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
def parent(client: TestClient, admin_headers: dict[str, str]) -> Account:
    return create_account(client, admin_headers, username="dad", role="member", display_name="おとうさん")


def _names(client: TestClient, headers: dict[str, str], family_id: int) -> list[str]:
    detail = client.get(f"/api/families/{family_id}", headers=headers).json()
    return [m["display_name"] for m in detail["memberships"]]


def _member(client: TestClient, headers: dict[str, str], family_id: int, *, name: str) -> dict[str, object]:
    detail = client.get(f"/api/families/{family_id}", headers=headers).json()
    found: dict[str, object] = next(m for m in detail["memberships"] if m["display_name"] == name)
    return found


def _linked_child(client: TestClient, parent: Account, family_id: int, *, username: str) -> dict[str, object]:
    """Prepare a child linked to an account."""
    child = add_child(client, parent.headers, family_id, display_name=username)
    invitation = issue_invitation(
        client, parent.headers, family_id, role="child", target_membership_id=int(str(child["id"]))
    )
    redeemed = client.post(
        "/api/families/invitations/redeem",
        json={"code": invitation["code"], "username": username, "password": f"{username}-pass-123"},
    )
    assert redeemed.status_code == 201, redeemed.text
    return child


# --- Order ------------------------------------------------------------------


def test_children_keep_the_order_they_were_added(client: TestClient, parent: Account) -> None:
    family_id = create_family(client, parent.headers)
    add_child(client, parent.headers, family_id, display_name="あに")
    add_child(client, parent.headers, family_id, display_name="おとうと")

    assert _names(client, parent.headers, family_id) == ["おとうさん", "あに", "おとうと"]


def test_reordering_changes_the_order_for_everyone(client: TestClient, parent: Account) -> None:
    family_id = create_family(client, parent.headers)
    older = add_child(client, parent.headers, family_id, display_name="あに")
    younger = add_child(client, parent.headers, family_id, display_name="おとうと")

    response = client.put(
        f"/api/families/{family_id}/member-order",
        headers=parent.headers,
        json={"membership_ids": [younger["id"], older["id"]]},
    )
    assert response.status_code == 200, response.text
    assert [m["display_name"] for m in response.json()["memberships"]] == [
        "おとうさん",
        "おとうと",
        "あに",
    ]
    # Same after reloading (the parent stays first)
    assert _names(client, parent.headers, family_id) == ["おとうさん", "おとうと", "あに"]


def test_a_child_added_later_goes_to_the_end(client: TestClient, parent: Account) -> None:
    """A child added after reordering does not cut into the chosen order."""
    family_id = create_family(client, parent.headers)
    older = add_child(client, parent.headers, family_id, display_name="あに")
    younger = add_child(client, parent.headers, family_id, display_name="おとうと")
    client.put(
        f"/api/families/{family_id}/member-order",
        headers=parent.headers,
        json={"membership_ids": [younger["id"], older["id"]]},
    )

    add_child(client, parent.headers, family_id, display_name="まつこ")

    assert _names(client, parent.headers, family_id) == ["おとうさん", "おとうと", "あに", "まつこ"]


def test_an_incomplete_order_is_refused(client: TestClient, parent: Account) -> None:
    family_id = create_family(client, parent.headers)
    older = add_child(client, parent.headers, family_id, display_name="あに")
    add_child(client, parent.headers, family_id, display_name="おとうと")

    refused = client.put(
        f"/api/families/{family_id}/member-order",
        headers=parent.headers,
        json={"membership_ids": [older["id"]]},
    )
    assert refused.status_code == 400
    assert refused.json()["detail"]["error"] == "invalid_member_order"


def test_a_child_cannot_reorder(client: TestClient, parent: Account) -> None:
    family_id = create_family(client, parent.headers)
    child = _linked_child(client, parent, family_id, username="taro")
    child_headers = login(client, username="taro", password="taro-pass-123")

    refused = client.put(
        f"/api/families/{family_id}/member-order",
        headers=child_headers,
        json={"membership_ids": [child["id"]]},
    )
    # The guest role does not have family:manage (stopped by scope)
    assert refused.status_code == 403


# --- Operation availability passed to the screen ----------------------------------------------------


def test_an_empty_ledger_can_be_removed(client: TestClient, parent: Account) -> None:
    family_id = create_family(client, parent.headers)
    child = add_child(client, parent.headers, family_id, display_name="たろう")

    assert _member(client, parent.headers, family_id, name="たろう")["can_remove"] is True

    removed = client.delete(f"/api/families/{family_id}/memberships/{child['id']}", headers=parent.headers)
    assert removed.status_code == 204


def test_a_child_with_records_is_not_offered_removal(client: TestClient, parent: Account) -> None:
    """With even one record the child cannot be deleted. Not shown on screen either (`can_remove` is false)."""
    family_id = create_family(client, parent.headers)
    child = add_child(client, parent.headers, family_id, display_name="たろう")
    Ledger(family_id=family_id, ledger_id=int(str(child["ledger_id"]))).record(
        client, parent.headers, amount=10, reason="おてつだい", key="k1"
    )

    assert _member(client, parent.headers, family_id, name="たろう")["can_remove"] is False

    refused = client.delete(f"/api/families/{family_id}/memberships/{child['id']}", headers=parent.headers)
    assert refused.status_code == 409
    assert refused.json()["detail"]["error"] == "ledger_not_empty"


def test_the_owner_is_never_offered_its_own_removal(client: TestClient, parent: Account) -> None:
    family_id = create_family(client, parent.headers)

    assert _member(client, parent.headers, family_id, name="おとうさん")["can_remove"] is False


def test_independence_and_password_need_an_account(client: TestClient, parent: Account) -> None:
    """A child who cannot sign in gets neither the independence action nor a temporary password."""
    family_id = create_family(client, parent.headers)
    unlinked = add_child(client, parent.headers, family_id, display_name="たろう")

    shown = _member(client, parent.headers, family_id, name="たろう")
    assert shown["can_propose_independence"] is False
    assert shown["can_reset_password"] is False

    refused = client.post(
        f"/api/families/{family_id}/memberships/{unlinked['id']}/independence-proposal",
        headers=parent.headers,
    )
    assert refused.status_code == 400
    assert refused.json()["detail"]["error"] == "membership_not_linked"


def test_a_linked_child_is_offered_independence(client: TestClient, parent: Account) -> None:
    family_id = create_family(client, parent.headers)
    _linked_child(client, parent, family_id, username="taro")

    shown = _member(client, parent.headers, family_id, name="taro")
    assert shown["can_propose_independence"] is True
    assert shown["can_reset_password"] is True


def test_a_child_is_offered_nothing_about_siblings(client: TestClient, parent: Account) -> None:
    family_id = create_family(client, parent.headers)
    _linked_child(client, parent, family_id, username="taro")
    add_child(client, parent.headers, family_id, display_name="いもうと")
    child_headers = login(client, username="taro", password="taro-pass-123")

    detail = client.get(f"/api/families/{family_id}", headers=child_headers).json()
    for shown in detail["memberships"]:
        assert shown["can_propose_independence"] is False
        assert shown["can_remove"] is False
        assert shown["can_reset_password"] is False


def test_actions_follow_the_scope_not_only_the_role(client: TestClient, admin_headers: dict[str, str]) -> None:
    """An owner who lost `family:manage` is shown no operations (ADR-0019).

    Deciding by position (owner) alone would show buttons that "return 403 when pressed" after an operator
    edits the role's permissions. Availability looks at both stages of authorization (scope and position).
    """
    created = client.post(
        "/api/admin/roles",
        headers=admin_headers,
        json={
            "name": "guardian-lite",
            "permissions": ["family:view", "family:manage", "point:view", "point:manage"],
        },
    )
    assert created.status_code == 201, created.text
    role_id = created.json()["id"]

    guardian = create_account(client, admin_headers, username="mom", role="guardian-lite")
    family_id = create_family(client, guardian.headers)
    child = add_child(client, guardian.headers, family_id, display_name="たろう")

    demoted = client.put(
        f"/api/admin/roles/{role_id}",
        headers=admin_headers,
        json={"permissions": ["family:view", "point:view", "point:manage"]},
    )
    assert demoted.status_code == 200, demoted.text
    # Scope is baked into the token, so permission changes take effect from the next sign-in
    headers = login(client, username=guardian.username, password=guardian.password)

    shown = _member(client, headers, family_id, name="たろう")
    assert shown["can_remove"] is False
    assert shown["can_propose_independence"] is False
    assert shown["can_reset_password"] is False

    refused = client.delete(f"/api/families/{family_id}/memberships/{child['id']}", headers=headers)
    assert refused.status_code == 403
