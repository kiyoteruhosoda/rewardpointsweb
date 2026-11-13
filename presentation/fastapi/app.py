"""FastAPI application factory."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator

from bounded_contexts.account_security.presentation.error_handling import (
    register_account_security_error_handler,
)
from bounded_contexts.account_security.presentation.passkey_login_router import (
    router as passkey_login_router,
)
from bounded_contexts.account_security.presentation.router import (
    router as account_security_router,
)
from bounded_contexts.display_devices.presentation.error_handling import (
    register_display_devices_error_handler,
)
from bounded_contexts.display_devices.presentation.router import router as display_router
from bounded_contexts.example.presentation.router import router as items_router
from bounded_contexts.identity_federation.presentation.error_handling import (
    register_identity_federation_error_handler,
)
from bounded_contexts.identity_federation.presentation.reconciliation import (
    start_sso_reconciliation,
)
from bounded_contexts.identity_federation.presentation.router import (
    router as sso_router,
)
from bounded_contexts.identity_federation.presentation.startup_check import (
    report_sso_configuration,
)
from bounded_contexts.reward_points.presentation.daily_bonus_grants import (
    start_daily_bonus_grants,
)
from bounded_contexts.reward_points.presentation.error_handling import (
    register_reward_points_error_handler,
)
from bounded_contexts.reward_points.presentation.router import router as families_router
from presentation.fastapi.error_handling import register_error_handling
from presentation.fastapi.middleware.deferred_log_writes import (
    DeferredLogWriteMiddleware,
)
from presentation.fastapi.middleware.internal_error import InternalErrorMiddleware
from presentation.fastapi.middleware.request_logging import RequestLoggingMiddleware
from presentation.fastapi.routers import spa
from presentation.fastapi.routers.admin.config import router as admin_config_router
from presentation.fastapi.routers.admin.logs import router as admin_logs_router
from presentation.fastapi.routers.admin.permissions import (
    router as admin_permissions_router,
)
from presentation.fastapi.routers.admin.roles import router as admin_roles_router
from presentation.fastapi.routers.admin.system import router as admin_system_router
from presentation.fastapi.routers.admin.users import router as admin_users_router
from presentation.fastapi.routers.auth import router as auth_router
from presentation.fastapi.routers.health import router as health_router
from presentation.fastapi.routers.ui_settings import router as ui_settings_router
from shared.kernel.logging.logging_config import setup_logging
from shared.kernel.restart import (
    RestartScope,
    start_restart_watcher,
    stop_restart_watchers,
)
from shared.kernel.scheduling import stop_periodic_runners
from shared.kernel.settings.settings import settings
from shared.kernel.version import load_build_info


@asynccontextmanager
async def _lifespan(_app: FastAPI) -> AsyncIterator[None]:
    # Pick up restart requests from the admin console (to apply settings only read at startup)
    start_restart_watcher(RestartScope.WEB)
    # Grant bonuses to children's ledgers when the date changes (ADR-0024). Days missed while
    # stopped are caught up in the first pass right after startup
    start_daily_bonus_grants()
    # Re-check hourly and stop SSO sessions of people suspended at the IdP
    # (does nothing if MACHINE_CLIENT_ID is empty. ADR-0040)
    start_sso_reconciliation()
    try:
        yield
    finally:
        stop_restart_watchers()
        stop_periodic_runners()


def create_app() -> FastAPI:
    setup_logging(
        level=settings.log_level,
        database=settings.log_to_database and not settings.testing,
    )

    build_info = load_build_info()
    app = FastAPI(
        title="RewardPoints",
        version=build_info.version,
        description="人ごとのポイントを記録・共有する PWA のバックエンド（FastAPI + DDD）。",
        lifespan=_lifespan,
    )
    app.state.build_info = build_info
    app.state.startup_time = datetime.now(UTC)

    # With incomplete settings SSO silently fails as "enabled but unusable".
    # Whether the private key is readable is not even known until a user returns from the IdP.
    # Check once at startup and log the result (ADR-0029).
    report_sso_configuration()

    # Prometheus metrics at /metrics
    Instrumentator(excluded_handlers=["/metrics"]).instrument(app).expose(app, include_in_schema=False)

    # ``add_middleware`` stacks, so **whatever is added first ends up innermost**.
    # Put the layer that turns exceptions into responses innermost, so request logging (which
    # records the 500 line) and CORS (which adds response headers) always wrap it.
    #
    # Log rows are written to the DB after the request's DB session closes (writing midway
    # causes lock contention on SQLite and rows are lost. ADR-0012). Placing the batch writer
    # outside request logging puts the access log line into the same write.
    app.add_middleware(InternalErrorMiddleware)
    app.add_middleware(RequestLoggingMiddleware)
    app.add_middleware(DeferredLogWriteMiddleware)
    if settings.cors_allowed_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=list(settings.cors_allowed_origins),
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    # Logging of failures (4xx, input validation) and a safety net for crashes outside the middleware.
    # Specific domain exception handlers take precedence.
    register_error_handling(app)
    register_account_security_error_handler(app)
    register_reward_points_error_handler(app)
    register_identity_federation_error_handler(app)
    register_display_devices_error_handler(app)

    _include_routers(app)

    return app


def _include_routers(app: FastAPI) -> None:
    """Register routes. **The SPA must come last** (it is a catch-all)."""
    for router in (
        health_router,
        ui_settings_router,
        auth_router,
        passkey_login_router,
        sso_router,
        account_security_router,
        admin_users_router,
        admin_roles_router,
        admin_permissions_router,
        admin_config_router,
        admin_logs_router,
        admin_system_router,
        items_router,
        families_router,
        display_router,
    ):
        app.include_router(router)

    # Serve only when built.
    if spa.dist_available():
        app.include_router(spa.router)


__all__ = ["create_app"]
