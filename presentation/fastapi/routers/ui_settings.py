"""Public API that serves the initial UI settings.

Operators set the default language and theme in the admin console (system_settings), but
the browser is what applies them. They are needed on pre-login screens too, so no auth is required.

A language or theme the user picked themselves wins via the browser's ``localStorage``; this
only returns "the initial value when nothing has been picked yet" and "the choices".
"""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from shared.kernel.settings.settings import settings

router = APIRouter(prefix="/api/ui", tags=["ui"])


class UiSettingsResponse(BaseModel):
    languages: list[str]
    default_locale: str
    default_theme: str


@router.get("/settings", response_model=UiSettingsResponse)
async def get_ui_settings() -> UiSettingsResponse:
    return UiSettingsResponse(
        languages=list(settings.languages),
        default_locale=settings.default_locale,
        default_theme=settings.default_theme,
    )
