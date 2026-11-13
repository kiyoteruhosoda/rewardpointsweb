"""Shared SQLAlchemy models.

So that Alembic autogenerate and tests see every table, add an import here when
adding a model (context-specific models are imported in ``migrations/env.py`` and
``tests/conftest.py``).
"""

from shared.infrastructure.models.log import Log
from shared.infrastructure.models.role import Permission, Role, role_permissions
from shared.infrastructure.models.system_setting import SystemSetting
from shared.infrastructure.models.user import PasswordResetToken, User, user_roles

__all__ = [
    "Log",
    "PasswordResetToken",
    "Permission",
    "Role",
    "SystemSetting",
    "User",
    "role_permissions",
    "user_roles",
]
