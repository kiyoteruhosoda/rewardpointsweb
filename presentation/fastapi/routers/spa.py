"""Serving the SPA (frontend/dist).

Mounted only when a built frontend exists. Paths other than the API and docs
fall back to ``index.html`` (for React Router history mode).

Served files come in two kinds with different caching.

- Under ``assets/``: Vite writes them with content-hashed names. When the content changes
  the URL changes too, so they can be cached without expiry.
- Everything else (``index.html``, ``sw.js``, ``manifest.webmanifest``, icons):
  the content changes under the same name. Without ``no-cache`` (= revalidate every time),
  devices keep the old version and neither the screen nor the icon changes after a deploy.

``no-cache`` means "revalidate every time", not "download every time". If the ``ETag``
matches, return 304 without a body (``FileResponse`` sets ``ETag`` but ignores
conditional requests, so the check is done here).
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import FileResponse, Response

DIST_DIR = Path(__file__).resolve().parents[3] / "frontend" / "dist"

INDEX_HTML = "index.html"
HASHED_ASSETS_PREFIX = "assets/"
CACHE_IMMUTABLE = "public, max-age=31536000, immutable"
CACHE_REVALIDATE = "no-cache"

# Headers that must be sent even with a 304 (RFC 9110 §15.4.5).
_NOT_MODIFIED_HEADERS = ("etag", "cache-control", "last-modified", "vary")

router = APIRouter(include_in_schema=False)


def dist_available() -> bool:
    return (DIST_DIR / INDEX_HTML).is_file()


def _cache_control(relative_path: str) -> str:
    if relative_path.startswith(HASHED_ASSETS_PREFIX):
        return CACHE_IMMUTABLE
    return CACHE_REVALIDATE


def _matches_etag(request: Request, etag: str | None) -> bool:
    """Whether ``If-None-Match`` contains our ``ETag``."""
    if etag is None:
        return False
    header = request.headers.get("if-none-match")
    if header is None:
        return False
    if header.strip() == "*":
        return True
    return any(candidate.strip() == etag for candidate in header.split(","))


def _not_modified(response: FileResponse) -> Response:
    headers = {name: response.headers[name] for name in _NOT_MODIFIED_HEADERS if name in response.headers}
    return Response(status_code=304, headers=headers)


def _serve(file_path: Path, relative_path: str, request: Request) -> Response:
    # Passing stat_result fixes ETag / Last-Modified at construction (without it they are not
    # set until just before the body is sent, so the conditional request cannot be checked here).
    response = FileResponse(
        file_path,
        headers={"cache-control": _cache_control(relative_path)},
        stat_result=file_path.stat(),
    )
    if _matches_etag(request, response.headers.get("etag")):
        return _not_modified(response)
    return response


@router.get("/")
async def index(request: Request) -> Response:
    return _serve(DIST_DIR / INDEX_HTML, INDEX_HTML, request)


@router.get("/{path:path}")
async def spa_fallback(path: str, request: Request) -> Response:
    candidate = (DIST_DIR / path).resolve()
    # Serve existing static files as is while preventing path traversal
    if candidate.is_file() and candidate.is_relative_to(DIST_DIR):
        return _serve(candidate, path, request)
    return _serve(DIST_DIR / INDEX_HTML, INDEX_HTML, request)
