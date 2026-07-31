"""マスタデータの整合性（正本ファイル内のドリフト検出）。"""

from shared.domain.auth import master_data


def test_role_permissions_reference_known_codes() -> None:
    known = set(master_data.PERMISSION_CODES)
    for role, codes in master_data.ROLE_PERMISSIONS.items():
        unknown = set(codes) - known
        assert not unknown, f"role {role} references unknown codes: {unknown}"


def test_every_role_has_permission_assignment() -> None:
    role_names = {name for _, name in master_data.ROLES}
    assert role_names == set(master_data.ROLE_PERMISSIONS)


def test_admin_role_has_all_permissions() -> None:
    assert set(master_data.ROLE_PERMISSIONS["admin"]) == set(master_data.PERMISSION_CODES)


def test_default_admin_role_exists() -> None:
    assert master_data.DEFAULT_ADMIN_ROLE in {name for _, name in master_data.ROLES}


def test_default_admin_password_hash_matches_documented_password() -> None:
    """平文とハッシュの食い違いを検出する。

    既定パスワードは README・OPERATIONS に載る公開値で、ハッシュはここに直書き
    してある。片方だけ直すと「ドキュメントどおりに入れてもログインできない」に
    なるため、両者が一致していることを機械で確かめる。
    """
    from werkzeug.security import check_password_hash

    assert check_password_hash(master_data.DEFAULT_ADMIN_PASSWORD_HASH, master_data.DEFAULT_ADMIN_PASSWORD)


def test_superseded_hashes_do_not_contain_the_current_default() -> None:
    """旧既定値に現行値が混ざると、投入のたびにパスワードを上書きし続けてしまう。"""
    assert master_data.DEFAULT_ADMIN_PASSWORD_HASH not in master_data.SUPERSEDED_ADMIN_PASSWORD_HASHES
