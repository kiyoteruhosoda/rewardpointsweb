"""Password length rules.

The upper limit stops callers from sending huge strings to endpoints reachable without login
(login, password reset) to force hash computation (task #733). 128 characters is enough for passphrases.
"""

from __future__ import annotations

MIN_LENGTH = 8
MAX_LENGTH = 128

__all__ = ["MAX_LENGTH", "MIN_LENGTH"]
