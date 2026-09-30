"""Branded, localized account emails (EN/KO/DE) used instead of allauth's plain-text templates.

Every email is one `Copy` rendered into the shared layout (templates/email/layout.{html,txt}).
Text is formatted with `str.format_map` from the allauth context; values are escaped by the
HTML template, so user-controlled values (emails, user agents) can never inject markup.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from zoneinfo import ZoneInfo

from django.conf import settings
from django.template.loader import render_to_string
from django.utils import timezone, translation

SUPPORTED = ("en", "ko", "de")


@dataclass(frozen=True)
class Copy:
    subject: str
    heading: str
    paragraphs: tuple[str, ...]
    cta: str = ""
    cta_url_key: str = ""
    footnote: str = ""
    notice: bool = False  # security notification: adds the IP / browser / time block


COMMON = {
    "en": {
        "preheader_notice": "Security notice for your account",
        "details": "Details",
        "ip": "IP address",
        "browser": "Browser",
        "time": "Time",
        "not_you": "If this wasn't you, reset your password right away and contact {support}.",
        "button_fallback": "If the button doesn't work, copy this link into your browser:",
        "code_label": "Your code",
        "footer": "You are receiving this email because of activity on your Secure Machines Lab account.",
        "team": "Secure Machines Lab",
    },
    "ko": {
        "preheader_notice": "계정 보안 알림",
        "details": "상세 정보",
        "ip": "IP 주소",
        "browser": "브라우저",
        "time": "시간",
        "not_you": "본인이 아니라면 즉시 비밀번호를 재설정하고 {support}(으)로 문의해 주세요.",
        "button_fallback": "버튼이 작동하지 않으면 아래 링크를 브라우저에 붙여 넣으세요:",
        "code_label": "인증 코드",
        "footer": "Secure Machines Lab 계정 활동으로 인해 발송된 메일입니다.",
        "team": "Secure Machines Lab",
    },
    "de": {
        "preheader_notice": "Sicherheitshinweis zu Ihrem Konto",
        "details": "Details",
        "ip": "IP-Adresse",
        "browser": "Browser",
        "time": "Zeitpunkt",
        "not_you": "Wenn Sie das nicht waren, setzen Sie sofort Ihr Passwort zurück und kontaktieren Sie {support}.",
        "button_fallback": "Falls die Schaltfläche nicht funktioniert, kopieren Sie diesen Link in Ihren Browser:",
        "code_label": "Ihr Code",
        "footer": "Sie erhalten diese E-Mail aufgrund einer Aktivität in Ihrem Secure-Machines-Lab-Konto.",
        "team": "Secure Machines Lab",
    },
}


def _confirm(en_intro: str, ko_intro: str, de_intro: str) -> dict[str, Copy]:
    return {
        "en": Copy("Confirm your email address", "Confirm your email", (en_intro,), "Confirm email", "activate_url",
                   "If you didn't request this, you can ignore this email. The link expires in 3 days."),
        "ko": Copy("이메일 주소를 인증해 주세요", "이메일 인증", (ko_intro,), "이메일 인증하기", "activate_url",
                   "요청하지 않으셨다면 이 메일을 무시하셔도 됩니다. 링크는 3일 후 만료됩니다."),
        "de": Copy("Bitte bestätigen Sie Ihre E-Mail-Adresse", "E-Mail-Adresse bestätigen", (de_intro,),
                   "E-Mail bestätigen", "activate_url",
                   "Wenn Sie das nicht angefordert haben, können Sie diese E-Mail ignorieren. "
                   "Der Link ist 3 Tage gültig."),
    }


def _notice(en: tuple[str, str], ko: tuple[str, str], de: tuple[str, str]) -> dict[str, Copy]:
    """(subject, sentence) per language for a security notification."""
    return {lang: Copy(subject, subject, (sentence,), notice=True)
            for lang, (subject, sentence) in {"en": en, "ko": ko, "de": de}.items()}


COPY: dict[str, dict[str, Copy]] = {
    "email_confirmation_signup": _confirm(
        "Welcome to Secure Machines Lab! Confirm {email} to activate your account — your welcome credits are "
        "added as soon as you do.",
        "Secure Machines Lab에 오신 것을 환영합니다! {email} 주소를 인증하면 계정이 활성화되고 가입 축하 크레딧이 "
        "바로 지급됩니다.",
        "Willkommen bei Secure Machines Lab! Bestätigen Sie {email}, um Ihr Konto zu aktivieren – Ihre "
        "Willkommens-Credits werden sofort gutgeschrieben.",
    ),
    "email_confirmation": _confirm(
        "Please confirm that {email} belongs to you.",
        "{email} 주소가 본인 소유인지 확인해 주세요.",
        "Bitte bestätigen Sie, dass {email} Ihnen gehört.",
    ),
    "password_reset_key": {
        "en": Copy("Reset your password", "Reset your password",
                   ("We received a request to reset the password for {email}.",),
                   "Choose a new password", "password_reset_url",
                   "If you didn't ask for this, ignore this email — your password stays the same."),
        "ko": Copy("비밀번호 재설정", "비밀번호 재설정", ("{email} 계정의 비밀번호 재설정 요청을 받았습니다.",),
                   "새 비밀번호 설정", "password_reset_url",
                   "요청하지 않으셨다면 이 메일을 무시하세요. 비밀번호는 변경되지 않습니다."),
        "de": Copy("Passwort zurücksetzen", "Passwort zurücksetzen",
                   ("Wir haben eine Anfrage zum Zurücksetzen des Passworts für {email} erhalten.",),
                   "Neues Passwort wählen", "password_reset_url",
                   "Wenn Sie das nicht angefordert haben, ignorieren Sie diese E-Mail – Ihr Passwort bleibt "
                   "unverändert."),
    },
    "unknown_account": {
        "en": Copy("No account found for this email", "No account with this email",
                   ("Someone — hopefully you — asked to reset the password for {email}, but there is no "
                    "Secure Machines Lab account with this address.",),
                   "Create an account", "signup_url", "If this wasn't you, you can ignore this email."),
        "ko": Copy("해당 이메일로 가입된 계정이 없습니다", "가입된 계정 없음",
                   ("{email} 주소로 비밀번호 재설정이 요청되었지만, "
                    "이 주소로 가입된 Secure Machines Lab 계정이 없습니다.",),
                   "회원가입", "signup_url", "본인이 요청하지 않았다면 이 메일을 무시하셔도 됩니다."),
        "de": Copy("Kein Konto für diese E-Mail-Adresse", "Kein Konto gefunden",
                   ("Jemand – hoffentlich Sie – wollte das Passwort für {email} zurücksetzen, aber es gibt kein "
                    "Secure-Machines-Lab-Konto mit dieser Adresse.",),
                   "Konto erstellen", "signup_url", "Wenn Sie das nicht waren, können Sie diese E-Mail ignorieren."),
    },
    "account_already_exists": {
        "en": Copy("You already have an account", "You already have an account",
                   ("Someone tried to sign up with {email}, but an account with this address already exists. "
                    "If you forgot your password, you can reset it.",),
                   "Reset password", "password_reset_url", "If this wasn't you, you can ignore this email."),
        "ko": Copy("이미 가입된 계정이 있습니다", "이미 가입된 계정",
                   ("{email} 주소로 회원가입이 시도되었지만 이미 가입된 계정이 있습니다. "
                    "비밀번호를 잊으셨다면 재설정할 수 있습니다.",),
                   "비밀번호 재설정", "password_reset_url", "본인이 시도하지 않았다면 이 메일을 무시하셔도 됩니다."),
        "de": Copy("Sie haben bereits ein Konto", "Konto bereits vorhanden",
                   ("Jemand hat versucht, sich mit {email} zu registrieren, aber es gibt bereits ein Konto mit "
                    "dieser Adresse. Falls Sie Ihr Passwort vergessen haben, können Sie es zurücksetzen.",),
                   "Passwort zurücksetzen", "password_reset_url",
                   "Wenn Sie das nicht waren, können Sie diese E-Mail ignorieren."),
    },
    "password_changed": _notice(
        ("Your password was changed", "The password for your account was just changed."),
        ("비밀번호가 변경되었습니다", "계정 비밀번호가 방금 변경되었습니다."),
        ("Ihr Passwort wurde geändert", "Das Passwort Ihres Kontos wurde soeben geändert."),
    ),
    "password_set": _notice(
        ("A password was set", "A password was set for your account."),
        ("비밀번호가 설정되었습니다", "계정에 비밀번호가 설정되었습니다."),
        ("Ein Passwort wurde festgelegt", "Für Ihr Konto wurde ein Passwort festgelegt."),
    ),
    "password_reset": _notice(
        ("Your password was reset", "Your password was reset and all other sessions were signed out."),
        ("비밀번호가 재설정되었습니다", "비밀번호가 재설정되었으며 다른 모든 세션에서 로그아웃되었습니다."),
        ("Ihr Passwort wurde zurückgesetzt",
         "Ihr Passwort wurde zurückgesetzt und alle anderen Sitzungen wurden abgemeldet."),
    ),
    "email_changed": _notice(
        ("Your email address was changed", "Your account email was changed from {from_email} to {to_email}."),
        ("이메일 주소가 변경되었습니다", "계정 이메일이 {from_email}에서 {to_email}(으)로 변경되었습니다."),
        ("Ihre E-Mail-Adresse wurde geändert", "Die E-Mail-Adresse Ihres Kontos wurde von {from_email} zu "
                                               "{to_email} geändert."),
    ),
    "email_deleted": _notice(
        ("An email address was removed", "{deleted_email} was removed from your account."),
        ("이메일 주소가 삭제되었습니다", "{deleted_email} 주소가 계정에서 삭제되었습니다."),
        ("Eine E-Mail-Adresse wurde entfernt", "{deleted_email} wurde aus Ihrem Konto entfernt."),
    ),
    "totp_activated": _notice(
        ("Two-factor authentication is on",
         "An authenticator app was added to your account. You'll be asked for a code when you sign in."),
        ("2단계 인증이 켜졌습니다", "계정에 인증 앱이 등록되었습니다. 로그인할 때 코드를 입력하게 됩니다."),
        ("Zwei-Faktor-Authentifizierung ist aktiv",
         "Ihrem Konto wurde eine Authenticator-App hinzugefügt. Bei der Anmeldung werden Sie nach einem Code gefragt."),
    ),
    "totp_deactivated": _notice(
        ("Authenticator app removed", "The authenticator app was removed from your account."),
        ("인증 앱이 삭제되었습니다", "계정에서 인증 앱이 삭제되었습니다."),
        ("Authenticator-App entfernt", "Die Authenticator-App wurde aus Ihrem Konto entfernt."),
    ),
    "recovery_codes_generated": _notice(
        ("New recovery codes generated",
         "New two-factor recovery codes were generated. Your previous codes no longer work."),
        ("새 복구 코드가 생성되었습니다",
         "새 2단계 인증 복구 코드가 생성되었습니다. 이전 코드는 더 이상 사용할 수 없습니다."),
        ("Neue Wiederherstellungscodes erstellt",
         "Es wurden neue Wiederherstellungscodes erstellt. Ihre bisherigen Codes sind ungültig."),
    ),
    "webauthn_added": _notice(
        ("Passkey added", "A new passkey or security key was added to your account."),
        ("패스키가 추가되었습니다", "계정에 새 패스키 또는 보안 키가 추가되었습니다."),
        ("Passkey hinzugefügt", "Ihrem Konto wurde ein neuer Passkey oder Sicherheitsschlüssel hinzugefügt."),
    ),
    "webauthn_removed": _notice(
        ("Passkey removed", "A passkey or security key was removed from your account."),
        ("패스키가 삭제되었습니다", "계정에서 패스키 또는 보안 키가 삭제되었습니다."),
        ("Passkey entfernt", "Ein Passkey oder Sicherheitsschlüssel wurde aus Ihrem Konto entfernt."),
    ),
}


class _Blank(dict):  # type: ignore[type-arg]
    def __missing__(self, key: str) -> str:
        return ""


def language_for(context: dict[str, Any]) -> str:
    """The recipient's saved language, else the language of the current request."""
    user = context.get("user")
    lang = getattr(user, "locale", None) or (translation.get_language() or "en")[:2]
    return lang if lang in SUPPORTED else "en"


