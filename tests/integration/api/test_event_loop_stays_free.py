"""DB を使う口と依存関数をイベントループの上で動かさない（雛形の ADR-0100・task #807）。

``async def`` の中で同期の DB を呼ぶと、後の要求が行のロックを待つあいだ、イベントループごと止まる。先の要求の
確定（``get_db`` の後始末）の順番が回ってこないので、ロック待ちの上限か gunicorn の ``--timeout`` まで固まる
（MariaDB でだけ起きる。SQLite の試験では出ない）。
"""

from __future__ import annotations

import ast
import inspect
from collections.abc import AsyncIterator, Callable, Iterator
from pathlib import Path

from fastapi import APIRouter, Depends, FastAPI
from fastapi.dependencies.models import Dependant
from fastapi.routing import APIRoute, iter_route_contexts

from shared.kernel.database.session import get_db

_PROJECT_ROOT = Path(__file__).resolve().parents[3]

#: ``async def`` のままにする関数と理由。DB は ``run_in_threadpool`` の中でだけ触る
_STAYS_ASYNC: dict[str, str] = {
    "receive_backchannel_logout": "本文を await で読む（大きすぎる本文を読まずに断る）。検証はスレッドへ逃がす",
}

#: 同期の関数で ``ContextVar`` を置いてよいファイルと理由
_CONTEXT_SETTERS: dict[str, str] = {
    "bounded_contexts/audit/presentation/pending_events.py": "ミドルウェア（イベントループの上）からだけ呼ばれる",
}


def _own_session(call: Callable[..., object]) -> bool:
    """``get_db`` を通らず、自分でセッションを開く依存関数（失敗の記録を別に確定するものなど）。"""
    return inspect.isfunction(call) and "get_session_factory" in inspect.getsource(call)


def _reaches_db(dependant: Dependant) -> bool:
    if dependant.call is get_db or (dependant.call is not None and _own_session(dependant.call)):
        return True
    return any(_reaches_db(child) for child in dependant.dependencies)


def _coroutines_on_the_way_to_db(dependant: Dependant) -> Iterator[str]:
    call = dependant.call
    # ``yield`` の依存関数は ``iscoroutinefunction`` が偽になる
    if (inspect.iscoroutinefunction(call) or inspect.isasyncgenfunction(call)) and _reaches_db(dependant):
        yield call.__name__
    for child in dependant.dependencies:
        yield from _coroutines_on_the_way_to_db(child)


def _blocking(app: FastAPI) -> set[str]:
    """DB を使うのに ``async def`` の関数の名前。

    ⚠ **``app.routes`` を直に回さない。** ``include_router`` した口はそこに並ばない。
    """
    return {
        name
        for context in iter_route_contexts(app.routes)
        if isinstance(context.original_route, APIRoute)
        for name in _coroutines_on_the_way_to_db(context.dependant)
    }


async def async_dependency(db: object = Depends(get_db)) -> object:
    return db


async def async_yield_dependency(db: object = Depends(get_db)) -> AsyncIterator[object]:
    yield db


def sync_dependency(db: object = Depends(get_db)) -> object:
    return db


async def free_dependency() -> None: ...


def _an_app_that_blocks() -> FastAPI:
    """規則を破った口を、``include_router`` の奥に置いたアプリ（判定の空振りを見つけるため）。"""
    inner = APIRouter()

    @inner.get("/direct")
    async def async_route(db: object = Depends(get_db)) -> None: ...

    @inner.get("/nested")
    def sync_route_with_async_dependency(db: object = Depends(async_dependency)) -> None: ...

    @inner.get("/yielding")
    def sync_route_with_async_yield_dependency(db: object = Depends(async_yield_dependency)) -> None: ...

    @inner.get("/through")
    async def async_route_through_sync_dependency(db: object = Depends(sync_dependency)) -> None: ...

    @inner.get("/fine")
    def fine(db: object = Depends(sync_dependency), _free: None = Depends(free_dependency)) -> None: ...

    @inner.get("/no-db")
    async def no_db(_free: None = Depends(free_dependency)) -> None: ...

    outer = APIRouter(prefix="/api")
    outer.include_router(inner)
    app = FastAPI()
    app.include_router(outer)
    return app


def test_the_check_catches_a_route_that_breaks_the_rule() -> None:
    assert _blocking(_an_app_that_blocks()) == {
        "async_route",
        "async_dependency",
        "async_yield_dependency",
        "async_route_through_sync_dependency",
    }


def test_the_real_routes_are_being_looked_at(app: FastAPI) -> None:
    """列挙が空だと、下の試験は素通りする。例外の表の口は必ず見つかるはず。"""
    assert set(_STAYS_ASYNC) <= _blocking(app)
    assert any(isinstance(context.original_route, APIRoute) for context in iter_route_contexts(app.routes))


def test_routes_that_use_the_database_do_not_run_on_the_event_loop(app: FastAPI) -> None:
    found = _blocking(app) - set(_STAYS_ASYNC)
    assert not found, f"DB を使うなら def にしてください。await が要るなら DB をスレッドへ逃がして表へ: {found}"


def _context_sets_in_sync_functions(tree: ast.AST) -> list[str]:
    """``def`` の中の ``なんとか_var.set(...)``。``def`` はスレッドで動くので、置いた値は呼び出し元へ戻らない。"""
    return [
        function.name
        for function in ast.walk(tree)
        if isinstance(function, ast.FunctionDef)
        for node in ast.walk(function)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "set"
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id.endswith("_var")
    ]


def test_the_context_check_catches_a_sync_function() -> None:
    tree = ast.parse("async def fine():\n    a_var.set(1)\ndef broken():\n    a_var.set(1)\n")
    assert _context_sets_in_sync_functions(tree) == ["broken"]


def test_presentation_does_not_set_context_in_sync_functions() -> None:
    """依存関数を ``def`` にすると、ログと監査の「誰が」が黙って消える（試験では気付きにくい）。"""
    found = []
    for root in ("bounded_contexts", "presentation"):
        for file in sorted((_PROJECT_ROOT / root).rglob("*.py")):
            path = file.relative_to(_PROJECT_ROOT).as_posix()
            if "presentation/" in path and path not in _CONTEXT_SETTERS:
                found += [f"{path}: {name}" for name in _context_sets_in_sync_functions(ast.parse(file.read_text()))]
    assert not found, f"ContextVar は async def の依存関数かミドルウェアで置いてください: {found}"
