"""実装そのものに課した約束（レビューではなく機械で守る）。

- 台帳の可否判定を `family_access_policy` の 2 関数の外へ散らさない（ADR-0009）
- `point_transactions` を追記専用に保つ（ADR-0010）

どちらも「うっかり 1 か所書いてしまう」ことで壊れる種類の約束で、壊れても
既存のテストは通ってしまう。AST で直接見る。
"""

from __future__ import annotations

import ast
from collections.abc import Iterator
from pathlib import Path

_CONTEXT_ROOT = Path(__file__).resolve().parents[2] / "bounded_contexts" / "reward_points"

# 立場（FamilyRole）を知ってよい場所。
# - value_objects/family_role.py: 列挙そのもの
# - services/family_access_policy.py: 唯一の判定者
# - infrastructure/: 行 ↔ 列挙の変換と、立場からアプリロールへの対応付け
# - presentation/schemas.py: リクエスト・レスポンスの型として載せるだけ
_ROLE_AWARE = (
    "domain/value_objects/family_role.py",
    "domain/services/family_access_policy.py",
    "domain/repositories/",
    "infrastructure/",
    "presentation/schemas.py",
)


def _python_files() -> Iterator[Path]:
    return (path for path in _CONTEXT_ROOT.rglob("*.py") if path.name != "__init__.py")


def _relative(path: Path) -> str:
    return path.relative_to(_CONTEXT_ROOT).as_posix()


def _is_role_value(node: ast.AST) -> bool:
    """``FamilyRole.OWNER`` のような列挙値への参照か。"""
    return isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id == "FamilyRole"


def _compares_role(tree: ast.AST) -> bool:
    """立場を **比較している** か。

    「どの立場として作るか」を指定するだけの参照（``role=FamilyRole.CHILD``）は
    判定ではないので数えない。散らかると困るのは分岐の方。
    """
    return any(
        isinstance(node, ast.Compare)
        and (_is_role_value(node.left) or any(_is_role_value(operand) for operand in node.comparators))
        for node in ast.walk(tree)
    )


def test_ledger_authorization_does_not_leak_role_comparisons() -> None:
    """台帳の可否は `can_view_ledger` / `can_modify_ledger` の中だけで決める。

    ユースケースやルーターが `role == owner` のような分岐を持ち始めると、
    可視範囲を変えたいときに直す場所が散る（ADR-0009 が避けたかったこと）。
    """
    offenders = [
        _relative(path)
        for path in _python_files()
        if not _relative(path).startswith(_ROLE_AWARE) and _compares_role(ast.parse(path.read_text(encoding="utf-8")))
    ]
    assert offenders == [], f"立場を直接比較している箇所: {offenders}"


def test_access_policy_exposes_exactly_two_ledger_decisions() -> None:
    policy = _CONTEXT_ROOT / "domain" / "services" / "family_access_policy.py"
    tree = ast.parse(policy.read_text(encoding="utf-8"))
    names = {node.name for node in tree.body if isinstance(node, ast.FunctionDef)}

    assert {"can_view_ledger", "can_modify_ledger"} <= names


def test_point_transactions_are_never_updated_or_deleted() -> None:
    """追記専用（ADR-0010）。訂正は打ち消しの行で表し、行は消さない。"""
    repository = _CONTEXT_ROOT / "infrastructure" / "sql_point_transaction_repository.py"
    tree = ast.parse(repository.read_text(encoding="utf-8"))

    called = {node.func.id for node in ast.walk(tree) if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)}
    assert "delete" not in called
    assert "update" not in called

    methods = {node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)}
    assert not {"delete", "update", "remove"} & methods


def test_transaction_repository_port_offers_no_way_to_change_a_row() -> None:
    port = _CONTEXT_ROOT / "domain" / "repositories" / "point_transaction_repository.py"
    tree = ast.parse(port.read_text(encoding="utf-8"))
    methods = {node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)}

    assert not {"delete", "update", "remove"} & methods
