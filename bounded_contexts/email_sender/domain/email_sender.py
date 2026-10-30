from abc import ABC, abstractmethod

from bounded_contexts.email_sender.domain.email_message import EmailMessage


class EmailSendingDisabledError(Exception):
    """メール送信が無効（``MAIL_ENABLED`` 未設定）のときに送出される。"""


class IEmailSender(ABC):
    @abstractmethod
    def send(self, message: EmailMessage) -> None: ...

    @abstractmethod
    def check_reachable(self) -> None:
        """送らずに、送り先のサーバーへ届くかだけを確かめる。届かなければ送るときと同じ例外を投げる。"""
