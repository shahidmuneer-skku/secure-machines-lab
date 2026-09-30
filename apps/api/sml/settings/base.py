"""Base settings shared by every environment.

Every value that differs between environments or is secret comes from the
environment (see the repository `.env.example`). Production refuses to start
when a required secret is missing (see `prod.py`).
"""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path

import environ

API_DIR = Path(__file__).resolve().parents[2]  # apps/api
REPO_ROOT = API_DIR.parents[1]  # repository root

env = environ.Env()
environ.Env.read_env(REPO_ROOT / ".env", overwrite=False)

DJANGO_ENV = env("DJANGO_ENV", default="dev")
DEBUG = env.bool("DJANGO_DEBUG", default=False)
SECRET_KEY = env("DJANGO_SECRET_KEY", default="")
ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS", default=["localhost", "127.0.0.1"])

# Public URL of the web app (used for links in emails and payment redirects).
PUBLIC_WEB_URL = env("PUBLIC_WEB_URL", default="http://localhost:3000").rstrip("/")
CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS", default=[PUBLIC_WEB_URL])

INSTALLED_APPS = [
    "sml.core.admin_apps.SecureAdminConfig",  # Django admin without its password-only login
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",
    # third party
    "rest_framework",
    "django_filters",
    "drf_spectacular",
    "allauth",
    "allauth.account",
    "allauth.mfa",
    "allauth.usersessions",
    "allauth.headless",
    # platform
    "sml.core",
    "sml.accounts",
    "sml.apikeys",
    "sml.credits",
    "sml.billing",
    "sml.catalog",
    "sml.media",
    "sml.jobs",
    "sml.reports",
    "sml.news",
    "sml.trial",
    "sml.dashboard",
    "sml.adminapi",
]

MIDDLEWARE = [
    # Order matters. Each entry states why it sits where it does.
    "sml.core.middleware.RequestIdMiddleware",           # first: every log line/response gets an id
    "sml.core.middleware.AccessLogMiddleware",           # wraps everything below to time the request
    "django.middleware.security.SecurityMiddleware",      # HSTS, SSL redirect, nosniff, referrer policy
    "whitenoise.middleware.WhiteNoiseMiddleware",         # static files (admin/docs) before any DB work
    "sml.core.middleware.SecurityHeadersMiddleware",      # CSP/Permissions-Policy/CORP/no-store for the API
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",          # Accept-Language fallback
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",          # double-submit token + Origin check
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "sml.accounts.middleware.SessionTimeoutMiddleware",   # idle/absolute timeouts (needs request.user)
    "sml.accounts.middleware.UserLocaleMiddleware",       # user's language beats Accept-Language
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "allauth.account.middleware.AccountMiddleware",       # required by django-allauth
    "allauth.usersessions.middleware.UserSessionsMiddleware",  # tracks IP/UA per session (revocable)
    "sml.core.middleware.MaintenanceModeMiddleware",      # blocks writes during maintenance
    "sml.apikeys.middleware.ApiKeyUsageMiddleware",       # per-key request log + daily counters
]

ROOT_URLCONF = "sml.urls"
WSGI_APPLICATION = "sml.wsgi.application"
ASGI_APPLICATION = "sml.asgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [API_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

# --- Database / cache -------------------------------------------------------
DATABASES = {
    "default": env.db("DATABASE_URL", default="postgres://sml:sml@127.0.0.1:5432/sml"),
}
DATABASES["default"]["ATOMIC_REQUESTS"] = False
DATABASES["default"]["CONN_MAX_AGE"] = env.int("DB_CONN_MAX_AGE", default=60)
DATABASES["default"]["CONN_HEALTH_CHECKS"] = True
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

REDIS_URL = env("REDIS_URL", default="redis://127.0.0.1:6379/0")
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": REDIS_URL,
        "KEY_PREFIX": "sml",
    }
}

# --- Auth -------------------------------------------------------------------
AUTH_USER_MODEL = "accounts.User"
AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
]
PASSWORD_HASHERS = [
    "sml.accounts.hashers.StrongArgon2PasswordHasher",
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
    # Legacy MongoDB users (bcrypt) are rehashed to Argon2id on first login.
    "django.contrib.auth.hashers.BCryptSHA256PasswordHasher",
]
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 12}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "sml.accounts.validators.BreachedPasswordValidator"},
]
BREACHED_PASSWORD_CHECK = env.bool("BREACHED_PASSWORD_CHECK", default=True)

