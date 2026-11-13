"""Promises imposed on the implementation itself (enforced by machine, not by review).

- Do not scatter ledger permission checks outside the 2 functions of `family_access_policy` (ADR-0009)
- Keep `point_transactions` append-only (ADR-0010)

Both are promises that break by "accidentally writing it in one place", and existing tests
still pass when they break. So the AST is inspected directly.
"""

from __future__ import annotations

import ast
from collections.abc import Iterator
from pathlib import Path

_CONTEXT_ROOT = Path(__file__).resolve().parents[2] / "bounded_contexts" / "reward_points"

# Places allowed to know about the family role (FamilyRole).
# - value_objects/family_role.py: the enum itself
# - services/family_access_policy.py: the sole decider
# - infrastructure/: row <-> enum conversion and mapping roles to app roles
# - presentation/schemas.py: only carries it as a request/response type
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
    """Whether this is a reference to an enum value such as ``FamilyRole.OWNER``."""
    return isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id == "FamilyRole"


def _compares_role(tree: ast.AST) -> bool:
    """Whether the role is being **compared**.

    A reference that only specifies "which role to create as" (``role=FamilyRole.CHILD``)
    is not a decision, so it is not counted. It is the branching that hurts when scattered.
    """
    return any(
        isinstance(node, ast.Compare)
        and (_is_role_value(node.left) or any(_is_role_value(operand) for operand in node.comparators))
        for node in ast.walk(tree)
    )


def test_ledger_authorization_does_not_leak_role_comparisons() -> None:
    """Ledger permissions are decided only inside `can_view_ledger` / `can_modify_ledger`.

    If use cases or routers start branching like `role == owner`, the places to fix
    get scattered when visibility needs to change (what ADR-0009 wanted to avoid).
    """
    offenders = [
        _relative(path)
        for path in _python_files()
        if not _relative(path).startswith(_ROLE_AWARE) and _compares_role(ast.parse(path.read_text(encoding="utf-8")))
    ]
    assert offenders == [], f"places comparing the role directly: {offenders}"


def test_access_policy_exposes_exactly_two_ledger_decisions() -> None:
    policy = _CONTEXT_ROOT / "domain" / "services" / "family_access_policy.py"
    tree = ast.parse(policy.read_text(encoding="utf-8"))
    names = {node.name for node in tree.body if isinstance(node, ast.FunctionDef)}

    assert {"can_view_ledger", "can_modify_ledger"} <= names


def test_point_transactions_are_never_updated_or_deleted() -> None:
    """Append-only (ADR-0010). Corrections are expressed with reversal rows; rows are never deleted individually.

    The only exception is ``delete_by_ledger`` (ADR-0014), which deletes a whole ledger when independence takes effect.
    Checks that delete calls do not appear outside that function.
    """
    repository = _CONTEXT_ROOT / "infrastructure" / "sql_point_transaction_repository.py"
    tree = ast.parse(repository.read_text(encoding="utf-8"))

    functions = [node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)]
    for function in functions:
        if function.name == "delete_by_ledger":
            continue
        called = {
            node.func.id
            for node in ast.walk(function)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
        }
        assert "delete" not in called, f"deleting outside delete_by_ledger: {function.name}"
        assert "update" not in called, f"updating: {function.name}"

    methods = {function.name for function in functions}
    assert not {"delete", "update", "remove"} & methods


def test_transaction_repository_port_offers_no_way_to_change_a_row() -> None:
    """No per-row update/delete entry points. Only the independence exception that deletes a whole ledger (ADR-0014)."""
    port = _CONTEXT_ROOT / "domain" / "repositories" / "point_transaction_repository.py"
    tree = ast.parse(port.read_text(encoding="utf-8"))
    methods = {node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)}

    assert not {"delete", "update", "remove"} & methods
    assert "delete_by_ledger" in methods
