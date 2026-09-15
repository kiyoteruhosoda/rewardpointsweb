"""SSO（OpenID Connect）ログイン API。

経路は 5 つ。

- ``GET /provider`` — ログイン画面が「SSO で入る」ボタンを出すかを問い合わせる
- ``GET /login`` — IdP の認可エンドポイントへブラウザを送り出す
- ``GET /callback`` — IdP からの戻り。引き換え券を付けて SPA へ戻す
- ``POST /token`` — 引き換え券をトークンへ換える（Cookie もここで載せる）
- ``POST /backchannel-logout`` — IdP からの停止の通知を受ける（ADR-0032）

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
from urllib.parse import parse_qsl, quote

from fastapi import APIRouter, Cookie, Depends, HTTPException, Query, Request, Response, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from bounded_contexts.account_security.application.use_cases.count_local_factors import (
    CountLocalFactors,
)
from bounded_contexts.account_security.infrastructure.sql_local_factor_directory import (
    SqlLocalFactorDirectory,
)
from bounded_contexts.identity_federation.application.use_cases.complete_sso_link import (
    CompleteSsoLink,
)
from bounded_contexts.identity_federation.application.use_cases.complete_sso_login import (
    CompleteSsoLogin,
)
from bounded_contexts.identity_federation.application.use_cases.describe_federated_link import (
    DescribeFederatedLink,
)
from bounded_contexts.identity_federation.application.use_cases.describe_round_trip import (
    DescribeRoundTrip,
)
from bounded_contexts.identity_federation.application.use_cases.describe_sso_provider import (
    DescribeSsoProvider,
)
from bounded_contexts.identity_federation.application.use_cases.exchange_sso_ticket import (
    ExchangeSsoTicket,
)
from bounded_contexts.identity_federation.application.use_cases.receive_backchannel_logout import (
    ReceiveBackchannelLogout,
)
from bounded_contexts.identity_federation.application.use_cases.start_sso_link import (
    StartSsoLink,
)
from bounded_contexts.identity_federation.application.use_cases.start_sso_login import (
    StartSsoLogin,
)
from bounded_contexts.identity_federation.application.use_cases.unlink_federated_identity import (
    UnlinkFederatedIdentity,
)
from bounded_contexts.identity_federation.domain.exceptions import (
    IdentityFederationError,
    InvalidLogoutTokenError,
    SsoLinkSessionMismatchError,
    SsoNotConfiguredError,
)
from bounded_contexts.identity_federation.domain.value_objects.sso_callback import (
    SsoCallback,
)
from bounded_contexts.identity_federation.presentation import dependencies
from bounded_contexts.identity_federation.presentation.schemas import (
    FederatedLinkResponse,
    SsoLinkStartResponse,
    SsoProviderResponse,
    SsoSessionResponse,
    SsoTicketRequest,
)
from presentation.fastapi.dependencies.auth import (
    get_active_principal,
    get_current_principal_or_none,
    set_access_token_cookie,
)
from presentation.fastapi.schemas.auth import StatusResponse
from presentation.fastapi.services.token_service import TokenService
from shared.application.authenticated_principal import AuthenticatedPrincipal
from shared.infrastructure.models import User
from shared.kernel.database.session import get_db
from shared.kernel.settings.settings import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth/sso", tags=["auth"])

DbDep = Annotated[Session, Depends(get_db)]

# 戻り先の SPA の経路（フロントエンドのルーティングと対で合わせる）
LOGIN_SCREEN = "/login"
HANDOFF_SCREEN = "/login/sso"
#: 連携の戻りの着地点（セキュリティ設定の画面。ADR-0036）
SECURITY_SCREEN = "/security"

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


class _CallbackTools:
    """戻りの後始末に要る道具（ADR-0036）。

    ログインの戻りと連携の戻りを 1 つの経路で受けるので、両方の道具をここへまとめる
    （ハンドラの引数を増やさないため。``SsoCallbackQuery`` と同じ書き方）。
    """

    def __init__(
        self,
        *,
        login: Annotated[CompleteSsoLogin, Depends(dependencies.complete_sso_login)],
        link: Annotated[CompleteSsoLink, Depends(dependencies.complete_sso_link)],
        purpose: Annotated[DescribeRoundTrip, Depends(dependencies.describe_round_trip)],
        viewer: Annotated[AuthenticatedPrincipal | None, Depends(get_current_principal_or_none)] = None,
    ) -> None:
        self.login = login
        self.link = link
        self.purpose = purpose
        self.viewer = viewer


@router.get("/callback", include_in_schema=False)
def complete_callback(
    *,
    query: Annotated[SsoCallbackQuery, Depends()],
    tools: Annotated[_CallbackTools, Depends()],
    binding: Annotated[str | None, Cookie(alias=SSO_BINDING_COOKIE)] = None,
) -> RedirectResponse:
    """IdP からの戻りを受け取る。ログインの戻りと連携の戻りを兼ねる（ADR-0036）。

    合言葉の Cookie は、成功しても失敗しても落とす（1 回の往復で使い切る）。

    ⚠ **どちらの往復かは控えが持っている。** クエリでは渡さない ——戻りの URL を
    書き換えるだけで化けさせられるため。
    """
    if query.error is not None or not query.code or not query.state:
        return _failed(query.error or "sso_callback_invalid")
    callback = SsoCallback(code=query.code, state=query.state, browser_binding=binding)
    if tools.purpose.execute(state=query.state) is not None:
        return _complete_link(callback, tools)
    return _complete_login(callback, tools)


def _complete_login(callback: SsoCallback, tools: _CallbackTools) -> RedirectResponse:
    """引き換え券を付けて SPA へ戻す。"""
    try:
        handoff = tools.login.execute(
            code=callback.code, state=callback.state, browser_binding=callback.browser_binding
        )
    except IdentityFederationError as error:
        return _failed(error.code)
    if handoff.account.linked:
        # 初めて結び付いた往復だけ 1 行残す（誰かは requestId から辿る。
        # CLAUDE.md「ログ」）。
        logger.info("sso_identity_linked")
    return _redirect(f"{HANDOFF_SCREEN}?ticket={quote(handoff.ticket)}")


def _complete_link(callback: SsoCallback, tools: _CallbackTools) -> RedirectResponse:
    """戻ってきた相手を、往復を始めた利用者へ結び付けて設定画面へ返す。

    ⚠ **いま入っている利用者を見て決め直さない。** 誰に結び付けるかは往復を始めた
    時点で決まっている（控えの ``link_user_id``）。ここで見るのは「その本人が
    まだ入っているか」だけで、入れ替わっていれば断る。
    """
    viewer = tools.viewer
    if viewer is None:
        return _link_failed(SsoLinkSessionMismatchError.code)
    try:
        tools.link.execute(callback=callback, user_id=viewer.user_id)
    except IdentityFederationError as error:
        logger.warning("sso_link_failed: %s", error.code)
        return _link_failed(error.code)
    logger.info("sso_link_succeeded")
    return _redirect(f"{SECURITY_SCREEN}?sso_link=linked")


@router.post("/link/start", response_model=SsoLinkStartResponse)
def start_link(
    *,
    principal: Annotated[AuthenticatedPrincipal, Depends(get_active_principal)],
    use_case: Annotated[StartSsoLink, Depends(dependencies.start_sso_link)],
    response: Response,
) -> SsoLinkStartResponse:
    """連携の往復を始める。**画面はこの URL へ自分で遷移する**（ADR-0036）。

    303 を返さず XHR にしているのは、⚠ **認証が切れている相手に 401 を返せる**
    ようにするため。画面遷移で始めると、切れていた場合に JSON の生本文が
    見えるだけで、やり直す導線が出せない。

    ⚠ **CSRF の守りはここで効く。** Cookie で認証する更新系なので
    ``CsrfMiddleware`` の対象になり、よその頁からは起こせない。
    """
    authorization = use_case.execute(user_id=principal.user_id)
    response.set_cookie(
        SSO_BINDING_COOKIE,
        authorization.browser_binding,
        max_age=settings.oidc_login_session_ttl_seconds,
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite="lax",
        path=router.prefix,
    )
    return SsoLinkStartResponse(authorization_url=authorization.authorization_url)


@router.get("/link", response_model=FederatedLinkResponse)
def describe_link(
    *,
    principal: Annotated[AuthenticatedPrincipal, Depends(get_active_principal)],
    use_case: Annotated[DescribeFederatedLink, Depends(dependencies.describe_federated_link)],
    db: DbDep,
) -> FederatedLinkResponse:
    """自分の連携の状態を答える（ADR-0036）。他人の分は見えない。"""
    link = use_case.execute(user_id=principal.user_id)
    return FederatedLinkResponse(
        available=link.available,
        display_name=link.display_name,
        linked=link.linked,
        linked_at=link.linked_at,
        can_unlink=link.linked and _has_other_entrance(db, principal.user_id),
    )


@router.delete("/link", response_model=StatusResponse)
def remove_link(
    *,
    principal: Annotated[AuthenticatedPrincipal, Depends(get_active_principal)],
    use_case: Annotated[UnlinkFederatedIdentity, Depends(dependencies.unlink_federated_identity)],
    db: DbDep,
) -> StatusResponse:
    """連携を外す。⚠ **外すと入れなくなる利用者は断る**（ADR-0036）。"""
    provider = dependencies.identity_provider()
    if provider is None:
        raise SsoNotConfiguredError
    use_case.execute(
        issuer=provider.issuer,
        user_id=principal.user_id,
        has_other_entrance=_has_other_entrance(db, principal.user_id),
    )
    logger.info("sso_identity_unlinked")
    return StatusResponse(status="ok")


def _has_other_entrance(db: Session, user_id: int) -> bool:
    """IdP を外したあとも、この利用者に**入り口**が残るか。

    ⚠ **二要素認証は入り口ではない。** パスワードの後ろに置く second factor なので、
    それだけでは入れない。数えるのはパスワードとパスキーである。
    """
    user = db.get(User, user_id)
    if user is None:  # pragma: no cover - 認証を通った直後に消えた場合のみ
        return False
    if user.has_local_password:
        return True
    return CountLocalFactors(SqlLocalFactorDirectory(db)).for_user(user_id).passkeys > 0


def _link_failed(code: str) -> RedirectResponse:
    """連携の失敗を設定画面へ返す。

    ⚠ **ログイン画面へ戻さない。** 押した人は入ったままなので、ログイン画面へ
    送ると「入っているのに入り直せと言われる」ことになる。
    """
    safe = code if _ERROR_CODE.fullmatch(code) else _GENERIC_ERROR
    return _redirect(f"{SECURITY_SCREEN}?sso_link_error={safe}")


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
    pair = TokenService.create_token_pair(user, federated_login=session.login)
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


# 通知の本体は ``application/x-www-form-urlencoded`` の 1 フィールドだけ。**``Form()`` を
# 使わない**——FastAPI の ``Form`` は ``python-multipart`` を要求するので、この 1 か所の
# ために依存を 1 つ増やすことになる。
#: 受け取る本文の上限。``logout_token`` 1 本しか入らないので、これで充分に広い。
_LOGOUT_BODY_MAX_BYTES = 16 * 1024


@router.post("/backchannel-logout", include_in_schema=False)
async def receive_backchannel_logout(
    request: Request,
    use_case: Annotated[ReceiveBackchannelLogout, Depends(dependencies.receive_backchannel_logout)],
) -> StatusResponse:
    """IdP からの停止の通知を受ける（OpenID Connect Back-Channel Logout 1.0。ADR-0032）。

    ⚠ **この口は未認証で叩ける。** 相手の証明は ``logout_token`` の署名だけなので、
    検証を通らないものは理由を返さずに 400 で落とす（どこまで通ったかを教えない）。

    ⚠ **応答は「受け取った」だけを意味する。** 実際にセッションが終わるのは、次に
    そのトークンが提示されたときである（サーバーにセッションの控えが無いため）。

    検証では discovery と JWKS の同期 HTTP が出るので、処理はスレッドプールへ逃がす
    （``/login`` や ``/callback`` を ``def`` にしているのと同じ理由）。
    """
    logout_token = _logout_token_of(await _bounded_body(request))
    notice = await run_in_threadpool(use_case.execute, logout_token=logout_token)
    logger.info(
        "sso_backchannel_logout_received: scope=%s",
        "session" if notice.session.session_id else "subject",
    )
    return StatusResponse(status="ok")


async def _bounded_body(request: Request) -> bytes:
    """本文を読む。**大きすぎるものは読まずに断る**（未認証で叩ける口のため）。"""
    declared = request.headers.get("Content-Length")
    if declared is not None and declared.isdigit() and int(declared) > _LOGOUT_BODY_MAX_BYTES:
        raise InvalidLogoutTokenError
    body = await request.body()
    if len(body) > _LOGOUT_BODY_MAX_BYTES:
        raise InvalidLogoutTokenError
    return body


def _logout_token_of(body: bytes) -> str:
    """``logout_token=<JWT>`` を取り出す。無い・空・複数あるものは受け取らない。"""
    values = [value for name, value in parse_qsl(body.decode("ascii", "replace")) if name == "logout_token"]
    if len(values) != 1 or not values[0]:
        raise InvalidLogoutTokenError
    return values[0]
