"""Branded account emails: every message in every language, escaping, and the real signup flow."""

from __future__ import annotations

import re
import smtplib

import pytest
from django.core import mail
from django.core.mail.backends.base import BaseEmailBackend
from django.utils import timezone
from rest_framework.test import APIClient

from sml.accounts import emails

CONTEXT = {
    "email": "reader@example.com", "activate_url": "https://app.test/verify-email/KEY",
    "password_reset_url": "https://app.test/reset-password/KEY", "signup_url": "https://app.test/signup",
    "from_email": "old@example.com", "to_email": "new@example.com", "deleted_email": "gone@example.com",
    "ip": "203.0.113.9", "user_agent": "Mozilla/5.0", "timestamp": timezone.now(),
}


@pytest.mark.parametrize("lang", emails.SUPPORTED)
@pytest.mark.parametrize("name", sorted(emails.COPY))
def test_every_email_renders_in_every_language(name, lang):
    subject, text, html = emails.render(name, lang, CONTEXT)
    assert subject and "\n" not in subject
    assert not re.search(r"\{[a-z_]+\}", text + html), "unfilled placeholder"
    assert f'lang="{lang}"' in html
    copy = emails.COPY[name][lang]
    if copy.cta_url_key:
        assert CONTEXT[copy.cta_url_key] in text and CONTEXT[copy.cta_url_key] in html
    if copy.notice:
        assert "203.0.113.9" in text and "203.0.113.9" in html


def test_user_controlled_values_are_escaped_in_html():
    ctx = CONTEXT | {"user_agent": "<script>alert(1)</script>", "deleted_email": "<b>x</b>@example.com"}
    _, text, html = emails.render("email_deleted", "en", ctx)
    assert "<script>" not in html and "&lt;script&gt;" in html
    assert "<b>x</b>" not in html
    assert "<script>alert(1)</script>" in text  # plain text is not HTML


def test_unknown_templates_fall_back_to_allauth():
    assert emails.render("login_code", "en", CONTEXT) is None


@pytest.mark.django_db
@pytest.mark.parametrize(("locale", "subject_word"), [("en", "Confirm"), ("ko", "인증"), ("de", "bestätigen")])
def test_signup_sends_a_branded_confirmation_in_the_chosen_language(platform, locale, subject_word):
    res = APIClient().post("/api/_allauth/browser/v1/auth/signup", {
        "email": f"new-{locale}@example.com", "password": "Correct-Horse-Battery-2026!", "accept_terms": True,
        "locale": locale,
    }, format="json")
    assert res.status_code in (200, 401), res.content  # 401 = signed up, email verification pending
    assert len(mail.outbox) == 1
    msg = mail.outbox[0]
    assert subject_word in msg.subject
    html = dict((mime, body) for body, mime in msg.alternatives)["text/html"]
    assert "/verify-email/" in msg.body and "/verify-email/" in html
    assert 'alt="Secure Machines Lab"' in html and "/brand/email-logo.png" in html
    assert "127.0.0.1" not in msg.body and "example.com!" not in msg.body


@pytest.mark.django_db
def test_password_change_notifies_the_owner(user, client_for):
    from allauth.account.adapter import get_adapter
    from django.test import RequestFactory

    request = RequestFactory().post("/", REMOTE_ADDR="198.51.100.4", HTTP_USER_AGENT="Firefox/140")
    request.user = user
    from allauth.core import context

    with context.request_context(request):
        get_adapter(request).send_notification_mail("account/email/password_changed", user)
    assert len(mail.outbox) == 1
    assert "198.51.100.4" in mail.outbox[0].body
    assert mail.outbox[0].to == [user.email]


class RefusingBackend(BaseEmailBackend):
    """A mail server that turns every message away (e.g. the relay does not accept this server yet)."""

    def send_messages(self, email_messages):  # type: ignore[no-untyped-def]
        raise smtplib.SMTPSenderRefused(550, b"5.7.0 Mail relay denied", "no-reply@example.com")


@pytest.mark.django_db
def test_a_mail_server_that_refuses_the_message_does_not_break_signup(platform, settings, caplog):
    settings.EMAIL_BACKEND = "sml.accounts.tests.test_emails.RefusingBackend"
    res = APIClient().post("/api/_allauth/browser/v1/auth/signup", {
        "email": "refused@example.com", "password": "Correct-Horse-Battery-2026!", "accept_terms": True,
    }, format="json")
    assert res.status_code in (200, 401), res.content  # signed up; the email can be sent again later
    assert "Could not send the email_confirmation_signup email" in caplog.text
