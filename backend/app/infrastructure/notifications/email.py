import logging
from dataclasses import dataclass
from typing import Protocol

logger = logging.getLogger("app.notifications")


@dataclass(frozen=True, slots=True)
class EmailMessage:
    to: str
    subject: str
    body: str


class EmailSender(Protocol):
    def send(self, message: EmailMessage) -> None: ...


class ConsoleEmailSender:
    """Development backend: the "email" is written to the log instead of being sent."""

    def send(self, message: EmailMessage) -> None:
        logger.info("Email to=%s subject=%r\n%s", message.to, message.subject, message.body)
