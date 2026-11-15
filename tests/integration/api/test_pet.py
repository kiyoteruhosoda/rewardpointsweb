"""The pet on a child's ledger (ADR-0061).

It comes with the ledger, starts as an egg, and grows with the points ever added: spending
never shrinks it, a reversed addition does. The parents or the child choose its species.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest
from fastapi.testclient import TestClient

from bounded_contexts.reward_points.domain.entities.pet import STAGE_THRESHOLDS
from tests.integration.api.family_support import (
    Account,
    Ledger,
    add_child,
    create_account,
    create_family,
    issue_invitation,
    login,
)


@dataclass(frozen=True, kw_only=True)
class Home:
    parent: Account
    ledger: Ledger
    child_membership_id: int
    sibling: Ledger


@pytest.fixture
def home(client: TestClient, admin_headers: dict[str, str]) -> Home:
    parent = create_account(client, admin_headers, username="papa", role="member", display_name="パパ")
    family_id = create_family(client, parent.headers)
    child = add_child(client, parent.headers, family_id, display_name="さくら")
    sibling = add_child(client, parent.headers, family_id, display_name="けんた")
    return Home(
        parent=parent,
        ledger=Ledger(family_id=family_id, ledger_id=int(str(child["ledger_id"]))),
        child_membership_id=int(str(child["id"])),
        sibling=Ledger(family_id=family_id, ledger_id=int(str(sibling["ledger_id"]))),
    )


def _pet(client: TestClient, ledger: Ledger, headers: dict[str, str]) -> dict[str, Any]:
    response = client.get(ledger.path(), headers=headers)
    assert response.status_code == 200, response.text
    pet: dict[str, Any] = response.json()["pet"]
    return pet


def _choose(client: TestClient, ledger: Ledger, *, headers: dict[str, str], species: str) -> Any:
    return client.put(f"{ledger.path()}/pet", headers=headers, json={"species": species})


def _child_headers(client: TestClient, home: Home) -> dict[str, str]:
    invitation = issue_invitation(
        client, home.parent.headers, home.ledger.family_id, role="child", target_membership_id=home.child_membership_id
    )
    redeemed = client.post(
        "/api/families/invitations/redeem",
        json={"code": invitation["code"], "username": "sakura", "password": "sakura-pass-123"},
    )
    assert redeemed.status_code == 201, redeemed.text
    return login(client, username="sakura", password="sakura-pass-123")


def test_a_new_ledger_has_an_egg_with_no_species(client: TestClient, home: Home) -> None:
    pet = _pet(client, home.ledger, home.parent.headers)

    assert pet["species"] is None
    assert pet["stage"] == 0
    assert pet["stage_count"] == len(STAGE_THRESHOLDS)
    assert pet["earned"] == 0
    assert pet["next_threshold"] == STAGE_THRESHOLDS[1]
    assert pet["can_choose"] is True


def test_the_pet_grows_with_points_added_and_does_not_shrink_when_they_are_spent(
    client: TestClient, home: Home
) -> None:
    home.ledger.record(client, home.parent.headers, amount=STAGE_THRESHOLDS[2], reason="おてつだい", key="k1")
    grown = _pet(client, home.ledger, home.parent.headers)

    home.ledger.record(client, home.parent.headers, amount=-STAGE_THRESHOLDS[2], reason="おかし", key="k2")
    after_spending = _pet(client, home.ledger, home.parent.headers)

    assert grown["stage"] == 2
    assert after_spending["stage"] == 2
    assert after_spending["earned"] == STAGE_THRESHOLDS[2]


def test_a_reversed_addition_is_taken_out_of_the_growth(client: TestClient, home: Home) -> None:
    added = home.ledger.record(client, home.parent.headers, amount=STAGE_THRESHOLDS[1], reason="まちがい", key="k1")

    reversed_ = client.post(
        f"{home.ledger.path()}/transactions/{added['id']}/reversals",
        headers=home.parent.headers,
        json={"idempotency_key": "k2"},
    )

    assert reversed_.status_code == 201, reversed_.text
    pet = _pet(client, home.ledger, home.parent.headers)
    assert (pet["stage"], pet["earned"]) == (0, 0)


def test_a_corrected_addition_counts_at_its_new_amount(client: TestClient, home: Home) -> None:
    added = home.ledger.record(client, home.parent.headers, amount=STAGE_THRESHOLDS[2], reason="おてつだい", key="k1")

    corrected = client.post(
        f"{home.ledger.path()}/transactions/{added['id']}/corrections",
        headers=home.parent.headers,
        json={"amount": STAGE_THRESHOLDS[1], "reason": "おてつだい", "idempotency_key": "k2"},
    )

    assert corrected.status_code == 201, corrected.text
    pet = _pet(client, home.ledger, home.parent.headers)
    assert (pet["stage"], pet["earned"]) == (1, STAGE_THRESHOLDS[1])


def test_a_guardian_chooses_the_species_and_the_growth_stays(client: TestClient, home: Home) -> None:
    home.ledger.record(client, home.parent.headers, amount=STAGE_THRESHOLDS[1], reason="おてつだい", key="k1")

    chosen = _choose(client, home.ledger, headers=home.parent.headers, species="rabbit")
    changed = _choose(client, home.ledger, headers=home.parent.headers, species="dragon")

    assert chosen.status_code == 200, chosen.text
    assert changed.json()["species"] == "dragon"
    pet = _pet(client, home.ledger, home.parent.headers)
    assert (pet["species"], pet["stage"]) == ("dragon", 1)


def test_an_unknown_species_is_refused(client: TestClient, home: Home) -> None:
    response = _choose(client, home.ledger, headers=home.parent.headers, species="unicorn")

    assert response.status_code == 422, response.text


def test_a_child_chooses_their_own_pet_but_not_a_siblings(client: TestClient, home: Home) -> None:
    child = _child_headers(client, home)

    own = _choose(client, home.ledger, headers=child, species="cat")
    siblings = _choose(client, home.sibling, headers=child, species="cat")

    assert own.status_code == 200, own.text
    assert _pet(client, home.ledger, child)["can_choose"] is True
    assert siblings.status_code == 403, siblings.text


def test_the_pet_is_not_in_another_familys_reach(client: TestClient, home: Home, admin_headers: dict[str, str]) -> None:
    stranger = create_account(client, admin_headers, username="yoso", role="member", display_name="よそ")

    response = _choose(client, home.ledger, headers=stranger.headers, species="cat")

    assert response.status_code == 403, response.text
