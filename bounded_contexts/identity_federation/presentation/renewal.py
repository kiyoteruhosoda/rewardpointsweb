"""Wrap-up of the round trip that continues an expired login without showing a screen (ADR-0058).

The screen (SPA) opens a hidden frame (iframe) and makes a ``prompt=none`` round trip to the IdP via
``/api/auth/sso/renew``. The return (``/callback``) is sent to **the result page**. The screen learns the result by
reading where the frame ended up (same origin) -- no script runs inside the frame.

This app keeps tokens in the screen's localStorage (not cookies). So when the login can be continued, a
**one-time exchange ticket** is put in the result page URL, and the screen exchanges it for tokens with
``POST /api/auth/sso/token`` (``continuing: true``). It is the same ticket as on the login return
(``/login/sso?ticket=…``).

There are three results.

- ``renewed`` -- continued (``ticket`` is attached)
- ``declined`` -- not signed in at the IdP, or not permitted. The screen goes to the login screen
- ``failed`` -- the round trip broke (no record, IdP unreachable). The screen goes to the login screen

⚠ **Only our own origin may frame these.** The round-trip endpoints (``/renew``, ``/callback`` of a continuing
round trip) and the result page carry ``X-Frame-Options: SAMEORIGIN`` and ``frame-ancestors 'self'``.
"""

from __future__ import annotations

from enum import StrEnum
from urllib.parse import urlencode

from fastapi import Response
from fastapi.responses import HTMLResponse

#: The result page. Keep in sync with the screen (``frontend/src/services/silentRenewal.ts``)
RESULT_PATH = "/api/auth/sso/renewed"
RESULT_PARAM = "result"
TICKET_PARAM = "ticket"

#: CSP for responses opened inside the frame. The result page loads nothing (so there is nowhere for the ticket
#: to leak via Referer)
_FRAMED_CSP = "default-src 'none'; frame-ancestors 'self'"


class RenewalResult(StrEnum):
    RENEWED = "renewed"
    DECLINED = "declined"
    FAILED = "failed"


def allow_same_origin_framing(response: Response) -> Response:
    """Mark the response as frameable only by our own origin."""
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    response.headers["Content-Security-Policy"] = _FRAMED_CSP
    return response


def result_location(result: RenewalResult, ticket: str | None = None) -> str:
    """URL of the result page. The exchange ticket is included only when the login was continued."""
    query = {RESULT_PARAM: result.value}
    if ticket is not None:
        query[TICKET_PARAM] = ticket
    return f"{RESULT_PATH}?{urlencode(query)}"


def result_page() -> HTMLResponse:
    """The result page. No content is needed (the screen reads only the URL)."""
    response = HTMLResponse(
        "<!doctype html><title>sso</title>",
        headers={"Cache-Control": "no-store", "Referrer-Policy": "no-referrer"},
    )
    allow_same_origin_framing(response)
    return response


__all__ = ["RESULT_PATH", "RenewalResult", "allow_same_origin_framing", "result_location", "result_page"]
