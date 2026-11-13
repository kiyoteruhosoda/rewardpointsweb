"""Do not run endpoints and dependencies that use the DB on the event loop (template ADR-0100, task #807).

Calling the synchronous DB inside ``async def`` stalls the whole event loop while a later request waits on a
row lock. The earlier request never gets its turn to commit (the ``get_db`` cleanup), so it hangs until the lock
wait limit or gunicorn's ``--timeout`` (happens only on MariaDB; the SQLite tests do not show it).
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

#: Functions that stay ``async def`` and why. They touch the DB only inside ``run_in_threadpool``
_STAYS_ASYNC: dict[str, str] = {
    "receive_backchannel_logout": "Reads the body with await (refuses oversized bodies unread). Verifies in a thread",
}

#: Files where a synchronous function may set a ``ContextVar``, and why
_CONTEXT_SETTERS: dict[str, str] = {
    "bounded_contexts/audit/presentation/pending_events.py": "Only called from middleware (on the event loop)",
}


def _own_session(call: Callable[..., object]) -> bool:
    """Dependencies that bypass ``get_db`` and open their own session (e.g. committing failure records separately)."""
    return inspect.isfunction(call) and "get_session_factory" in inspect.getsource(call)


def _reaches_db(dependant: Dependant) -> bool:
    if dependant.call is get_db or (dependant.call is not None and _own_session(dependant.call)):
        return True
    return any(_reaches_db(child) for child in dependant.dependencies)


def _coroutines_on_the_way_to_db(dependant: Dependant) -> Iterator[str]:
    call = dependant.call
    # ``iscoroutinefunction`` is false for ``yield`` dependencies
    if (inspect.iscoroutinefunction(call) or inspect.isasyncgenfunction(call)) and _reaches_db(dependant):
        yield call.__name__
    for child in dependant.dependencies:
        yield from _coroutines_on_the_way_to_db(child)


def _blocking(app: FastAPI) -> set[str]:
    """Names of ``async def`` functions that use the DB.

    ⚠ **Do not iterate ``app.routes`` directly.** Endpoints added via ``include_router`` do not appear there.
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
    """An app with a rule-breaking endpoint deep inside ``include_router`` (to catch a check that silently misses)."""
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
    """If the enumeration is empty, the tests below pass vacuously. Endpoints in the exception table must be found."""
    assert set(_STAYS_ASYNC) <= _blocking(app)
    assert any(isinstance(context.original_route, APIRoute) for context in iter_route_contexts(app.routes))


def test_routes_that_use_the_database_do_not_run_on_the_event_loop(app: FastAPI) -> None:
    found = _blocking(app) - set(_STAYS_ASYNC)
    assert not found, f"Use def for DB access. If await is needed, move the DB to a thread and list it: {found}"


def _context_sets_in_sync_functions(tree: ast.AST) -> list[str]:
    """``something_var.set(...)`` inside a ``def``. A ``def`` runs in a thread, so the caller never sees it."""
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
    """Making a dependency a ``def`` silently drops the "who" in logs and audit (hard to notice in tests)."""
    found = []
    for root in ("bounded_contexts", "presentation"):
        for file in sorted((_PROJECT_ROOT / root).rglob("*.py")):
            path = file.relative_to(_PROJECT_ROOT).as_posix()
            if "presentation/" in path and path not in _CONTEXT_SETTERS:
                found += [f"{path}: {name}" for name in _context_sets_in_sync_functions(ast.parse(file.read_text()))]
    assert not found, f"Set ContextVar in an async def dependency or in middleware: {found}"
