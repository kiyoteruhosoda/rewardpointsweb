"""The pet on a child's ledger (ADR-0061).

It comes with the ledger and starts as an egg. Choosing its species hands the egg over; from
then on it grows with the points added: spending never shrinks it, a reversed addition does,
and points from before the egg was handed over do not count.
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


def _adopt(client: TestClient, home: Home, species: str = "cat") -> None:
    response = _choose(client, home.ledger, headers=home.parent.headers, species=species)
    assert response.status_code == 200, response.text


def test_points_from_before_the_egg_was_handed_over_do_not_count(client: TestClient, home: Home) -> None:
    home.ledger.record(client, home.parent.headers, amount=STAGE_THRESHOLDS[-1], reason="これまで", key="k0")

    before = _pet(client, home.ledger, home.parent.headers)
    _adopt(client, home)
    adopted = _pet(client, home.ledger, home.parent.headers)

    assert (before["species"], before["stage"], before["earned"]) == (None, 0, 0)
    assert (adopted["species"], adopted["stage"], adopted["earned"]) == ("cat", 0, 0)


def test_the_pet_grows_with_points_added_and_does_not_shrink_when_they_are_spent(
    client: TestClient, home: Home
) -> None:
    _adopt(client, home)
    home.ledger.record(client, home.parent.headers, amount=STAGE_THRESHOLDS[2], reason="おてつだい", key="k1")
    grown = _pet(client, home.ledger, home.parent.headers)

    home.ledger.record(client, home.parent.headers, amount=-STAGE_THRESHOLDS[2], reason="おかし", key="k2")
    after_spending = _pet(client, home.ledger, home.parent.headers)

    assert grown["stage"] == 2
    assert after_spending["stage"] == 2
    assert after_spending["earned"] == STAGE_THRESHOLDS[2]


def test_a_reversed_addition_is_taken_out_of_the_growth(client: TestClient, home: Home) -> None:
    _adopt(client, home)
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
    _adopt(client, home)
    added = home.ledger.record(client, home.parent.headers, amount=STAGE_THRESHOLDS[2], reason="おてつだい", key="k1")

    corrected = client.post(
        f"{home.ledger.path()}/transactions/{added['id']}/corrections",
        headers=home.parent.headers,
        json={"amount": STAGE_THRESHOLDS[1], "reason": "おてつだい", "idempotency_key": "k2"},
    )

    assert corrected.status_code == 201, corrected.text
    pet = _pet(client, home.ledger, home.parent.headers)
    assert (pet["stage"], pet["earned"]) == (1, STAGE_THRESHOLDS[1])


def _error(response: Any) -> str:
    return str(response.json()["detail"]["error"])


def test_the_species_cannot_change_while_the_pet_is_growing(client: TestClient, home: Home) -> None:
    _adopt(client, home, "rabbit")
    home.ledger.record(client, home.parent.headers, amount=STAGE_THRESHOLDS[1], reason="おてつだい", key="k1")

    changed = _choose(client, home.ledger, headers=home.parent.headers, species="dragon")

    assert changed.status_code == 409, changed.text
    assert _error(changed) == "pet_already_chosen"
    pet = _pet(client, home.ledger, home.parent.headers)
    assert (pet["species"], pet["stage"], pet["can_choose"]) == ("rabbit", 1, False)


def test_a_fully_grown_pet_lets_the_next_one_start_from_an_egg(client: TestClient, home: Home) -> None:
    _adopt(client, home, "cat")
    home.ledger.record(client, home.parent.headers, amount=STAGE_THRESHOLDS[-1] + 50, reason="がんばった", key="k1")
    grown = _pet(client, home.ledger, home.parent.headers)

    nxt = _choose(client, home.ledger, headers=home.parent.headers, species="bird")

    assert (grown["stage"], grown["can_choose"]) == (len(STAGE_THRESHOLDS) - 1, True)
    assert nxt.status_code == 200, nxt.text
    pet = _pet(client, home.ledger, home.parent.headers)
    assert (pet["species"], pet["stage"], pet["earned"], pet["raised"]) == ("bird", 0, 0, ["cat"])
    assert pet["can_choose"] is False


def test_the_next_pet_counts_only_points_after_its_egg(client: TestClient, home: Home) -> None:
    _adopt(client, home, "cat")
    home.ledger.record(client, home.parent.headers, amount=STAGE_THRESHOLDS[-1], reason="がんばった", key="k1")
    _adopt(client, home, "dragon")

    home.ledger.record(client, home.parent.headers, amount=STAGE_THRESHOLDS[1], reason="おてつだい", key="k2")

    pet = _pet(client, home.ledger, home.parent.headers)
    assert (pet["species"], pet["stage"], pet["earned"]) == ("dragon", 1, STAGE_THRESHOLDS[1])


def test_an_unknown_species_is_refused(client: TestClient, home: Home) -> None:
    response = _choose(client, home.ledger, headers=home.parent.headers, species="unicorn")

    assert response.status_code == 422, response.text


def test_a_child_chooses_their_own_pet_but_not_a_siblings(client: TestClient, home: Home) -> None:
    child = _child_headers(client, home)

    before = _pet(client, home.ledger, child)
    own = _choose(client, home.ledger, headers=child, species="cat")
    siblings = _choose(client, home.sibling, headers=child, species="cat")

    assert before["can_choose"] is True
    assert own.status_code == 200, own.text
    assert siblings.status_code == 403, siblings.text


def test_the_pet_is_not_in_another_familys_reach(client: TestClient, home: Home, admin_headers: dict[str, str]) -> None:
    stranger = create_account(client, admin_headers, username="yoso", role="member", display_name="よそ")

    response = _choose(client, home.ledger, headers=stranger.headers, species="cat")

    assert response.status_code == 403, response.text
