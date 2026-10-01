from __future__ import annotations

from django.contrib.auth.models import Group
from rest_framework import serializers

from sml.accounts.models import CAPABILITY_CODENAMES, AccessPolicy, User
from sml.billing.models import CreditPack, Payment, Plan, WebhookEvent
from sml.catalog.registry import registry
from sml.core.models import AuditLog, PlatformSettings
from sml.credits.models import PriceRule


class AdminUserSerializer(serializers.ModelSerializer):
    roles = serializers.SerializerMethodField()
    balance = serializers.IntegerField(source="wallet.balance_cache", read_only=True, default=0)
    has_mfa = serializers.BooleanField(read_only=True)
    email_verified = serializers.SerializerMethodField()
    jobs_count = serializers.IntegerField(read_only=True, default=None)

    class Meta:
        model = User
        fields = ["id", "email", "display_name", "locale", "is_active", "disabled_reason", "date_joined",
                  "last_login", "roles", "balance", "has_mfa", "email_verified", "jobs_count", "marketing_opt_in"]
        read_only_fields = ["id", "email", "date_joined", "last_login"]

    def get_roles(self, obj: User) -> list[str]:
        return [g.name for g in obj.groups.all()]

    def get_email_verified(self, obj: User) -> bool:
        return obj.emailaddress_set.filter(verified=True).exists()


class AccessPolicySerializer(serializers.ModelSerializer):
    allowed_modules = serializers.ListField(child=serializers.ChoiceField(choices=AccessPolicy.MODULES),
                                            allow_null=True, required=False)
    allowed_models = serializers.ListField(child=serializers.CharField(), allow_null=True, required=False)
    allowed_audit_steps = serializers.ListField(child=serializers.ChoiceField(choices=AccessPolicy.AUDIT_STEPS),
                                                allow_null=True, required=False)

    class Meta:
        model = AccessPolicy
        fields = ["allowed_modules", "allowed_models", "allowed_audit_steps", "max_inflight_tasks",
                  "retention_days_override", "unlimited_credits", "notes", "updated_at"]
        read_only_fields = ["updated_at"]

    def validate_allowed_models(self, value):  # type: ignore[no-untyped-def]
        if value is None:
            return None
        reg = registry()
        unknown = [m for m in value if reg.get(m) is None and m not in reg.long_video_models]
        if unknown:
            raise serializers.ValidationError(f"Unknown models: {', '.join(unknown)}")
        return sorted(set(value))


class RoleSerializer(serializers.ModelSerializer):
    capabilities = serializers.SerializerMethodField()
    description = serializers.CharField(source="role_profile.description", read_only=True, default="")
    mfa_required = serializers.BooleanField(source="role_profile.mfa_required", read_only=True, default=False)
    is_staff_role = serializers.BooleanField(source="role_profile.is_staff_role", read_only=True, default=False)
    is_default = serializers.BooleanField(source="role_profile.is_default", read_only=True, default=False)
    members = serializers.IntegerField(read_only=True, default=0)

    class Meta:
        model = Group
        fields = ["id", "name", "description", "mfa_required", "is_staff_role", "is_default", "capabilities",
                  "members"]

    def get_capabilities(self, obj: Group) -> list[str]:
        return sorted(p.codename for p in obj.permissions.all() if p.codename in CAPABILITY_CODENAMES)


class CreditAdjustSerializer(serializers.Serializer):
    delta = serializers.IntegerField(help_text="Positive to grant, negative to deduct.")
    reason = serializers.CharField(max_length=255)
    expires_in_days = serializers.IntegerField(min_value=1, required=False, allow_null=True)

    def validate_delta(self, value: int) -> int:
        if value == 0 or abs(value) > 1_000_000:
            raise serializers.ValidationError("delta must be non-zero and at most 1,000,000.")
        return value


class BlockUserSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=255, required=False, allow_blank=True,
                                   help_text="Kept on the account and in the audit log.")


class PriceRuleUpdateSerializer(serializers.Serializer):
    prices = serializers.DictField(child=serializers.IntegerField(min_value=0))

    def validate_prices(self, value: dict) -> dict:
        valid = {k for k, _ in PriceRule.Key.choices}
        unknown = set(value) - valid
        if unknown:
            raise serializers.ValidationError(f"Unknown price keys: {', '.join(sorted(unknown))}")
        return value


class CreditPackAdminSerializer(serializers.ModelSerializer):
    class Meta:
        model = CreditPack
        fields = ["id", "slug", "name", "credits", "bonus_credits", "price_krw", "price_usd_cents",
                  "credit_expiry_days", "highlight", "active", "sort_order", "created_at"]


class PlanAdminSerializer(serializers.ModelSerializer):
    class Meta:
        model = Plan
        fields = ["id", "slug", "name", "description", "features", "monthly_credits", "price_krw",
                  "price_usd_cents", "priority", "retention_days", "api_access", "max_inflight_tasks", "highlight",
                  "active", "sort_order", "created_at"]


class PaymentAdminSerializer(serializers.ModelSerializer):
    user_email = serializers.EmailField(source="user.email", read_only=True)

    class Meta:
        model = Payment
        fields = ["id", "order_id", "order_name", "user", "user_email", "provider", "kind", "status", "currency",
                  "amount", "credits", "bonus_credits", "provider_payment_id", "method", "receipt_url", "paid_at",
                  "refunded_amount", "failure_reason", "created_at"]


class RefundRequestSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=255)
    override_full = serializers.BooleanField(default=False, help_text="Company fault: refund everything.")
    amount = serializers.IntegerField(min_value=1, required=False)


class PlatformSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = PlatformSettings
        # What jobs run is edited (and validated) on Admin → Models (DetectionSetupView).
        exclude = ["id", "audit_steps", "long_video_model", "long_video_face_crops"]
        read_only_fields = ["updated_at"]


class AuditLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = AuditLog
        fields = ["id", "created_at", "actor", "actor_label", "action", "target_type", "target_id", "target_label",
                  "before", "after", "ip", "user_agent", "request_id"]


class WebhookEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = WebhookEvent
        fields = ["id", "provider", "event_id", "event_type", "received_at", "processed_at", "error"]
