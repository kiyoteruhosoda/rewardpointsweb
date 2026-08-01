"""パスワードリセット（トークン発行・メール送信・再設定）。

トークンは平文を保存せず SHA-256 ハッシュのみを保存する。

申し込みの識別子は **ユーザー名**。メールアドレスは任意項目になったので、
「そのアドレスの持ち主」を起点にできない（ADR-0011）。応答は
:class:`ResetOutcome` の 3 種類で、``NO_EMAIL`` だけは「親に頼んでください」と
案内するために区別する。メールアドレスを持たない子アカウントに「送りました」と
返すと、届かないメールを待たせることになるため。

区別する以上、その 1 つは「そのユーザー名は実在し、メールアドレスを持たない」
ことを意味する。家庭内で使う識別子であること（親が決めて本人へ伝える）を踏まえ、
この範囲の露出は許容する。
"""

from __future__ import annotations

import hashlib
import logging
import secrets
from datetime import timedelta
from enum import Enum

from sqlalchemy import select
from sqlalchemy.orm import Session

from bounded_contexts.email_sender.application.send_email import SendEmail
from bounded_contexts.email_sender.domain.email_message import EmailMessage
from bounded_contexts.email_sender.domain.email_sender import (
    EmailSendingDisabledError,
    IEmailSender,
)
from bounded_contexts.email_sender.infrastructure.smtp_email_sender import (
    SmtpEmailSender,
)
from shared.domain.auth.username import Username
from shared.infrastructure.models import PasswordResetToken, User
from shared.infrastructure.models.base import utcnow
from shared.kernel.settings.settings import settings

logger = logging.getLogger(__name__)


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


class ResetOutcome(Enum):
    """申し込みの結果。"""

    #: リセットリンクを送った（あるいは、そのユーザー名が存在しなかった）
    ACCEPTED = "accepted"
    #: 実在するがメールアドレスを持たない。回復は親からの一時パスワードで行う
    ASK_GUARDIAN = "ask_guardian"


class PasswordResetService:
    def __init__(self, sender: IEmailSender | None = None) -> None:
        self._sender = sender or SmtpEmailSender()

    def request_reset(self, session: Session, username: str) -> ResetOutcome:
        """リセットトークンを発行しメールを送る。

        ユーザー不在なら黙って ``ACCEPTED`` を返す（存在の有無を漏らさない）。
        """
        user = self._find(session, username)
        if user is None or not user.is_active:
            logger.info("password_reset_requested_unknown_account")
            return ResetOutcome.ACCEPTED
        if user.email is None:
            # 送る先が無い。メール送信は試みず、親への依頼を促す（ADR-0011）
            logger.info("password_reset_requested_without_email")
            return ResetOutcome.ASK_GUARDIAN

        token = secrets.token_urlsafe(32)
        session.add(
            PasswordResetToken(
                user_id=user.id,
                token_hash=_hash_token(token),
                expires_at=utcnow() + timedelta(seconds=settings.password_reset_token_ttl_seconds),
            )
        )
        session.flush()

        base_url = settings.app_base_url.rstrip("/")
        link = f"{base_url}/reset-password?token={token}"
        try:
            SendEmail(self._sender).execute(
                EmailMessage(
                    to=user.email,
                    subject="Password reset",
                    body=(
                        "A password reset was requested for your account.\n"
                        f"Open the following link to set a new password:\n{link}\n\n"
                        "If you did not request this, you can ignore this mail."
                    ),
                )
            )
        except EmailSendingDisabledError:
            logger.warning("password_reset_mail_disabled")
        return ResetOutcome.ACCEPTED

    @staticmethod
    def _find(session: Session, username: str) -> User | None:
        try:
            identifier = Username(username).value
        except ValueError:
            return None
        return session.scalar(select(User).where(User.username == identifier))

    def reset(self, session: Session, token: str, new_password: str) -> bool:
        """トークンを検証してパスワードを更新する。成功時 True。"""
        from werkzeug.security import generate_password_hash

        row = session.scalar(select(PasswordResetToken).where(PasswordResetToken.token_hash == _hash_token(token)))
        if row is None or row.used_at is not None or row.expires_at < utcnow():
            return False
        user = session.get(User, row.user_id)
        if user is None or not user.is_active:
            return False
        user.password_hash = generate_password_hash(new_password)
        # 親が発行した一時パスワードの途中でも、本人がメールから再設定できる。
        # 期限を残すと、そのまま新しいパスワードまで期限切れ扱いになってしまう。
        user.must_change_password = False
        user.temporary_password_expires_at = None
        row.used_at = utcnow()
        session.flush()
        return True


__all__ = ["PasswordResetService", "ResetOutcome"]
