"""パスワードリセット（トークン発行・メール送信・再設定）。

トークンは平文を保存せず SHA-256 ハッシュのみを保存する。

申し込みの識別子は **ユーザー名**。メールアドレスは任意項目になったので、
「そのアドレスの持ち主」を起点にできない（ADR-0011）。応答は
:class:`ResetOutcome` の 3 種類で、``ASK_GUARDIAN`` だけは「親に頼んでください」と
案内するために区別する。メールアドレスを持たない子アカウントに「送りました」と
返すと、届かないメールを待たせることになるため。

区別する以上、その 1 つは「そのユーザー名は実在し、メールアドレスを持たない」
ことを意味する。家庭内で使う識別子であること（親が決めて本人へ伝える）を踏まえ、
この範囲の露出は許容する。

同じ理由で ``MAIL_UNAVAILABLE`` を持つ。``MAIL_ENABLED`` が無効な運用や SMTP が
落ちている間に「送りました」と返すと、決して届かないメールを待たせることになり、
ログイン不能からの回復手段が事実上失われる。送信可否は利用者に依らないので、
実在しないユーザー名でも同じ応答になり、実在は漏れない。

そして発行したリンクは **必ずログへ出す**。メールが届かない場面でも運用者が
本人へ手渡せる経路を残すため。ログを読める人はそのリンクでアカウントを乗っ取れる
ので、ログの取り扱いは管理者に限ること。
"""

from __future__ import annotations

import hashlib
import logging
import secrets
import smtplib
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
    #: メールを送れない（``MAIL_ENABLED`` が無効、または SMTP に届かない）。
    #: 待たせても届かないので、親からの一時パスワードへ誘導する
    MAIL_UNAVAILABLE = "mail_unavailable"


class PasswordResetService:
    def __init__(self, sender: IEmailSender | None = None) -> None:
        self._sender = sender or SmtpEmailSender()

    def request_reset(self, session: Session, username: str) -> ResetOutcome:
        """リセットトークンを発行し、ログへ出したうえでメールを送る。

        ユーザー不在なら黙って「送信手段があれば ``ACCEPTED``」を返す（存在の
        有無を漏らさない）。送信手段が無い運用では、実在・不在にかかわらず
        ``MAIL_UNAVAILABLE`` を返すので、ここでも実在は漏れない。
        """
        user = self._find(session, username)
        if user is None or not user.is_active:
            logger.info("password_reset_requested_unknown_account")
            # 応答は実在するアカウントと揃える（送信可否だけで決める）
            return ResetOutcome.ACCEPTED if settings.mail_enabled else ResetOutcome.MAIL_UNAVAILABLE
        if user.email is None:
            # 送る先が無い。メール送信は試みず、親への依頼を促す（ADR-0011）
            logger.info("password_reset_requested_without_email")
            return ResetOutcome.ASK_GUARDIAN

        link = self._issue_link(session, user)
        # メールが届かない場面（MAIL_ENABLED 無効・SMTP 障害）でも運用者が本人へ
        # 手渡せるよう、リンクは必ずログへ出す。ログを読める人はこのリンクで
        # アカウントを乗っ取れるため、ログの取り扱いは管理者に限ること。
        logger.warning("password_reset_link_issued: %s", link)

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
            # MAIL_ENABLED が無効。リンクはログに出してあるので運用者が手渡せる
            logger.warning("password_reset_unavailable: mail_disabled")
            return ResetOutcome.MAIL_UNAVAILABLE
        except (OSError, smtplib.SMTPException):
            # SMTP に届かない。以前はここが 500 になり、利用者には原因の分からない
            # 失敗として出ていた。回復手段を案内できる形にする
            logger.exception("password_reset_unavailable: mail_send_failed")
            return ResetOutcome.MAIL_UNAVAILABLE
        return ResetOutcome.ACCEPTED

    @staticmethod
    def _issue_link(session: Session, user: User) -> str:
        """トークンを 1 つ発行し、再設定画面の URL を組み立てる。"""
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
        return f"{base_url}/reset-password?token={token}"

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
