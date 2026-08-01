"""FastAPI アプリケーションファクトリ。"""

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
from bounded_contexts.example.presentation.router import router as items_router
from bounded_contexts.reward_points.presentation.error_handling import (
    register_reward_points_error_handler,
)
from bounded_contexts.reward_points.presentation.router import router as families_router
from presentation.fastapi.error_handling import register_error_handling
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
from shared.kernel.settings.settings import settings
from shared.kernel.version import load_build_info


@asynccontextmanager
async def _lifespan(_app: FastAPI) -> AsyncIterator[None]:
    # 管理画面からの再起動要求を拾う（起動時にしか読まれない設定の反映用）
    start_restart_watcher(RestartScope.WEB)
    try:
        yield
    finally:
        stop_restart_watchers()


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

    # Prometheus metrics at /metrics
    Instrumentator(excluded_handlers=["/metrics"]).instrument(app).expose(app, include_in_schema=False)

    # ``add_middleware`` は積み増しなので、**先に足したものほど内側**になる。
    # 例外を応答へ変える層を最も内側に置き、リクエストログ（500 の行を残す）と
    # CORS（応答ヘッダーを付ける）が必ずその外側を通るようにする。
    app.add_middleware(InternalErrorMiddleware)
    app.add_middleware(RequestLoggingMiddleware)
    if settings.cors_allowed_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=list(settings.cors_allowed_origins),
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    # 失敗の記録（4xx・入力検証）と、ミドルウェアより外側で落ちたとき用の保険。
    # 個別のドメイン例外ハンドラが優先される。
    register_error_handling(app)
    register_account_security_error_handler(app)
    register_reward_points_error_handler(app)

    app.include_router(health_router)
    app.include_router(ui_settings_router)
    app.include_router(auth_router)
    app.include_router(passkey_login_router)
    app.include_router(account_security_router)
    app.include_router(admin_users_router)
    app.include_router(admin_roles_router)
    app.include_router(admin_permissions_router)
    app.include_router(admin_config_router)
    app.include_router(admin_logs_router)
    app.include_router(admin_system_router)
    app.include_router(items_router)
    app.include_router(families_router)

    # SPA は最後（catch-all のため）。ビルド済みの場合のみ配信する。
    if spa.dist_available():
        app.include_router(spa.router)

    return app


__all__ = ["create_app"]
