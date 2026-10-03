from __future__ import annotations

import logging
import smtplib
from typing import Any

from allauth.account.adapter import DefaultAccountAdapter
from django.core.mail import EmailMessage, EmailMultiAlternatives
from django.http import HttpRequest

from sml.core.models import PlatformSettings

from . import emails

logger = logging.getLogger(__name__)


class AccountAdapter(DefaultAccountAdapter):
    def is_open_for_signup(self, request: HttpRequest) -> bool:
        return PlatformSettings.load().signups_enabled

    def get_login_redirect_url(self, request: HttpRequest) -> str:
        return "/app"

    def send_mail(self, template_prefix: str, email: str, context: dict[str, Any]) -> None:
        """A mail server that is down or refuses a message must not turn sign-up or sign-in into an
        error (the account already exists by then): the failure is logged, and the user can ask for the
        email again ("Resend email")."""
        try:
            super().send_mail(template_prefix, email, context)
        except (smtplib.SMTPException, OSError):
            logger.exception("Could not send the %s email", template_prefix.rsplit("/", 1)[-1])

    def render_mail(self, template_prefix: str, email: str | list[str], context: dict[str, Any],
                    headers: dict[str, str] | None = None) -> EmailMessage:
        """Branded EN/KO/DE emails in the recipient's language; allauth's templates for anything else."""
        name = template_prefix.rsplit("/", 1)[-1]
        rendered = emails.render(name, emails.language_for(context), context)
        if rendered is None:
            return super().render_mail(template_prefix, email, context, headers)
        subject, text, html = rendered
        to = [email] if isinstance(email, str) else email
        msg = EmailMultiAlternatives(self.format_email_subject(subject), text, self.get_from_email(), to,
                                     headers=headers)
        msg.attach_alternative(html, "text/html")
        return msg
