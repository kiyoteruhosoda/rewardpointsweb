"""SSO（OpenID Connect）ログイン API。

経路は 4 つ。

- ``GET /provider`` — ログイン画面が「SSO で入る」ボタンを出すかを問い合わせる
- ``GET /login`` — IdP の認可エンドポイントへブラウザを送り出す
- ``GET /callback`` — IdP からの戻り。引き換え券を付けて SPA へ戻す
- ``POST /token`` — 引き換え券をトークンへ換える（Cookie もここで載せる）

``/login`` は**ブラウザに合言葉の Cookie を持たせてから**送り出す。控えの表は
全員で共有するので、``state`` を知っているだけの相手でも戻りを完了できてしまう
（攻撃者が始めた認可要求を被害者に踏ませると、被害者は攻撃者としてログインした
状態になる。ログイン CSRF）。``/callback`` はこの Cookie が一致することまで見る。

``/login`` と ``/callback`` は**ブラウザの画面遷移**で、応答本文を SPA は読めない。
そのため失敗も JSON ではなくログイン画面への転送で返す（``?sso_error=<code>``）。
表示文言はフロントエンドが決める（CLAUDE.md「国際化」）。

トークンを URL に載せないための引き換え券は ADR-0029。
"""

from __future__ import annotations

import logging
import re
from typing import Annotated
from urllib.parse import quote

from fastapi import APIRouter, Cookie, Depends, HTTPException, Query, Response, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from bounded_contexts.identity_federation.application.use_cases.complete_sso_login import (
    CompleteSsoLogin,
)
from bounded_contexts.identity_federation.application.use_cases.describe_sso_provider import (
    DescribeSsoProvider,
)
from bounded_contexts.identity_federation.application.use_cases.exchange_sso_ticket import (
    ExchangeSsoTicket,
)
from bounded_contexts.identity_federation.application.use_cases.start_sso_login import (
    StartSsoLogin,
)
from bounded_contexts.identity_federation.domain.exceptions import (
    IdentityFederationError,
)
from bounded_contexts.identity_federation.presentation import dependencies
from bounded_contexts.identity_federation.presentation.schemas import (
    SsoProviderResponse,
    SsoSessionResponse,
    SsoTicketRequest,
)
from presentation.fastapi.dependencies.auth import set_access_token_cookie
from presentation.fastapi.services.token_service import TokenService
from shared.infrastructure.models import User
from shared.kernel.database.session import get_db
from shared.kernel.settings.settings import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth/sso", tags=["auth"])

DbDep = Annotated[Session, Depends(get_db)]

# 戻り先の SPA の経路（フロントエンドのルーティングと対で合わせる）
LOGIN_SCREEN = "/login"
HANDOFF_SCREEN = "/login/sso"

# 認可要求を出したブラウザに持たせる合言葉。``SameSite=Lax`` にするのは、
# IdP からの戻りが**別サイトからの GET の画面遷移**だから（``Strict`` だと
# 戻ってきた時点で送られず、正規のログインが必ず失敗する）。
SSO_BINDING_COOKIE = "sso_binding"

# IdP が返すエラーコードはそのまま画面の URL へ載るため、素性の分かる形だけを通す
# （反射した文字列でリンクを組み立てられないようにする）。照合は ``fullmatch``——
# ``$`` は末尾の改行の直前にも当たるため、``match`` だと改行を通してしまう。
_ERROR_CODE = re.compile(r"[a-z_]{1,64}")
_GENERIC_ERROR = "sso_error"


class SsoCallbackQuery:
    """IdP からの戻りに付くクエリ（成功なら ``code`` と ``state``）。"""

    def __init__(
        self,
        code: Annotated[str | None, Query(max_length=2048)] = None,
        state: Annotated[str | None, Query(max_length=255)] = None,
        error: Annotated[str | None, Query(max_length=255)] = None,
    ) -> None:
        self.code = code
        self.state = state
        self.error = error


@router.get("/provider", response_model=SsoProviderResponse)
async def describe_provider(
    use_case: Annotated[DescribeSsoProvider, Depends(dependencies.describe_sso_provider)],
) -> SsoProviderResponse:
    """SSO が使えるかを答える（未認証で呼べる。接続先の情報は返さない）。"""
    provider = use_case.execute()
    return SsoProviderResponse(enabled=provider.enabled, display_name=provider.display_name)


