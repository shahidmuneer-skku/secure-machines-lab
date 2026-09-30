"""Users, capabilities (permissions), per-user access policies and consents."""

from __future__ import annotations

from typing import Any

from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.utils import timezone
from django.utils.functional import cached_property

from sml.core.ids import uuid7

# Capabilities are the atomic permissions that roles (Django groups) bundle.
# Keep in sync with config/roles.yaml; `manage.py seed_rbac` applies it.
CAPABILITIES: list[tuple[str, str]] = [
    # user-level
    ("run_detection", "Run image/video detections"),
    ("run_long_video", "Run long-form video scans"),
    ("run_news_verification", "Run multimedia news verification"),
    ("use_reasoning", "Request AI reasoning (Explain why)"),
    ("manage_own_api_keys", "Create and manage own API keys"),
    ("purchase_credits", "Buy credit packs and subscriptions"),
    # staff
    ("view_users", "View users"),
    ("manage_users", "Create, edit, disable users"),
    ("manage_user_access", "Edit per-user model/module/audit permissions"),
    ("manage_roles", "Edit role definitions and assign staff roles"),
    ("view_all_jobs", "View all users' jobs"),
    ("view_all_media", "View other users' uploaded media"),
    ("manage_all_jobs", "Cancel, re-run or delete any job"),
    ("view_billing", "View payments, subscriptions and revenue"),
    ("manage_billing", "Manage packs, plans, payments and refunds"),
    ("refund_limited", "Issue refunds up to the support limit"),
    ("grant_credits", "Grant or deduct credits manually"),
    ("manage_pricing", "Edit credit prices"),
    ("manage_models", "Enable/disable models, edit model settings"),
    ("view_queues", "View queue and worker health"),
    ("manage_queues", "Requeue dead letters, drain workers"),
    ("view_system", "View GPU and system status"),
    ("view_audit_log", "View the audit log"),
    ("manage_settings", "Edit platform settings and feature flags"),
    ("view_api_usage", "View API usage across all keys"),
]
CAPABILITY_CODENAMES = [c for c, _ in CAPABILITIES]


class Capability(models.Model):
    """Holder for custom permissions. Never has rows; only its Meta.permissions matter."""

    class Meta:
        managed = False
        default_permissions = ()
        permissions = CAPABILITIES

    def __str__(self) -> str:
        return "Capability placeholder"


class UserManager(BaseUserManager["User"]):
    use_in_migrations = True

    def _create(self, email: str, password: str | None, **extra: Any) -> User:
        if not email:
            raise ValueError("Email is required")
        user = self.model(email=self.normalize_email(email).lower(), **extra)
        user.set_password(password) if password else user.set_unusable_password()
        user.save(using=self._db)
        return user

    def create_user(self, email: str, password: str | None = None, **extra: Any) -> User:
        extra.setdefault("is_staff", False)
        extra.setdefault("is_superuser", False)
        return self._create(email, password, **extra)

    def create_superuser(self, email: str, password: str | None = None, **extra: Any) -> User:
        extra.update(is_staff=True, is_superuser=True)
        return self._create(email, password, **extra)


class User(AbstractBaseUser, PermissionsMixin):
    class Locale(models.TextChoices):
        EN = "en", "English"
        KO = "ko", "한국어"
        DE = "de", "Deutsch"

    id = models.UUIDField(primary_key=True, default=uuid7, editable=False)
    email = models.EmailField(unique=True)
    display_name = models.CharField(max_length=120, blank=True, default="")
    locale = models.CharField(max_length=5, choices=Locale.choices, default=Locale.EN)
    time_zone = models.CharField(max_length=64, default="Asia/Seoul")
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False, help_text="Can log into the Django admin site.")
    date_joined = models.DateTimeField(default=timezone.now)
    terms_accepted_at = models.DateTimeField(null=True, blank=True)
    marketing_opt_in = models.BooleanField(default=False)
    disabled_reason = models.CharField(max_length=255, blank=True, default="")
    deletion_requested_at = models.DateTimeField(null=True, blank=True)

    objects = UserManager()

    USERNAME_FIELD = "email"
    EMAIL_FIELD = "email"
    REQUIRED_FIELDS: list[str] = []

    class Meta:
        ordering = ["-date_joined"]

    def __str__(self) -> str:
        return self.email

    @cached_property
    def role_names(self) -> list[str]:
        return sorted(self.groups.values_list("name", flat=True))

    @cached_property
    def requires_mfa(self) -> bool:
        return RoleProfile.objects.filter(group__user=self, mfa_required=True).exists()

    @property
    def has_mfa(self) -> bool:
        from allauth.mfa.models import Authenticator

        return Authenticator.objects.filter(
            user=self, type__in=[Authenticator.Type.TOTP, Authenticator.Type.WEBAUTHN]
        ).exists()


class RoleProfile(models.Model):
    """Extra metadata for a role (Django group)."""

    group = models.OneToOneField("auth.Group", on_delete=models.CASCADE, related_name="role_profile")
    description = models.CharField(max_length=255, blank=True, default="")
    mfa_required = models.BooleanField(default=False)
    is_staff_role = models.BooleanField(default=False)
    is_default = models.BooleanField(default=False, help_text="Assigned to every new signup.")
    is_system = models.BooleanField(default=True, help_text="Seeded from roles.yaml; cannot be deleted.")

    def __str__(self) -> str:
        return self.group.name


class AccessPolicy(models.Model):
    """Attribute-based restrictions layered on top of role capabilities.

    `None` means unrestricted; a list restricts to those ids. Effective access is
    the intersection of role capabilities and this policy.
    """

    MODULES = ["detect", "long_video", "news"]
    AUDIT_STEPS = ["face", "safety", "fas", "metadata"]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="access_policy")
    allowed_modules = models.JSONField(null=True, blank=True)
    allowed_models = models.JSONField(null=True, blank=True)
    allowed_audit_steps = models.JSONField(null=True, blank=True)
    max_inflight_tasks = models.PositiveIntegerField(null=True, blank=True)
    retention_days_override = models.PositiveIntegerField(null=True, blank=True)
    unlimited_credits = models.BooleanField(
        default=False, help_text="Enterprise / invoice-later accounts: detections are not charged."
    )
    notes = models.TextField(blank=True, default="")
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"Access policy for {self.user}"

    def allows_module(self, module: str) -> bool:
        return self.allowed_modules is None or module in self.allowed_modules

    def allows_model(self, model_id: str) -> bool:
        return self.allowed_models is None or model_id in self.allowed_models

    def allows_audit_step(self, step: str) -> bool:
        return self.allowed_audit_steps is None or step in self.allowed_audit_steps


class TrainingConsent(models.Model):
    """Opt-in consent to use the user's uploads for model improvement (PIPA art. 15/22)."""

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="training_consent")
    granted = models.BooleanField(default=False)
    granted_at = models.DateTimeField(null=True, blank=True)
    withdrawn_at = models.DateTimeField(null=True, blank=True)
    policy_version = models.CharField(max_length=32, default="2026-10-01")

    def __str__(self) -> str:
        return f"Training consent for {self.user}: {'granted' if self.granted else 'not granted'}"

    def set(self, granted: bool) -> None:
        now = timezone.now()
        self.granted = granted
        if granted:
            self.granted_at = now
            self.withdrawn_at = None
        else:
            self.withdrawn_at = now
        self.save()
