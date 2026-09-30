"""Production settings. Refuses to boot without the required secrets."""

from django.core.exceptions import ImproperlyConfigured

from .base import *  # noqa: F403
from .base import env

DEBUG = False

_REQUIRED = {
    "DJANGO_SECRET_KEY": SECRET_KEY,  # noqa: F405
    "API_KEY_PEPPER": API_KEY_PEPPER,  # noqa: F405
    "FIELD_ENCRYPTION_KEY": FIELD_ENCRYPTION_KEY,  # noqa: F405
    "DATABASE_URL": env("DATABASE_URL", default=""),
    "CELERY_BROKER_URL": env("CELERY_BROKER_URL", default=""),
    "REDIS_URL": env("REDIS_URL", default=""),
}
_missing = [name for name, value in _REQUIRED.items() if not value]
if _missing:
    raise ImproperlyConfigured(f"Missing required production settings: {', '.join(_missing)}")
if len(SECRET_KEY) < 50:  # noqa: F405
    raise ImproperlyConfigured("DJANGO_SECRET_KEY must be at least 50 characters in production")

API_KEY_ENV_LABEL = "live"

# TLS terminates at nginx; trust its forwarded scheme.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = env.bool("SECURE_SSL_REDIRECT", default=True)
SECURE_HSTS_SECONDS = 63072000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

# __Host- cookies: Secure, Path=/, no Domain attribute (cannot be set by subdomains).
SESSION_COOKIE_NAME = "__Host-sml_session"
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_NAME = "__Host-sml_csrftoken"
CSRF_COOKIE_SECURE = True
MFA_WEBAUTHN_ALLOW_INSECURE_ORIGIN = False

LOG_FORMAT = "json"
LOGGING["handlers"]["console"]["formatter"] = "json"  # noqa: F405
