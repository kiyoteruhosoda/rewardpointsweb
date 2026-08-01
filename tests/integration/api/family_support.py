"""家族まわりのテストで繰り返す手順（アカウント作成・ログイン・家族の用意）。

API だけを使って組み立てる。DB を直接触ると、実際の利用者が通れない状態でも
テストが通ってしまう。
"""

from __future__ import annotations

from dataclasses import dataclass

from fastapi.testclient import TestClient


@dataclass(frozen=True, kw_only=True)
class Account:
    user_id: int
    username: str
    password: str
    headers: dict[str, str]


def login(client: TestClient, *, username: str, password: str) -> dict[str, str]:
    response = client.post("/api/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def create_account(
    client: TestClient,
    admin_headers: dict[str, str],
    *,
    username: str,
    role: str,
    display_name: str | None = None,
) -> Account:
    password = f"{username}-pass-123"
    response = client.post(
        "/api/admin/users",
        headers=admin_headers,
        json={
            "username": username,
            "display_name": display_name or username,
            "password": password,
            "roles": [role],
        },
    )
    assert response.status_code == 201, response.text
    return Account(
        user_id=response.json()["id"],
        username=username,
        password=password,
        headers=login(client, username=username, password=password),
    )


def create_family(client: TestClient, headers: dict[str, str], *, name: str = "ほその家") -> int:
    response = client.post("/api/families", headers=headers, json={"name": name})
    assert response.status_code == 201, response.text
    family_id: int = response.json()["id"]
    return family_id


def add_child(client: TestClient, headers: dict[str, str], family_id: int, *, display_name: str) -> dict[str, object]:
    response = client.post(
        f"/api/families/{family_id}/memberships",
        headers=headers,
        json={"display_name": display_name},
    )
    assert response.status_code == 201, response.text
    membership: dict[str, object] = response.json()
    return membership


def issue_invitation(
    client: TestClient,
    headers: dict[str, str],
    family_id: int,
    *,
    role: str,
    target_membership_id: int | None = None,
) -> dict[str, object]:
    response = client.post(
        f"/api/families/{family_id}/invitations",
        headers=headers,
        json={"role": role, "target_membership_id": target_membership_id},
    )
    assert response.status_code == 201, response.text
    invitation: dict[str, object] = response.json()
    return invitation


@dataclass(frozen=True, kw_only=True)
class Ledger:
    """記録先（家族と台帳の組）と、そこへの追記。"""

    family_id: int
    ledger_id: int

    def path(self) -> str:
        return f"/api/families/{self.family_id}/ledgers/{self.ledger_id}"

    def record(
        self,
        client: TestClient,
        headers: dict[str, str],
        *,
        amount: int,
        reason: str,
        key: str,
    ) -> dict[str, object]:
        response = client.post(
            f"{self.path()}/transactions",
            headers=headers,
            json={"amount": amount, "reason": reason, "idempotency_key": key},
        )
        assert response.status_code == 201, response.text
        transaction: dict[str, object] = response.json()
        return transaction


__all__ = [
    "Account",
    "Ledger",
    "add_child",
    "create_account",
    "create_family",
    "issue_invitation",
    "login",
]
