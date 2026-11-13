"""QR code rendering.

For display, so the authenticator app can read the TOTP ``otpauth://`` URI. Drawn as SVG, so it
does not depend on an image library (Pillow) and does not get blurry when scaled.
"""

from __future__ import annotations

import base64
import io

import qrcode
from qrcode.image.svg import SvgPathImage


def render_qr_code_data_uri(value: str) -> str:
    """Return a QR code encoding *value* as an SVG data URI."""
    buffer = io.BytesIO()
    qrcode.make(value, image_factory=SvgPathImage).save(buffer)
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f"data:image/svg+xml;base64,{encoded}"


__all__ = ["render_qr_code_data_uri"]