# Server-side sessions (PostgreSQL + Redis cache). The cookie is opaque, HttpOnly
# and never readable from JavaScript. Timeouts are enforced by
# sml.accounts.middleware.SessionTimeoutMiddleware.
SESSION_ENGINE = "django.contrib.sessions.backends.cached_db"
SESSION_COOKIE_NAME = env("SESSION_COOKIE_NAME", default="sml_session")
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_AGE = int(timedelta(days=30).total_seconds())
SESSION_IDLE_TIMEOUT = int(timedelta(minutes=env.int("SESSION_IDLE_MINUTES", default=30)).total_seconds())
SESSION_ABSOLUTE_TIMEOUT = int(timedelta(hours=env.int("SESSION_ABSOLUTE_HOURS", default=12)).total_seconds())
SESSION_REMEMBER_TIMEOUT = int(timedelta(days=env.int("SESSION_REMEMBER_DAYS", default=30)).total_seconds())

CSRF_COOKIE_NAME = env("CSRF_COOKIE_NAME", default="sml_csrftoken")
CSRF_COOKIE_HTTPONLY = False  # double-submit: the SPA echoes it in X-CSRFToken
CSRF_COOKIE_SAMESITE = "Lax"
CSRF_HEADER_NAME = "HTTP_X_CSRFTOKEN"

# --- django-allauth (headless) ----------------------------------------------
HEADLESS_ONLY = True
HEADLESS_CLIENTS = ("browser",)
HEADLESS_SERVE_SPECIFICATION = True
HEADLESS_FRONTEND_URLS = {
    "account_confirm_email": f"{PUBLIC_WEB_URL}/verify-email/{{key}}",
    "account_reset_password": f"{PUBLIC_WEB_URL}/reset-password",
    "account_reset_password_from_key": f"{PUBLIC_WEB_URL}/reset-password/{{key}}",
    "account_signup": f"{PUBLIC_WEB_URL}/signup",
}
ACCOUNT_ADAPTER = "sml.accounts.adapters.AccountAdapter"
ACCOUNT_USER_MODEL_USERNAME_FIELD = None
ACCOUNT_LOGIN_METHODS = {"email"}
ACCOUNT_SIGNUP_FIELDS = ["email*", "password1*"]
ACCOUNT_SIGNUP_FORM_CLASS = "sml.accounts.forms.SignupForm"
ACCOUNT_EMAIL_VERIFICATION = "mandatory"
ACCOUNT_EMAIL_VERIFICATION_BY_CODE_ENABLED = False
ACCOUNT_UNIQUE_EMAIL = True
ACCOUNT_PREVENT_ENUMERATION = True
ACCOUNT_SESSION_REMEMBER = None  # user chooses "remember me"
ACCOUNT_LOGIN_ON_EMAIL_CONFIRMATION = False
ACCOUNT_LOGOUT_ON_PASSWORD_CHANGE = False
ACCOUNT_PASSWORD_RESET_TOKEN_GENERATOR = "allauth.account.forms.EmailAwarePasswordResetTokenGenerator"  # noqa: S105
ACCOUNT_REAUTHENTICATION_TIMEOUT = 300
ACCOUNT_EMAIL_SUBJECT_PREFIX = "[Secure Machines Lab] "
# Security notifications (password/email changed, 2FA and passkey changes) go to the account owner.
ACCOUNT_EMAIL_NOTIFICATIONS = True
ACCOUNT_RATE_LIMITS = {
    "login": "30/m/ip",
    "login_failed": "10/m/ip,5/5m/key",
    "signup": "20/h/ip",
    "confirm_email": "1/3m/key",
    "reset_password": "20/m/ip,5/m/key",
    "reset_password_from_key": "20/m/ip",
    "change_password": "5/m/user",
    "reauthenticate": "10/m/user",
}
USERSESSIONS_TRACK_ACTIVITY = True

MFA_SUPPORTED_TYPES = ["totp", "recovery_codes", "webauthn"]
MFA_PASSKEY_LOGIN_ENABLED = True
MFA_TOTP_ISSUER = "Secure Machines Lab"
MFA_RECOVERY_CODE_COUNT = 10
MFA_WEBAUTHN_ALLOW_INSECURE_ORIGIN = env.bool("MFA_WEBAUTHN_ALLOW_INSECURE_ORIGIN", default=False)

