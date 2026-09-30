from __future__ import annotations

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from .models import CreditPack, Payment, Plan, Provider, Subscription, localized
from .services import display_price


class PriceSerializer(serializers.Serializer):
    amount = serializers.IntegerField(help_text="Minor units (KRW: won, USD: cents)")
    display = serializers.CharField()


class PricesSerializer(serializers.Serializer):
    KRW = PriceSerializer()
    USD = PriceSerializer()


def _lang(ctx: dict) -> str:
    return ctx.get("lang", "en")


class CreditPackSerializer(serializers.ModelSerializer):
    display_name = serializers.SerializerMethodField()
    prices = serializers.SerializerMethodField()

    class Meta:
        model = CreditPack
        fields = ["id", "slug", "display_name", "credits", "bonus_credits", "prices", "credit_expiry_days",
                  "highlight"]

    @extend_schema_field(OpenApiTypes.STR)
    def get_display_name(self, obj: CreditPack) -> str:
        return localized(obj.name, _lang(self.context))

    @extend_schema_field(PricesSerializer)
    def get_prices(self, obj: CreditPack) -> dict:
        return {"KRW": {"amount": obj.price_krw, "display": display_price(obj.price_krw, "KRW")},
                "USD": {"amount": obj.price_usd_cents, "display": display_price(obj.price_usd_cents, "USD")}}


class PlanSerializer(serializers.ModelSerializer):
    display_name = serializers.SerializerMethodField()
    display_description = serializers.SerializerMethodField()
    display_features = serializers.SerializerMethodField()
    prices = serializers.SerializerMethodField()

    class Meta:
        model = Plan
        fields = ["id", "slug", "display_name", "display_description", "display_features", "monthly_credits",
                  "prices", "priority", "retention_days", "api_access", "max_inflight_tasks", "highlight"]

    @extend_schema_field(OpenApiTypes.STR)
    def get_display_name(self, obj: Plan) -> str:
        return localized(obj.name, _lang(self.context))

    @extend_schema_field(OpenApiTypes.STR)
    def get_display_description(self, obj: Plan) -> str:
        return localized(obj.description, _lang(self.context))

    @extend_schema_field(serializers.ListField(child=serializers.CharField()))
    def get_display_features(self, obj: Plan) -> list[str]:
        feats = obj.features or {}
        return feats.get(_lang(self.context)) or feats.get("en") or []

    @extend_schema_field(PricesSerializer)
    def get_prices(self, obj: Plan) -> dict:
        return {"KRW": {"amount": obj.price_krw, "display": display_price(obj.price_krw, "KRW")},
                "USD": {"amount": obj.price_usd_cents, "display": display_price(obj.price_usd_cents, "USD")}}


class PaymentSerializer(serializers.ModelSerializer):
    display_amount = serializers.SerializerMethodField()
    status_label = serializers.CharField(source="get_status_display")
    kind_label = serializers.CharField(source="get_kind_display")

    class Meta:
        model = Payment
        fields = ["id", "order_id", "order_name", "provider", "kind", "kind_label", "status", "status_label",
                  "currency", "amount", "display_amount", "credits", "bonus_credits", "method", "receipt_url",
                  "paid_at", "period_start", "period_end", "refunded_amount", "created_at", "failure_reason"]

    @extend_schema_field(OpenApiTypes.STR)
    def get_display_amount(self, obj: Payment) -> str:
        return display_price(obj.amount, obj.currency)


class SubscriptionSerializer(serializers.ModelSerializer):
    plan = PlanSerializer(read_only=True)

    class Meta:
        model = Subscription
        fields = ["id", "plan", "provider", "currency", "status", "current_period_start", "current_period_end",
                  "cancel_at_period_end", "canceled_at", "created_at"]


class CheckoutSerializer(serializers.Serializer):
    product = serializers.ChoiceField(choices=["pack", "plan"])
    product_id = serializers.UUIDField()
    provider = serializers.ChoiceField(choices=Provider.choices)
