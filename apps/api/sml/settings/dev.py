"""Local development settings."""

from .base import *  # noqa: F403
from .base import env

DEBUG = env.bool("DJANGO_DEBUG", default=True)
SECRET_KEY = SECRET_KEY or "dev-only-insecure-secret-key-change-me"  # noqa: F405
API_KEY_PEPPER = API_KEY_PEPPER or "dev-only-api-key-pepper"  # noqa: F405
FIELD_ENCRYPTION_KEY = FIELD_ENCRYPTION_KEY or "ZGV2LW9ubHktZmllbGQtZW5jcnlwdGlvbi1rZXktMzI="  # noqa: F405

# Plain-HTTP localhost: browsers refuse `__Host-`/Secure cookies without TLS.
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
MFA_WEBAUTHN_ALLOW_INSECURE_ORIGIN = True

REST_FRAMEWORK = {  # noqa: F405
    **REST_FRAMEWORK,  # noqa: F405
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
        "rest_framework.renderers.BrowsableAPIRenderer",
    ],
}