# --- Email --------------------------------------------------------------------
EMAIL_BACKEND = env("EMAIL_BACKEND", default="django.core.mail.backends.console.EmailBackend")
EMAIL_HOST = env("EMAIL_HOST", default="")
EMAIL_PORT = env.int("EMAIL_PORT", default=587)
EMAIL_HOST_USER = env("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", default="")
EMAIL_USE_TLS = env.bool("EMAIL_USE_TLS", default=True)
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="Secure Machines Lab <no-reply@securemachineslab.com>")
SUPPORT_EMAIL = env("SUPPORT_EMAIL", default="support@securemachineslab.com")

# --- i18n -----------------------------------------------------------------------
LANGUAGE_CODE = "en"
LANGUAGES = [("en", "English"), ("ko", "한국어"), ("de", "Deutsch")]
LOCALE_PATHS = [API_DIR / "locale"]
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True
# Business day boundary for daily credits (owner is in Korea).
BUSINESS_TIME_ZONE = env("BUSINESS_TIME_ZONE", default="Asia/Seoul")

# --- Static / media storage -----------------------------------------------------
STATIC_URL = "/api/static/"
STATIC_ROOT = API_DIR / "staticfiles"

S3_ENDPOINT_URL = env("S3_ENDPOINT_URL", default="")
S3_PUBLIC_ENDPOINT_URL = env("S3_PUBLIC_ENDPOINT_URL", default=S3_ENDPOINT_URL)
S3_BUCKET = env("S3_BUCKET", default="sml-media")
S3_ACCESS_KEY = env("S3_ACCESS_KEY", default="")
S3_SECRET_KEY = env("S3_SECRET_KEY", default="")
S3_REGION = env("S3_REGION", default="us-east-1")
LOCAL_MEDIA_ROOT = Path(env("LOCAL_MEDIA_ROOT", default=str(REPO_ROOT / "var" / "media")))

if S3_ENDPOINT_URL:
    _media_storage = {
        "BACKEND": "storages.backends.s3.S3Storage",
        "OPTIONS": {
            "bucket_name": S3_BUCKET,
            "endpoint_url": S3_ENDPOINT_URL,
            "access_key": S3_ACCESS_KEY,
            "secret_key": S3_SECRET_KEY,
            "region_name": S3_REGION,
            "default_acl": None,
            "querystring_auth": True,
            "querystring_expire": 300,
            "file_overwrite": False,
            "signature_version": "s3v4",
            "addressing_style": "path",
        },
    }
else:
    _media_storage = {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
        "OPTIONS": {"location": str(LOCAL_MEDIA_ROOT)},
    }

STORAGES = {
    "default": _media_storage,
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}

# Upload limits (bytes / seconds / pixels). Also enforced by the reverse proxy.
UPLOAD_MAX_IMAGE_BYTES = env.int("UPLOAD_MAX_IMAGE_BYTES", default=50 * 1024 * 1024)
UPLOAD_MAX_VIDEO_BYTES = env.int("UPLOAD_MAX_VIDEO_BYTES", default=4 * 1024 * 1024 * 1024)
UPLOAD_MAX_IMAGE_PIXELS = env.int("UPLOAD_MAX_IMAGE_PIXELS", default=80_000_000)
UPLOAD_MAX_VIDEO_SECONDS = env.int("UPLOAD_MAX_VIDEO_SECONDS", default=3 * 60 * 60)
UPLOAD_MAX_FILES_PER_BATCH = env.int("UPLOAD_MAX_FILES_PER_BATCH", default=50)
DATA_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024
FILE_UPLOAD_TEMP_DIR = env("FILE_UPLOAD_TEMP_DIR", default=None)