# ``/login`` と ``/callback`` は IdP へ同期の HTTP を出す（discovery・トークン交換）。
# ``async def`` にするとその往復のあいだイベントループが止まり、同じワーカーの
# 全リクエストが待たされる。``def`` で定義してスレッドプールへ逃がす。
@router.get("/login", include_in_schema=False)
def start_login(
    use_case: Annotated[StartSsoLogin, Depends(dependencies.start_sso_login)],
    redirect_to: Annotated[str | None, Query(max_length=255)] = None,
) -> RedirectResponse:
    """IdP へ送り出す。設定が無い・IdP と話せない場合はログイン画面へ戻す。"""
    try:
        authorization = use_case.execute(redirect_to=redirect_to)
    except IdentityFederationError as error:
        logger.warning("sso_start_failed: %s", error.code)
        return _to_login_screen(error.code)
    response = RedirectResponse(url=authorization.authorization_url, status_code=status.HTTP_303_SEE_OTHER)
    response.set_cookie(
        SSO_BINDING_COOKIE,
        authorization.browser_binding,
        max_age=settings.oidc_login_session_ttl_seconds,
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite="lax",
        path=router.prefix,
    )
    return response


@router.get("/callback", include_in_schema=False)
def complete_login(
    query: Annotated[SsoCallbackQuery, Depends()],
    use_case: Annotated[CompleteSsoLogin, Depends(dependencies.complete_sso_login)],
    binding: Annotated[str | None, Cookie(alias=SSO_BINDING_COOKIE)] = None,
) -> RedirectResponse:
    """IdP からの戻りを受け取り、引き換え券を付けて SPA へ戻す。

    合言葉の Cookie は、成功しても失敗しても落とす（1 回の往復で使い切る）。
    """
    if query.error is not None or not query.code or not query.state:
        return _failed(query.error or "sso_callback_invalid")
    try:
        handoff = use_case.execute(code=query.code, state=query.state, browser_binding=binding)
    except IdentityFederationError as error:
        return _failed(error.code)
    if handoff.account.linked:
        # 初めて結び付いた往復だけ 1 行残す（誰かは requestId から辿る。
        # CLAUDE.md「ログ」）。
        logger.info("sso_identity_linked")
    return _redirect(f"{HANDOFF_SCREEN}?ticket={quote(handoff.ticket)}")


@router.post("/token", response_model=SsoSessionResponse)
async def exchange_ticket(
    *,
    body: SsoTicketRequest,
    response: Response,
    db: DbDep,
    use_case: Annotated[ExchangeSsoTicket, Depends(dependencies.exchange_sso_ticket)],
) -> SsoSessionResponse:
    """引き換え券をトークンへ換える（1 回限り）。

    一時パスワードの状態（``must_change_password``）は SSO で入っても解けない。
    ここで黙って落とすと、親が発行した一時パスワードの意味が無くなる（ADR-0011）。
    """
    session = use_case.execute(ticket=body.ticket)
    user = db.get(User, session.user_id)
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "invalid_credentials"},
        )
    pair = TokenService.create_token_pair(user)
    set_access_token_cookie(response, str(pair["access_token"]))
    logger.info("sso_login_succeeded")
    return SsoSessionResponse(
        access_token=str(pair["access_token"]),
        refresh_token=str(pair["refresh_token"]),
        token_type=str(pair["token_type"]),
        expires_in=int(str(pair["expires_in"])),
        must_change_password=user.must_change_password,
        redirect_to=session.redirect_to,
    )


def _redirect(url: str) -> RedirectResponse:
    """SPA へ戻す。合言葉の Cookie はここで落とす（往復が終わったため）。"""
    response = RedirectResponse(url=url, status_code=status.HTTP_303_SEE_OTHER)
    response.delete_cookie(SSO_BINDING_COOKIE, path=router.prefix)
    return response


def _to_login_screen(code: str) -> RedirectResponse:
    safe = code if _ERROR_CODE.fullmatch(code) else _GENERIC_ERROR
    return _redirect(f"{LOGIN_SCREEN}?sso_error={safe}")


def _failed(reason: str) -> RedirectResponse:
    """失敗を記録してログイン画面へ戻す。

    誰が試したかは書かない。SSO のログインが通っていない時点では分かっていない。
    """
    safe = reason if _ERROR_CODE.fullmatch(reason) else _GENERIC_ERROR
    logger.warning("sso_login_failed: %s", safe)
    return _to_login_screen(safe)


__all__ = ["HANDOFF_SCREEN", "LOGIN_SCREEN", "SSO_BINDING_COOKIE", "router"]
