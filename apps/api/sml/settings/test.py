"""Test settings: fast hashing, in-memory cache, eager Celery, local storage."""

import tempfile
from pathlib import Path

from .base import *  # noqa: F403

DEBUG = False
SECRET_KEY = "test-secret-key"  # noqa: S105
API_KEY_PEPPER = "test-pepper"
FIELD_ENCRYPTION_KEY = "dGVzdC1vbmx5LWZpZWxkLWVuY3J5cHRpb24ta2V5LTMyYg=="
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
BREACHED_PASSWORD_CHECK = False
CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
SESSION_ENGINE = "django.contrib.sessions.backends.db"
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
LOCAL_MEDIA_ROOT = Path(tempfile.mkdtemp(prefix="sml-test-media-"))
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage",
                "OPTIONS": {"location": str(LOCAL_MEDIA_ROOT)}},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}
S3_ENDPOINT_URL = ""
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
EVENTS_BACKEND = "memory"
REST_FRAMEWORK = {  # noqa: F405
    **REST_FRAMEWORK,  # noqa: F405
    "DEFAULT_THROTTLE_CLASSES": [],
}
ACCOUNT_RATE_LIMITS = False