# --- REST framework / OpenAPI --------------------------------------------------
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "sml.apikeys.authentication.ApiKeyAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ],
    # Secure by default: every endpoint requires an authenticated principal
    # unless the view explicitly opts out.
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "DEFAULT_PARSER_CLASSES": [
        "rest_framework.parsers.JSONParser",
        "rest_framework.parsers.MultiPartParser",
        "rest_framework.parsers.FormParser",
    ],
    "DEFAULT_FILTER_BACKENDS": ["django_filters.rest_framework.DjangoFilterBackend"],
    "DEFAULT_PAGINATION_CLASS": "sml.core.pagination.DefaultCursorPagination",
    "PAGE_SIZE": 25,
    "EXCEPTION_HANDLER": "sml.core.exceptions.problem_exception_handler",
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_THROTTLE_CLASSES": [
        "sml.core.throttling.PrincipalRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "principal": env("THROTTLE_PRINCIPAL", default="240/min"),
        "anon": env("THROTTLE_ANON", default="60/min"),
        "trial": env("THROTTLE_TRIAL", default="10/min"),
        "job_create": env("THROTTLE_JOB_CREATE", default="60/min"),
    },
    "TEST_REQUEST_DEFAULT_FORMAT": "json",
}

SPECTACULAR_SETTINGS = {
    "TITLE": "Secure Machines Lab API",
    "DESCRIPTION": (
        "Deepfake & AI-generated media detection platform. Authenticate with a browser session "
        "(web app) or an API key sent as `Authorization: Bearer sml_live_...`."
    ),
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "SCHEMA_PATH_PREFIX": r"/api/v1",
    "COMPONENT_SPLIT_REQUEST": True,
    "POSTPROCESSING_HOOKS": [
        "drf_spectacular.hooks.postprocess_schema_enums",
        "sml.api_schema_hooks.require_response_fields",
    ],
    "ENUM_NAME_OVERRIDES": {
        "JobStatusEnum": "sml.jobs.models.Job.Status",
        "JobKindEnum": "sml.jobs.models.Job.Kind",
        "JobSourceEnum": "sml.jobs.models.Job.Source",
        "VerdictEnum": "sml.jobs.models.Job.Verdict",
        "TaskStatusEnum": "sml.jobs.models.JobTask.Status",
        "TaskKindEnum": "sml.jobs.models.JobTask.Kind",
        "ExplanationStatusEnum": "sml.jobs.models.Explanation.Status",
        "ArtifactKindEnum": "sml.jobs.models.Artifact.Kind",
        "PaymentStatusEnum": "sml.billing.models.Payment.Status",
        "PaymentKindEnum": "sml.billing.models.Payment.Kind",
        "SubscriptionStatusEnum": "sml.billing.models.Subscription.Status",
        "ProviderEnum": "sml.billing.models.Provider",
        "LocaleEnum": "sml.accounts.models.User.Locale",
        "ModuleEnum": "sml.accounts.models.AccessPolicy.MODULES",
        "CurrencyEnum": "sml.billing.models.Currency",
        "ReportStatusEnum": "sml.reports.models.Report.Status",
        "ReportFormatEnum": "sml.reports.models.Report.Format",
        "LedgerKindEnum": "sml.credits.models.LedgerKind",
        "MediaStatusEnum": "sml.media.models.MediaObject.Status",
        "MediaTypeEnum": [("image", "Image"), ("video", "Video")],
    },
    "APPEND_COMPONENTS": {
        "securitySchemes": {
            "ApiKeyAuth": {"type": "http", "scheme": "bearer", "bearerFormat": "sml_live_<id>_<secret>"},
            "SessionAuth": {"type": "apiKey", "in": "cookie", "name": SESSION_COOKIE_NAME},
        }
    },
    "SECURITY": [{"ApiKeyAuth": []}, {"SessionAuth": []}],
    "TAGS": [
        {"name": "account", "description": "Current user, profile and preferences"},
        {"name": "api-keys", "description": "Create and manage personal API keys"},
        {"name": "catalog", "description": "Detection models and modules available to the caller"},
        {"name": "uploads", "description": "Media uploads"},
        {"name": "jobs", "description": "Detection jobs, progress and results"},
        {"name": "credits", "description": "Credit balance and ledger"},
        {"name": "billing", "description": "Credit packs, subscriptions and payments"},
        {"name": "reports", "description": "PDF / HWP / CSV reports"},
        {"name": "news", "description": "Multimedia news verification"},
        {"name": "trial", "description": "Anonymous free trial"},
        {"name": "admin", "description": "Administration (internal)"},
    ],
}

