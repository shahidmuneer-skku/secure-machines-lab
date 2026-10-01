from __future__ import annotations

import ipaddress

from django.utils import timezone
from rest_framework import serializers

from .models import ApiKey, ApiKeyUsageDaily, ApiRequestLog, Scope


class ApiKeySerializer(serializers.ModelSerializer):
    display_key = serializers.CharField(read_only=True)
    status = serializers.CharField(read_only=True)
    scopes = serializers.ListField(child=serializers.ChoiceField(choices=Scope.choices), allow_empty=False)
    allowed_ips = serializers.ListField(child=serializers.CharField(max_length=64), required=False)
    rate_limit_per_minute = serializers.IntegerField(min_value=1, max_value=6000, required=False, allow_null=True)

    class Meta:
        model = ApiKey
        fields = ["id", "name", "display_key", "status", "scopes", "allowed_ips",
                  "rate_limit_per_minute", "expires_at", "created_at", "last_used_at", "last_used_ip",
                  "revoked_at"]
        read_only_fields = ["id", "display_key", "status", "created_at", "last_used_at", "last_used_ip",
                            "revoked_at"]

    def validate_allowed_ips(self, value: list[str]) -> list[str]:
        out = []
        for cidr in value:
            try:
                out.append(str(ipaddress.ip_network(cidr.strip(), strict=False)))
            except ValueError as exc:
                raise serializers.ValidationError(f"Invalid IP or CIDR: {cidr}") from exc
        return out

    def validate_expires_at(self, value):  # type: ignore[no-untyped-def]
        if value is not None and value <= timezone.now():
            raise serializers.ValidationError("Expiry must be in the future.")
        return value


class ApiKeyCreatedSerializer(ApiKeySerializer):
    key = serializers.CharField(read_only=True, help_text="The full key. Shown only once; store it securely.")

    class Meta(ApiKeySerializer.Meta):
        fields = [*ApiKeySerializer.Meta.fields, "key"]


class ApiKeyUsageDailySerializer(serializers.ModelSerializer):
    class Meta:
        model = ApiKeyUsageDaily
        fields = ["date", "requests", "errors", "jobs_created", "credits_spent"]


class ApiRequestLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = ApiRequestLog
        fields = ["created_at", "method", "path", "status", "duration_ms", "ip", "request_id"]
