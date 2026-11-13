"""Master data consistency (detects drift within the source-of-truth files)."""

from shared.domain.auth import master_data


def test_role_permissions_reference_known_codes() -> None:
    known = set(master_data.PERMISSION_CODES)
    for role, codes in master_data.ROLE_PERMISSIONS.items():
        unknown = set(codes) - known
        assert not unknown, f"role {role} references unknown codes: {unknown}"


def test_every_role_has_permission_assignment() -> None:
    role_names = {name for _, name in master_data.ROLES}
    assert role_names == set(master_data.ROLE_PERMISSIONS)


def test_admin_role_has_everything_except_family_and_points() -> None:
    """The system admin stays out of families and points and cannot approve display devices (ADR-0018, ADR-0047)."""
    outside = {"family:view", "family:manage", "point:view", "point:manage", "display:approve"}
    granted = set(master_data.ROLE_PERMISSIONS["admin"])
    assert granted == set(master_data.PERMISSION_CODES) - outside
    assert not granted & outside


def test_only_the_operator_approves_display_devices() -> None:
    """Only the operations admin approves display devices (ADR-0047)."""
    holders = {role for role, codes in master_data.ROLE_PERMISSIONS.items() if "display:approve" in codes}
    assert holders == {"operator"}


def test_display_role_only_views() -> None:
    """Display devices are view only. They hold no scope for changes (ADR-0047)."""
    granted = set(master_data.ROLE_PERMISSIONS["display"])
    assert {"family:view", "point:view"} <= granted
    assert not {code for code in granted if code.endswith(":manage") or code == "display:approve"}


def test_default_admin_role_exists() -> None:
    assert master_data.DEFAULT_ADMIN_ROLE in {name for _, name in master_data.ROLES}


def test_default_admin_password_hash_matches_documented_password() -> None:
    """Detect a mismatch between the plaintext and the hash.

    The default password is a public value listed in README and OPERATIONS, and the hash is hard-coded
    here. Fixing only one would lead to "signing in as documented does not work",
    so this mechanically checks that the two match.
    """
    from werkzeug.security import check_password_hash

    assert check_password_hash(master_data.DEFAULT_ADMIN_PASSWORD_HASH, master_data.DEFAULT_ADMIN_PASSWORD)


def test_superseded_hashes_do_not_contain_the_current_default() -> None:
    """If the current value is mixed into the old defaults, every seeding would keep overwriting the password."""
    assert master_data.DEFAULT_ADMIN_PASSWORD_HASH not in master_data.SUPERSEDED_ADMIN_PASSWORD_HASHES