# --- Celery / RabbitMQ ---------------------------------------------------------
CELERY_BROKER_URL = env("CELERY_BROKER_URL", default="amqp://sml:sml@127.0.0.1:5672/sml")
CELERY_RESULT_BACKEND = None
CELERY_TASK_ACKS_LATE = True
CELERY_TASK_REJECT_ON_WORKER_LOST = True
CELERY_WORKER_PREFETCH_MULTIPLIER = 1
CELERY_TASK_SERIALIZER = "json"
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_DEFAULT_QUEUE = "sml.default"
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True
# Beat keeps runtime state; it lives with the other runtime files in var/ (git-ignored).
CELERY_BEAT_SCHEDULE_FILENAME = str(REPO_ROOT / "var" / "celerybeat-schedule")
CELERY_TASK_ALWAYS_EAGER = env.bool("CELERY_TASK_ALWAYS_EAGER", default=False)
CELERY_TIMEZONE = "UTC"

# Monitoring endpoints used by the admin queue dashboard.
RABBITMQ_MANAGEMENT_URL = env("RABBITMQ_MANAGEMENT_URL", default="http://127.0.0.1:15672")
RABBITMQ_MANAGEMENT_USER = env("RABBITMQ_MANAGEMENT_USER", default="sml")
RABBITMQ_MANAGEMENT_PASSWORD = env("RABBITMQ_MANAGEMENT_PASSWORD", default="sml")
RABBITMQ_VHOST = env("RABBITMQ_VHOST", default="sml")

# --- Model registry / workers --------------------------------------------------
MODELS_CONFIG_PATH = Path(env("MODELS_CONFIG_PATH", default=str(REPO_ROOT / "config" / "models.yaml")))
ROLES_CONFIG_PATH = Path(env("ROLES_CONFIG_PATH", default=str(REPO_ROOT / "config" / "roles.yaml")))

# --- Secrets for derived material --------------------------------------------
API_KEY_PEPPER = env("API_KEY_PEPPER", default="")
API_KEY_ENV_LABEL = env("API_KEY_ENV_LABEL", default="test")  # "live" in production
FIELD_ENCRYPTION_KEY = env("FIELD_ENCRYPTION_KEY", default="")
TRIAL_COOKIE_NAME = env("TRIAL_COOKIE_NAME", default="sml_trial")

# --- CAPTCHA (Cloudflare Turnstile; optional) -----------------------------------
TURNSTILE_SITE_KEY = env("TURNSTILE_SITE_KEY", default="")
TURNSTILE_SECRET_KEY = env("TURNSTILE_SECRET_KEY", default="")

# --- Billing ------------------------------------------------------------------
BILLING_ENABLED = env.bool("BILLING_ENABLED", default=True)
BILLING_PROVIDERS = env.list("BILLING_PROVIDERS", default=["toss", "stripe"])
STRIPE_SECRET_KEY = env("STRIPE_SECRET_KEY", default="")
STRIPE_PUBLISHABLE_KEY = env("STRIPE_PUBLISHABLE_KEY", default="")
STRIPE_WEBHOOK_SECRET = env("STRIPE_WEBHOOK_SECRET", default="")
TOSS_CLIENT_KEY = env("TOSS_CLIENT_KEY", default="")
TOSS_SECRET_KEY = env("TOSS_SECRET_KEY", default="")
TOSS_API_BASE = env("TOSS_API_BASE", default="https://api.tosspayments.com")

# --- Reasoning / news engines -------------------------------------------------
OLLAMA_BASE_URL = env("OLLAMA_BASE_URL", default="http://127.0.0.1:11434")
ANTHROPIC_API_KEY = env("ANTHROPIC_API_KEY", default="")

# --- Logging ------------------------------------------------------------------
LOG_LEVEL = env("LOG_LEVEL", default="INFO")
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {"request_id": {"()": "sml.core.logging.RequestIdFilter"}},
    "formatters": {
        "json": {"()": "sml.core.logging.JsonFormatter"},
        "plain": {"format": "%(asctime)s %(levelname)s %(name)s [%(request_id)s] %(message)s"},
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": env("LOG_FORMAT", default="plain"),
            "filters": ["request_id"],
        },
    },
    "root": {"handlers": ["console"], "level": LOG_LEVEL},
    "loggers": {
        "sml.access": {"level": "INFO"},
        "django.db.backends": {"level": "WARNING"},
        "celery": {"level": "INFO"},
    },
}

# --- Security headers (tightened further in prod.py) -------------------------
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"
SECURE_CROSS_ORIGIN_OPENER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"
