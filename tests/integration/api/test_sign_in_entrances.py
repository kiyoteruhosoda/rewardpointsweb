"""An inventory of "the ways this user can get in" (ADR-0035).

With two authentication systems, the number of open entrances **cannot be seen without listing them side by side**.
Each context answers for its own part (password / TOTP and passkeys / link to the IdP).
"""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from bounded_contexts.account_security.infrastructure.account_security_models import (
    PasskeyCredentialRecord,
    TotpSecretRecord,
)
from bounded_contexts.identity_federation.infrastructure.identity_federation_models import (
    FederatedIdentityRecord,
)
from shared.domain.auth import master_data
from shared.infrastructure.models import User
from shared.kernel.timestamps import utcnow

_ISSUER = "https://idp.example"


def _entrances_of(client: TestClient, headers: dict[str, str], username: str) -> dict[str, object]:
    listed = client.get("/api/admin/users", headers=headers)
    assert listed.status_code == 200, listed.text
    row = next(user for user in listed.json() if user["username"] == username)
    entrances: dict[str, object] = row["entrances"]
    return entrances


def _admin(db_session: Session) -> User:
    user = db_session.scalar(select(User).where(User.username == master_data.DEFAULT_ADMIN_USERNAME))
    assert user is not None
    return user


def test_a_password_only_user_shows_one_entrance(client: TestClient, admin_headers: dict[str, str]) -> None:
    assert _entrances_of(client, admin_headers, master_data.DEFAULT_ADMIN_USERNAME) == {
        "password": True,
        "totp": False,
        "passkeys": 0,
        "identity_providers": [],
        "display_device": False,
    }


def test_every_entrance_is_listed(client: TestClient, db_session: Session, admin_headers: dict[str, str]) -> None:
    """⚠ IdP-side multi-factor does not show up here. Only entrances this app knows about can be listed."""
    admin = _admin(db_session)
    db_session.add(TotpSecretRecord(user_id=admin.id, secret="s", confirmed_at=utcnow()))
    db_session.add(
        PasskeyCredentialRecord(
            credential_id="c1",
            user_id=admin.id,
            public_key="k",
            sign_count=0,
            name="laptop",
        )
    )
    db_session.add(FederatedIdentityRecord(issuer=_ISSUER, subject="sub", user_id=admin.id))
    db_session.commit()

    assert _entrances_of(client, admin_headers, master_data.DEFAULT_ADMIN_USERNAME) == {
        "password": True,
        "totp": True,
        "passkeys": 1,
        "identity_providers": [_ISSUER],
        "display_device": False,
    }


def test_an_enrolment_in_progress_is_not_an_entrance(
    client: TestClient, db_session: Session, admin_headers: dict[str, str]
) -> None:
    """A registration still in progress (``confirmed_at`` is NULL) is not yet an entrance."""
    db_session.add(TotpSecretRecord(user_id=_admin(db_session).id, secret="s", confirmed_at=None))
    db_session.commit()

    assert _entrances_of(client, admin_headers, master_data.DEFAULT_ADMIN_USERNAME)["totp"] is False


def test_a_user_without_a_password_shows_only_what_is_left(
    client: TestClient, db_session: Session, admin_headers: dict[str, str]
) -> None:
    """⚠ Even with the password taken away, SSO still works while the link remains."""
    admin = _admin(db_session)
    db_session.add(FederatedIdentityRecord(issuer=_ISSUER, subject="sub", user_id=admin.id))
    admin.password_hash = None
    db_session.commit()

    assert _entrances_of(client, admin_headers, master_data.DEFAULT_ADMIN_USERNAME) == {
        "password": False,
        "totp": False,
        "passkeys": 0,
        "identity_providers": [_ISSUER],
        "display_device": False,
    }
