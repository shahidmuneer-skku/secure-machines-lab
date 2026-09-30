"""Extra signup fields collected by allauth's headless signup endpoint."""

from __future__ import annotations

from django import forms
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from sml.core.captcha import verify_captcha
from sml.core.middleware import client_ip


class SignupForm(forms.Form):
    display_name = forms.CharField(max_length=120, required=False)
    locale = forms.ChoiceField(choices=[("en", "en"), ("ko", "ko"), ("de", "de")], required=False)
    accept_terms = forms.BooleanField(
        required=True, error_messages={"required": _("You must accept the Terms of Service and Privacy Policy.")}
    )
    marketing_opt_in = forms.BooleanField(required=False)
    captcha_token = forms.CharField(required=False)

    def clean_captcha_token(self) -> str:
        token = self.cleaned_data.get("captcha_token") or ""
        request = getattr(self, "request", None)
        if not verify_captcha(token, client_ip(request)):
            raise forms.ValidationError(_("Please complete the CAPTCHA."), code="captcha_failed")
        return token

    def signup(self, request, user) -> None:  # type: ignore[no-untyped-def]
        user.display_name = self.cleaned_data.get("display_name") or ""
        user.locale = self.cleaned_data.get("locale") or "en"
        user.marketing_opt_in = bool(self.cleaned_data.get("marketing_opt_in"))
        user.terms_accepted_at = timezone.now()
        user.save(update_fields=["display_name", "locale", "marketing_opt_in", "terms_accepted_at"])
