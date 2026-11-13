from abc import ABC, abstractmethod

from bounded_contexts.email_sender.domain.email_message import EmailMessage


class EmailSendingDisabledError(Exception):
    """Raised when sending email is disabled (``MAIL_ENABLED`` not set)."""


class IEmailSender(ABC):
    @abstractmethod
    def send(self, message: EmailMessage) -> None: ...

    @abstractmethod
    def check_reachable(self) -> None:
        """Check only that the destination server is reachable, without sending.

        Raises the same exception as send when it is not.
        """
