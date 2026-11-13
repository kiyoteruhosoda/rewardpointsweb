"""Source of truth for authorization master data (ubiquitous language: role / permission / permission grant).

Roles, permission codes, permission grants to roles and the initial admin are "master data"
the application needs to work correctly from startup. To prevent drift from duplicated
definitions, this is the single source of truth, and

- migrations (``migrations/versions/*_seed_master_data.py``)
- the seeding script (``scripts/seed_master_data.py``)

both refer to this module. It is pure data with no framework or DB dependency,
so it can be imported safely from anywhere.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

# --- Roles ------------------------------------------------------------------
# id is fixed as a stable key for external references (user_roles etc.).
ROLES: Sequence[tuple[int, str]] = (
    (1, "admin"),
    (2, "manager"),
    (3, "member"),
    (4, "guest"),
    (5, "operator"),
    (6, "display"),
)

# --- Permission codes (scope) -----------------------------------------------
# Authorization uses scope (permission code values). The code is the stable key; id is assigned by the DB.
PERMISSION_CODES: Sequence[str] = (
    "admin:system-settings",
    "user:manage",
    "role:manage",
    "permission:manage",
    "system:manage",
    "log:view",
    "dashboard:view",
    "gui:view",
    "item:view",
    "item:manage",
    # --- Points (reward_points context) ---
    # scope only decides "is this a role that may do the operation". "May they touch this family /
    # this ledger" is decided separately by the role within the family (ADR-0009).
    "family:view",
    "family:manage",
    "point:view",
    "point:manage",
    # --- Display devices (display_devices context, ADR-0047) ---
    # Approve, list and remove display devices. This shows a family's ledger on a device,
    # so admin does not get it (admin does not see household ledgers, ADR-0018)
    "display:approve",
)

# --- Permission grants to roles ---------------------------------------------
# Role name -> set of permission codes granted. The effective scope is the union over the user's roles.
#
# Roles correspond to actors (people) (ADR-0018).
#   admin   = system administrator. Handles users, roles, settings and logs, but
#             families and points belong to the household parties (member / guest) and admin stays out
#   member  = parent / adult (member). Creates a family, adds children and records points
#   guest   = child (guest). Created only by accepting an invitation; only views their own family and ledger
#   manager = log viewer (screen name; formerly "operator"). Unrelated to family features, never assigned in family flows
#   operator = display device approver (screen name; formerly "operations admin").
#              Approves display devices and decides which family is shown on which device (ADR-0047)
#   display  = display device (not a person). Created by approval; only views the ledgers of all children in the family (ADR-0047)
_FAMILY_POINT_SCOPES: frozenset[str] = frozenset({"family:view", "family:manage", "point:view", "point:manage"})
# Scopes admin does not get. Besides families and points, also no approval to show a family on a device
_OUTSIDE_ADMIN_SCOPES: frozenset[str] = _FAMILY_POINT_SCOPES | {"display:approve"}

ROLE_PERMISSIONS: Mapping[str, Sequence[str]] = {
    "admin": tuple(code for code in PERMISSION_CODES if code not in _OUTSIDE_ADMIN_SCOPES),
    "manager": (
        "item:view",
        "item:manage",
        "dashboard:view",
        "gui:view",
    ),
    "member": (
        "item:view",
        "dashboard:view",
        "gui:view",
        # Create a family, add children, add and spend points
        "family:view",
        "family:manage",
        "point:view",
        "point:manage",
    ),
    "guest": (
        "dashboard:view",
        "gui:view",
        # Can see their own family, own points and history, but has no scope to change them
        "family:view",
        "point:view",
    ),
    "operator": (
        "dashboard:view",
        "gui:view",
        "display:approve",
    ),
    "display": (
        "dashboard:view",
        "gui:view",
        # Only views the ledgers of all children in the family. Which ledger is decided by the in-family role display
        "family:view",
        "point:view",
    ),
}

# --- Initial admin ----------------------------------------------------------
# The login identifier is ``username`` (ADR-0011). The default equals the email address
# because existing accounts are migrated with ``username = email``; this keeps the
# login procedure the same before and after the migration.
#
# The password can be overridden with the environment variable ``ADMIN_INITIAL_PASSWORD`` (recommended).
# If unset, the default password (the same string as the email address) is used. Anyone
# can know it, so in production always change it after the first login.
#
# Both plaintext and hash are kept because the plaintext is a public default (not a secret),
# and this lets a mismatch between documentation and hash be detected
# (``tests/unit/test_master_data.py`` checks they match). Hashing is an
# Infrastructure concern, so this layer does not compute it and keeps it as a constant.
DEFAULT_ADMIN_ID: int = 1
DEFAULT_ADMIN_EMAIL: str = "admin@example.com"
DEFAULT_ADMIN_USERNAME: str = "admin@example.com"
DEFAULT_ADMIN_DISPLAY_NAME: str = "admin"
DEFAULT_ADMIN_ROLE: str = "admin"
DEFAULT_ADMIN_PASSWORD: str = "admin@example.com"
DEFAULT_ADMIN_PASSWORD_HASH: str = (
    "scrypt:32768:8:1$fxv8GEDMhRaffdeK$"
    "22b106c0f64c1d0896c8cce2641303613477dd5d7c24ad2d60e839b2f3f052c6129e7176"
    "fef5f7c1833bac4c15468d546c50c2db67ea93363aec1fddb663f95e"
)

# Hashes shipped as defaults in the past. Kept to tell that an admin still on the default is
# "untouched" (used only for that check, never for new seeding).
# When the default changes, append the previous value here.
SUPERSEDED_ADMIN_PASSWORD_HASHES: Sequence[str] = (
    # plaintext "admin"
    "scrypt:32768:8:1$kp58BgWIX2eGuqc6$"
    "879463f4b7684251a26d3ce6d863de80b756a47c42244709a752e0b935ad5f0b7392f598"
    "b9a43436d8af47aba78d78c726eb8fab983fe03e823c19f92108ff27",
)

__all__ = [
    "DEFAULT_ADMIN_DISPLAY_NAME",
    "DEFAULT_ADMIN_EMAIL",
    "DEFAULT_ADMIN_ID",
    "DEFAULT_ADMIN_PASSWORD",
    "DEFAULT_ADMIN_PASSWORD_HASH",
    "DEFAULT_ADMIN_ROLE",
    "DEFAULT_ADMIN_USERNAME",
    "PERMISSION_CODES",
    "ROLES",
    "ROLE_PERMISSIONS",
    "SUPERSEDED_ADMIN_PASSWORD_HASHES",
]
