"""切れたログインを、画面を出さずに続ける往復の後始末（ADR-0058）。

画面（SPA）は見えない枠（iframe）を開き、``/api/auth/sso/renew`` から IdP へ ``prompt=none`` で
往復させる。戻り（``/callback``）は**結果の頁**へ送る。画面は枠の行き先（同じオリジン）を読んで結果を知る
——枠の中でスクリプトを動かさない。

このアプリはトークンを画面の localStorage に持つ（Cookie ではない）。そのため続けられたときは、
結果の頁の URL に **1 回限りの引き換え券**を載せ、画面がそれを ``POST /api/auth/sso/token``
（``continuing: true``）でトークンへ換える。ログインの戻り（``/login/sso?ticket=…``）と同じ券である。

結果は 3 つ。

- ``renewed`` —— 続けられた（``ticket`` が付く）
- ``declined`` —— IdP で入っていない・許可が無い。画面はログイン画面へ送る
- ``failed`` —— 往復が壊れた（控えが無い・IdP と話せない）。画面はログイン画面へ送る

⚠ **枠に入れてよいのは自分のオリジンだけ。** 往復の口（``/renew``・続ける往復の ``/callback``）と結果の頁は
``X-Frame-Options: SAMEORIGIN`` と ``frame-ancestors 'self'`` を付ける。
"""

from __future__ import annotations

from enum import StrEnum
from urllib.parse import urlencode

from fastapi import Response
from fastapi.responses import HTMLResponse

#: 結果の頁。画面（``frontend/src/services/silentRenewal.ts``）と対で合わせる
RESULT_PATH = "/api/auth/sso/renewed"
RESULT_PARAM = "result"
TICKET_PARAM = "ticket"

#: 枠の中で開く応答の CSP。結果の頁は何も読み込まない（券が Referer で漏れる先も無い）
_FRAMED_CSP = "default-src 'none'; frame-ancestors 'self'"


class RenewalResult(StrEnum):
    RENEWED = "renewed"
    DECLINED = "declined"
    FAILED = "failed"


def allow_same_origin_framing(response: Response) -> Response:
    """自分のオリジンの枠にだけ入れてよい印を付ける。"""
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    response.headers["Content-Security-Policy"] = _FRAMED_CSP
    return response


def result_location(result: RenewalResult, ticket: str | None = None) -> str:
    """結果の頁の URL。続けられたときだけ引き換え券を載せる。"""
    query = {RESULT_PARAM: result.value}
    if ticket is not None:
        query[TICKET_PARAM] = ticket
    return f"{RESULT_PATH}?{urlencode(query)}"


def result_page() -> HTMLResponse:
    """結果の頁。中身は要らない（画面が読むのは URL だけ）。"""
    response = HTMLResponse(
        "<!doctype html><title>sso</title>",
        headers={"Cache-Control": "no-store", "Referrer-Policy": "no-referrer"},
    )
    allow_same_origin_framing(response)
    return response


__all__ = ["RESULT_PATH", "RenewalResult", "allow_same_origin_framing", "result_location", "result_page"]
