"""SSO から見たこのアプリの利用者。

``shared`` の ``User`` モデルそのものではなく、ID 連携が必要とする項目だけを持つ。
Domain 層が SQLAlchemy のモデルに触れないようにするための境界で、実体とのやり取りは
``domain/repositories/federated_user_directory.py`` の
:class:`FederatedUserDirectory` が行う。
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FederatedAccount:
    user_id: int
    is_active: bool


__all__ = ["FederatedAccount"]
