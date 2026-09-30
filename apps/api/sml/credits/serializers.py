from rest_framework import serializers

from .models import LedgerEntry, PriceRule


class BalanceSerializer(serializers.Serializer):
    balance = serializers.IntegerField()
    held = serializers.IntegerField(help_text="Credits reserved by jobs still running.")
    unlimited = serializers.BooleanField()
    by_source = serializers.DictField(child=serializers.IntegerField())
    next_expiry_at = serializers.DateTimeField(allow_null=True)
    next_expiry_amount = serializers.IntegerField()
    daily_free_credits = serializers.IntegerField()
    low_balance = serializers.BooleanField()


class LedgerEntrySerializer(serializers.ModelSerializer):
    kind_label = serializers.CharField(source="get_kind_display")

    class Meta:
        model = LedgerEntry
        fields = ["id", "created_at", "kind", "kind_label", "delta", "balance_after",
                  "reference_type", "reference_id", "memo"]


class PriceRuleSerializer(serializers.ModelSerializer):
    label = serializers.CharField(source="get_key_display", read_only=True)

    class Meta:
        model = PriceRule
        fields = ["key", "label", "credits", "updated_at"]
        read_only_fields = ["key", "updated_at"]


class QuoteLineSerializer(serializers.Serializer):
    label = serializers.CharField()
    credits = serializers.IntegerField()


class QuoteSerializer(serializers.Serializer):
    credits = serializers.IntegerField()
    lines = QuoteLineSerializer(many=True)
