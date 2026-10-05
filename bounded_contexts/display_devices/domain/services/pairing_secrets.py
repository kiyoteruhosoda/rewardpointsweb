"""ペアリングで使う値の生成と、その保存形（ADR-0047）。

- 確認コード（``user_code``）: 人が読み・打つ。紛らわしい字（0/O・1/I/L）を除いた
  大文字と数字の 8 字で、4 字ずつ ``-`` で区切って見せる
- 端末の秘密（``device_code``）・端末の資格情報（``device_credential``）: 推測できない
  ことだけが要件。32 バイトの乱数

どれも持ち主へ渡す資格情報なので、DB へは SHA-256 のハッシュだけを置く。
"""

from __future__ import annotations

import hashlib
import secrets

USER_CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
USER_CODE_LENGTH = 8
_USER_CODE_GROUP = 4
_SECRET_BYTES = 32


def new_user_code() -> str:
    """確認コード（区切りなしの 8 字）。見せるときは :func:`format_user_code` を通す。"""
    return "".join(secrets.choice(USER_CODE_ALPHABET) for _ in range(USER_CODE_LENGTH))


def format_user_code(code: str) -> str:
    """``KQ7M3XPA`` → ``KQ7M-3XPA``。"""
    return f"{code[:_USER_CODE_GROUP]}-{code[_USER_CODE_GROUP:]}"


def normalize_user_code(raw: str) -> str | None:
    """人が打った確認コードを、保存した形（区切りなしの大文字）へ揃える。

    区切り・空白・小文字は許す。使わない字が混じる・長さが違うなら ``None``
    （照合するまでもなく存在しない）。
    """
    code = "".join(ch for ch in raw.upper() if ch.isalnum())
    if len(code) != USER_CODE_LENGTH or any(ch not in USER_CODE_ALPHABET for ch in code):
        return None
    return code


def new_secret() -> str:
    """端末の秘密・端末の資格情報。"""
    return secrets.token_urlsafe(_SECRET_BYTES)


def hash_secret(value: str) -> str:
    """保存用のハッシュ。突き合わせは常にハッシュ同士で行う。"""
    return hashlib.sha256(value.encode()).hexdigest()


__all__ = [
    "USER_CODE_ALPHABET",
    "USER_CODE_LENGTH",
    "format_user_code",
    "hash_secret",
    "new_secret",
    "new_user_code",
    "normalize_user_code",
]
