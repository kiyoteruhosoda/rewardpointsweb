"""Caring for the hatched pet on a child's ledger (ADR-0061, task #1128).

Care is free and never touches the balance, the ledger or the growth. It lifts the mood; a pet
left alone only looks lonely. The child cares for their own pet and the parents for any child's;
a display device only looks.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient

from bounded_contexts.reward_points.domain.entities.pet import STAGE_THRESHOLDS
from bounded_contexts.reward_points.domain.entities.pet_care import CARE_GAIN
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

_VIEW_CLOCK = "bounded_contexts.reward_points.application.use_cases.view_point_ledger.utcnow"
_CARE_CLOCK = "bounded_contexts.reward_points.application.use_cases.care_for_pet.utcnow"


@dataclass(frozen=True, kw_only=True)
class Home:
    parent: Account
    ledger: Ledger
    child_membership_id: int
    sibling: Ledger


@pytest.fixture
def home(client: TestClient, admin_headers: dict[str, str]) -> Home:
    # The parent is also an operator so a display device can be paired to the family
    parent = create_account(client, admin_headers, username="papa", role=("member", "operator"), display_name="パパ")
    family_id = create_family(client, parent.headers)
    child = add_child(client, parent.headers, family_id, display_name="さくら")
    sibling = add_child(client, parent.headers, family_id, display_name="けんた")
    return Home(
        parent=parent,
        ledger=Ledger(family_id=family_id, ledger_id=int(str(child["ledger_id"]))),
        child_membership_id=int(str(child["id"])),
        sibling=Ledger(family_id=family_id, ledger_id=int(str(sibling["ledger_id"]))),
    )


def _ledger(client: TestClient, ledger: Ledger, headers: dict[str, str]) -> dict[str, Any]:
    response = client.get(ledger.path(), headers=headers)
    assert response.status_code == 200, response.text
    body: dict[str, Any] = response.json()
    return body


def _pet(client: TestClient, ledger: Ledger, headers: dict[str, str]) -> dict[str, Any]:
    pet: dict[str, Any] = _ledger(client, ledger, headers)["pet"]
    return pet


def _care(client: TestClient, ledger: Ledger, *, headers: dict[str, str], kind: str) -> Any:
    return client.post(f"{ledger.path()}/pet/cares", headers=headers, json={"kind": kind})


def _cared(client: TestClient, ledger: Ledger, *, headers: dict[str, str], kind: str) -> dict[str, Any]:
    response = _care(client, ledger, headers=headers, kind=kind)
    assert response.status_code == 200, response.text
    pet: dict[str, Any] = response.json()
    return pet


def _hatch(client: TestClient, home: Home, ledger: Ledger | None = None) -> None:
    target = ledger or home.ledger
    chosen = client.put(f"{target.path()}/pet", headers=home.parent.headers, json={"species": "cat"})
    assert chosen.status_code == 200, chosen.text
    target.record(
        client, home.parent.headers, amount=STAGE_THRESHOLDS[1], reason="おてつだい", key=f"h{target.ledger_id}"
    )


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


def _display_headers(client: TestClient, home: Home) -> dict[str, str]:
    started = client.post("/api/display/pairings")
    assert started.status_code == 201, started.text
    approved = client.post(
        "/api/display/pairings/approve",
        headers=home.parent.headers,
        json={"user_code": started.json()["user_code"], "family_id": home.ledger.family_id, "name": "リビング"},
    )
    assert approved.status_code == 201, approved.text
    claimed = client.post("/api/display/pairings/claim", json={"device_code": started.json()["device_code"]})
    assert claimed.status_code == 200, claimed.text
    session = client.post("/api/display/session", json={"device_credential": claimed.json()["device_credential"]})
    assert session.status_code == 200, session.text
    return {"Authorization": f"Bearer {session.json()['access_token']}"}


def _error(response: Any) -> str:
    return str(response.json()["detail"]["error"])


# --- Before it hatches --------------------------------------------------------


def test_an_egg_with_no_species_cannot_be_cared_for(client: TestClient, home: Home) -> None:
    pet = _pet(client, home.ledger, home.parent.headers)
    refused = _care(client, home.ledger, headers=home.parent.headers, kind="feed")

    assert (pet["care"], pet["can_care"]) == (None, False)
    assert refused.status_code == 409, refused.text
    assert _error(refused) == "pet_not_hatched"


def test_a_chosen_egg_is_not_cared_for_until_it_hatches(client: TestClient, home: Home) -> None:
    client.put(f"{home.ledger.path()}/pet", headers=home.parent.headers, json={"species": "rabbit"})

    pet = _pet(client, home.ledger, home.parent.headers)
    refused = _care(client, home.ledger, headers=home.parent.headers, kind="pat")

    assert (pet["species"], pet["stage"], pet["care"], pet["can_care"]) == ("rabbit", 0, None, False)
    assert refused.status_code == 409, refused.text


# --- Caring -------------------------------------------------------------------


def test_a_hatched_pet_that_was_never_cared_for_is_calm(client: TestClient, home: Home) -> None:
    _hatch(client, home)

    pet = _pet(client, home.ledger, home.parent.headers)

    assert pet["can_care"] is True
    assert pet["care"] == {
        "mood": 0,
        "mood_level": "calm",
        "days_cared": 0,
        "last_kind": None,
        "last_cared_at": None,
    }


def test_care_lifts_the_mood_and_is_free_and_does_not_grow_the_pet(client: TestClient, home: Home) -> None:
    _hatch(client, home)
    before = _ledger(client, home.ledger, home.parent.headers)

    for kind in ("feed", "pat", "play", "bath"):
        _cared(client, home.ledger, headers=home.parent.headers, kind=kind)
    after = _ledger(client, home.ledger, home.parent.headers)

    assert after["pet"]["care"]["mood"] == 4 * CARE_GAIN
    assert after["pet"]["care"]["mood_level"] == "happy"
    assert after["pet"]["care"]["days_cared"] == 1
    assert after["pet"]["care"]["last_kind"] == "bath"
    assert after["pet"]["care"]["last_cared_at"].endswith("Z")
    assert after["balance"] == before["balance"]
    assert after["transactions"] == before["transactions"]
    growth = ("stage", "earned", "current_threshold", "next_threshold")
    assert {key: after["pet"][key] for key in growth} == {key: before["pet"][key] for key in growth}


def test_the_same_kind_again_right_away_is_not_counted_twice(client: TestClient, home: Home) -> None:
    _hatch(client, home)

    first = _cared(client, home.ledger, headers=home.parent.headers, kind="feed")
    again = _cared(client, home.ledger, headers=home.parent.headers, kind="feed")
    other = _cared(client, home.ledger, headers=home.parent.headers, kind="play")

    assert first["care"]["mood"] == CARE_GAIN
    assert again["care"]["mood"] == CARE_GAIN
    assert other["care"]["mood"] == 2 * CARE_GAIN


def test_an_unknown_kind_of_care_is_refused(client: TestClient, home: Home) -> None:
    _hatch(client, home)

    assert _care(client, home.ledger, headers=home.parent.headers, kind="scold").status_code == 422


# --- Left alone ---------------------------------------------------------------


def test_a_pet_left_alone_only_looks_lonely_and_care_brings_it_back(
    client: TestClient, home: Home, monkeypatch: pytest.MonkeyPatch
) -> None:
    _hatch(client, home)
    _cared(client, home.ledger, headers=home.parent.headers, kind="feed")
    before = _pet(client, home.ledger, home.parent.headers)
    later: datetime = utcnow() + timedelta(hours=40)
    monkeypatch.setattr(_VIEW_CLOCK, lambda: later)
    monkeypatch.setattr(_CARE_CLOCK, lambda: later)

    lonely = _pet(client, home.ledger, home.parent.headers)
    cheered = _cared(client, home.ledger, headers=home.parent.headers, kind="pat")

    assert lonely["care"]["mood_level"] == "lonely"
    assert (lonely["species"], lonely["stage"], lonely["earned"]) == (
        before["species"],
        before["stage"],
        before["earned"],
    )
    assert cheered["care"]["mood_level"] == "calm"
    assert cheered["care"]["mood"] > lonely["care"]["mood"]
    assert cheered["care"]["days_cared"] == 2


# --- Who may care -------------------------------------------------------------


def test_a_child_cares_for_their_own_pet_but_not_a_siblings(client: TestClient, home: Home) -> None:
    _hatch(client, home)
    _hatch(client, home, home.sibling)
    child = _child_headers(client, home)

    own = _care(client, home.ledger, headers=child, kind="feed")
    siblings = _care(client, home.sibling, headers=child, kind="feed")

    assert own.status_code == 200, own.text
    assert own.json()["can_care"] is True
    assert siblings.status_code == 403, siblings.text


def test_a_display_device_sees_the_care_but_cannot_give_one(client: TestClient, home: Home) -> None:
    _hatch(client, home)
    _cared(client, home.ledger, headers=home.parent.headers, kind="play")
    display = _display_headers(client, home)

    seen = _pet(client, home.ledger, display)
    refused = _care(client, home.ledger, headers=display, kind="feed")

    assert seen["can_care"] is False
    assert seen["care"]["last_kind"] == "play"
    assert refused.status_code == 403, refused.text
    assert _pet(client, home.ledger, home.parent.headers)["care"]["mood"] == CARE_GAIN


def test_a_stranger_cannot_care_for_the_pet(client: TestClient, home: Home, admin_headers: dict[str, str]) -> None:
    _hatch(client, home)
    stranger = create_account(client, admin_headers, username="stranger", role="member")

    assert _care(client, home.ledger, headers=stranger.headers, kind="feed").status_code == 403


# --- The next pet ---------------------------------------------------------------


def test_the_next_pet_starts_without_the_earlier_ones_care(client: TestClient, home: Home) -> None:
    _hatch(client, home)
    _cared(client, home.ledger, headers=home.parent.headers, kind="feed")
    home.ledger.record(client, home.parent.headers, amount=STAGE_THRESHOLDS[-1], reason="がんばった", key="grown")
    nxt = client.put(f"{home.ledger.path()}/pet", headers=home.parent.headers, json={"species": "bird"})
    assert nxt.status_code == 200, nxt.text
    home.ledger.record(client, home.parent.headers, amount=STAGE_THRESHOLDS[1], reason="おてつだい", key="next")

    pet = _pet(client, home.ledger, home.parent.headers)

    assert (pet["species"], pet["stage"]) == ("bird", 1)
    assert (pet["care"]["mood"], pet["care"]["days_cared"], pet["care"]["last_kind"]) == (0, 0, None)
