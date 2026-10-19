"""Minimal outbound e-mail delivery via SMTP."""
from __future__ import annotations

import logging
import smtplib
import ssl
from email.message import EmailMessage

from app.config import Settings

logger = logging.getLogger(__name__)


class MailService:
    """Send plain-text e-mails through the SMTP server configured in ``Settings``.

    Delivery is optional: when no ``SMTP_HOST`` is configured, :meth:`is_configured`
    returns ``False`` and :meth:`send` is a no-op that returns ``False``.
    """

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def is_configured(self) -> bool:
        """Return ``True`` if an SMTP host and sender address are configured."""
        return bool(self.settings.smtp_host and (self.settings.smtp_from or self.settings.smtp_username))

    def send(self, *, to: str, subject: str, body: str) -> bool:
        """Send a plain-text message to *to*.

        Returns ``True`` on success and ``False`` if SMTP is not configured or delivery
        failed. Errors are logged instead of raised so callers never leak delivery
        details to unauthenticated clients.
        """
        if not self.is_configured() or not to:
            return False

        sender = self.settings.smtp_from or self.settings.smtp_username or ""
        message = EmailMessage()
        message["From"] = sender
        message["To"] = to
        message["Subject"] = subject
        message.set_content(body)

        host = str(self.settings.smtp_host)
        port = int(self.settings.smtp_port)
        timeout = float(self.settings.smtp_timeout_seconds)
        try:
            if self.settings.smtp_use_ssl:
                client: smtplib.SMTP = smtplib.SMTP_SSL(
                    host, port, timeout=timeout, context=ssl.create_default_context()
                )
            else:
                client = smtplib.SMTP(host, port, timeout=timeout)
            with client:
                if self.settings.smtp_starttls and not self.settings.smtp_use_ssl:
                    client.starttls(context=ssl.create_default_context())
                if self.settings.smtp_username:
                    client.login(self.settings.smtp_username, self.settings.smtp_password or "")
                client.send_message(message)
            return True
        except (OSError, smtplib.SMTPException) as exc:
            logger.warning("Failed to send e-mail to %s: %s", to, exc.__class__.__name__)
            return False