def render(name: str, lang: str, context: dict[str, Any]) -> tuple[str, str, str] | None:
    """Returns (subject, text, html) or None when there is no branded version of this email."""
    variants = COPY.get(name)
    if not variants:
        return None
    copy = variants.get(lang) or variants["en"]
    common = COMMON.get(lang, COMMON["en"])
    support = getattr(settings, "SUPPORT_EMAIL", "support@securemachineslab.com")
    values = _Blank({k: str(v) for k, v in context.items() if isinstance(v, str | int)})
    values["support"] = support
    timestamp = context.get("timestamp")
    with translation.override(lang):
        ctx = {
            "lang": lang,
            "subject": copy.subject,
            "heading": copy.heading,
            "paragraphs": [p.format_map(values) for p in copy.paragraphs],
            "cta": copy.cta,
            "cta_url": str(context.get(copy.cta_url_key, "")) if copy.cta_url_key else "",
            "code": context.get("code") if name.startswith("email_confirmation") else None,
            "footnote": copy.footnote,
            "notice": copy.notice,
            "details": [
                (common["ip"], context.get("ip") or "—"),
                (common["browser"], (context.get("user_agent") or "—")[:200]),
                (common["time"], timezone.localtime(timestamp, ZoneInfo(settings.BUSINESS_TIME_ZONE))
                 .strftime("%Y-%m-%d %H:%M %Z") if timestamp else "—"),
            ] if copy.notice else [],
            "not_you": common["not_you"].format(support=support),
            "support_email": support,
            "site_url": settings.PUBLIC_WEB_URL,
            "common": common,
            "year": timezone.now().year,
        }
        text = render_to_string("email/layout.txt", ctx).strip() + "\n"
        html = render_to_string("email/layout.html", ctx)
    return copy.subject, text, html
