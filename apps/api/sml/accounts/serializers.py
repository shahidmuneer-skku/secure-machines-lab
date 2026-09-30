from __future__ import annotations

from rest_framework import serializers

from .models import TrainingConsent, User


class MeSerializer(serializers.ModelSerializer):
    roles = serializers.ListField(source="role_names", read_only=True)
    requires_mfa = serializers.BooleanField(read_only=True)
    has_mfa = serializers.BooleanField(read_only=True)
    is_staff_user = serializers.SerializerMethodField()
    capabilities = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ["id", "email", "display_name", "locale", "time_zone", "marketing_opt_in", "date_joined",
                  "roles", "requires_mfa", "has_mfa", "is_staff_user", "capabilities"]
        read_only_fields = ["id", "email", "date_joined"]

    def get_is_staff_user(self, obj: User) -> bool:
        return obj.groups.filter(role_profile__is_staff_role=True).exists()

    def get_capabilities(self, obj: User) -> list[str]:
        return sorted(p.split(".", 1)[1] for p in obj.get_all_permissions() if p.startswith("accounts."))

    def validate_time_zone(self, value: str) -> str:
        from zoneinfo import available_timezones

        if value not in available_timezones():
            raise serializers.ValidationError("Unknown time zone.")
        return value


class ConsentSerializer(serializers.ModelSerializer):
    class Meta:
        model = TrainingConsent
        fields = ["granted", "granted_at", "withdrawn_at", "policy_version"]
        read_only_fields = ["granted_at", "withdrawn_at", "policy_version"]
