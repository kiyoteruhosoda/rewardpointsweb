"""A user of this app as seen from SSO.

Not the ``User`` model of ``shared`` itself; it holds only the fields identity federation needs.
It is a boundary keeping the domain layer from touching SQLAlchemy models; exchange with the real thing is done by
:class:`FederatedUserDirectory` in
``domain/repositories/federated_user_directory.py``.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FederatedAccount:
    user_id: int
    is_active: bool


__all__ = ["FederatedAccount"]
