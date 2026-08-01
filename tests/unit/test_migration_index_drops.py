"""マイグレーションが「テーブルごと落とす索引」を単独で DROP していないこと。

MariaDB（InnoDB）は外部キーが使う索引を単独で落とせない::

    (1553, "Cannot drop index 'ix_point_entries_member_id': needed in a foreign
     key constraint")

``DROP TABLE`` は索引も一緒に消すため、テーブルを落とすなら索引を先に落とす必要は
無い。書けば動作は変わらないどころか、外部キー列の索引だと本番だけで落ちる。開発・
テストの SQLite は同じ DDL を通してしまい気付けないので、静的に検査する。

対象は「同じ関数の中で ``drop_index`` と ``drop_table`` の両方が同じテーブルに
向いている」場合だけ。テーブルを残したまま索引を張り替える正当な ``drop_index``
は妨げない。
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

_MIGRATIONS_DIR = Path(__file__).resolve().parents[2] / "migrations" / "versions"


def _migration_files() -> list[Path]:
    files = sorted(path for path in _MIGRATIONS_DIR.glob("*.py") if path.name != "__init__.py")
    assert files, f"マイグレーションが見つからない: {_MIGRATIONS_DIR}"
    return files


def _op_call_name(node: ast.Call) -> str | None:
    """``op.drop_index(...)`` の ``drop_index`` を返す。``op`` 以外なら ``None``。"""
    func = node.func
    if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name) and func.value.id == "op":
        return func.attr
    return None


def _string_argument(node: ast.Call, position: int, keyword: str) -> str | None:
    """位置引数またはキーワード引数から文字列リテラルを取り出す。

    ``op.f("ix_...")`` のようなラップは対象外（索引名は見ないため必要ない）。
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
        f"{path.name}: DROP TABLE する表の索引を先に落としている（MariaDB では"
        f"外部キーが使う索引を単独で DROP できない）: {violations}"
    )


# --- 検査そのものの検証 -------------------------------------------------------
# 「違反が無いこと」だけを見るテストは、検査側が壊れると黙って通る。検出と
# 見逃してよい形の双方に、テストを当てる。


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
        # 位置引数
        'def downgrade():\n    op.drop_index("ix_a", "a")\n    op.drop_table("a")\n',
        # table_name キーワード（既存のマイグレーションの書き方）
        'def downgrade():\n    op.drop_index(op.f("ix_a"), table_name="a")\n    op.drop_table("a")\n',
        # 順序が逆でも同じ関数内なら検出する
        'def downgrade():\n    op.drop_table("a")\n    op.drop_index("ix_a", table_name="a")\n',
    ],
)
def test_a_redundant_index_drop_is_detected(source: str) -> None:
    assert _violations(source) == ["downgrade(): a"]


@pytest.mark.parametrize(
    "source",
    [
        # テーブルを残したまま索引を張り替える（正当な drop_index）
        'def upgrade():\n    op.drop_index("ix_a", table_name="a")\n    op.create_index("ix_a2", "a", ["b"])\n',
        # 別のテーブルを落とすだけ
        'def downgrade():\n    op.drop_index("ix_a", table_name="a")\n    op.drop_table("b")\n',
        # 落とす表が別の関数（同じ関数内でないものまで拾わない）
        'def a():\n    op.drop_index("ix_a", table_name="a")\ndef b():\n    op.drop_table("a")\n',
    ],
)
def test_a_legitimate_index_drop_is_allowed(source: str) -> None:
    assert _violations(source) == []
