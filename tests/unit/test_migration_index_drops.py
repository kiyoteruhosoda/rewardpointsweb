"""Migrations must not separately DROP an index that goes away with its table.

MariaDB (InnoDB) cannot drop an index used by a foreign key on its own::

    (1553, "Cannot drop index 'ix_point_entries_member_id': needed in a foreign
     key constraint")

``DROP TABLE`` removes the indexes along with it, so there is no need to drop the indexes first when
dropping the table. Writing it changes nothing at best, and for a foreign-key column index it fails only in production.
The development/test SQLite accepts the same DDL so it would go unnoticed, hence this static check.

It only targets cases where "``drop_index`` and ``drop_table`` in the same function point at
the same table". A legitimate ``drop_index`` that rebuilds an index while keeping the table
is not blocked.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

_MIGRATIONS_DIR = Path(__file__).resolve().parents[2] / "migrations" / "versions"


def _migration_files() -> list[Path]:
    files = sorted(path for path in _MIGRATIONS_DIR.glob("*.py") if path.name != "__init__.py")
    assert files, f"no migrations found: {_MIGRATIONS_DIR}"
    return files


def _op_call_name(node: ast.Call) -> str | None:
    """Return ``drop_index`` for ``op.drop_index(...)``; ``None`` if not on ``op``."""
    func = node.func
    if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name) and func.value.id == "op":
        return func.attr
    return None


def _string_argument(node: ast.Call, position: int, keyword: str) -> str | None:
    """Extract a string literal from a positional or keyword argument.

    Wrappers such as ``op.f("ix_...")`` are ignored (not needed, since index names are not checked).
    """
    if len(node.args) > position:
        argument = node.args[position]
        if isinstance(argument, ast.Constant) and isinstance(argument.value, str):
            return argument.value
    for kwarg in node.keywords:
        if kwarg.arg == keyword and isinstance(kwarg.value, ast.Constant) and isinstance(kwarg.value.value, str):
            return kwarg.value.value
    return None


def _dropped_tables(function: ast.FunctionDef) -> set[str]:
    return {
        table
        for node in ast.walk(function)
        if isinstance(node, ast.Call)
        and _op_call_name(node) == "drop_table"
        and (table := _string_argument(node, 0, "table_name")) is not None
    }


def _indexed_tables_dropped_first(function: ast.FunctionDef) -> set[str]:
    return {
        table
        for node in ast.walk(function)
        if isinstance(node, ast.Call)
        and _op_call_name(node) == "drop_index"
        and (table := _string_argument(node, 1, "table_name")) is not None
    }


def _functions(tree: ast.Module) -> list[ast.FunctionDef]:
    return [node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)]


@pytest.mark.parametrize("path", _migration_files(), ids=lambda path: path.stem)
def test_no_index_is_dropped_from_a_table_that_is_dropped(path: Path) -> None:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

    violations = sorted(
        {
            f"{function.name}(): {table}"
            for function in _functions(tree)
            for table in _indexed_tables_dropped_first(function) & _dropped_tables(function)
        }
    )

    assert not violations, (
        f"{path.name}: drops indexes of a table that is DROP TABLEd (MariaDB cannot DROP"
        f" an index used by a foreign key on its own): {violations}"
    )


# --- Testing the check itself ---------------------------------------------------
# A test that only checks "there are no violations" silently passes if the check breaks. So both
# detection and the shapes that may be let through get tests.


def _violations(source: str) -> list[str]:
    tree = ast.parse(source)
    return [
        f"{function.name}(): {table}"
        for function in _functions(tree)
        for table in sorted(_indexed_tables_dropped_first(function) & _dropped_tables(function))
    ]


@pytest.mark.parametrize(
    "source",
    [
        # positional argument
        'def downgrade():\n    op.drop_index("ix_a", "a")\n    op.drop_table("a")\n',
        # table_name keyword (how existing migrations write it)
        'def downgrade():\n    op.drop_index(op.f("ix_a"), table_name="a")\n    op.drop_table("a")\n',
        # detected even in reverse order within the same function
        'def downgrade():\n    op.drop_table("a")\n    op.drop_index("ix_a", table_name="a")\n',
    ],
)
def test_a_redundant_index_drop_is_detected(source: str) -> None:
    assert _violations(source) == ["downgrade(): a"]


@pytest.mark.parametrize(
    "source",
    [
        # rebuild an index while keeping the table (legitimate drop_index)
        'def upgrade():\n    op.drop_index("ix_a", table_name="a")\n    op.create_index("ix_a2", "a", ["b"])\n',
        # only drops a different table
        'def downgrade():\n    op.drop_index("ix_a", table_name="a")\n    op.drop_table("b")\n',
        # the dropped table is in a different function (do not pick up what is not in the same function)
        'def a():\n    op.drop_index("ix_a", table_name="a")\ndef b():\n    op.drop_table("a")\n',
    ],
)
def test_a_legitimate_index_drop_is_allowed(source: str) -> None:
    assert _violations(source) == []
