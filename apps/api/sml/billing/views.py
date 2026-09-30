from __future__ import annotations

import logging

from django.conf import settings
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import generics, serializers, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from sml.core.exceptions import ApiError
from sml.core.idempotency import idempotent
from sml.core.permissions import SessionOnly, require

from . import services
from .models import CreditPack, Payment, Plan, Subscription
from .providers import enabled_providers
from .serializers import (
    CheckoutSerializer,
    CreditPackSerializer,
    PaymentSerializer,
    PlanSerializer,
    SubscriptionSerializer,
)

logger = logging.getLogger(__name__)
BUYER = [IsAuthenticated, SessionOnly, require("purchase_credits")]


def _lang(request: Request) -> str:
    lang = request.query_params.get("lang") or getattr(request.user, "locale", None) or "en"
    return lang if lang in ("en", "ko", "de") else "en"


class CatalogView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(tags=["billing"], summary="Credit packs, subscription plans and available payment methods")
    def get(self, request: Request) -> Response:
        ctx = {"lang": _lang(request)}
        providers = enabled_providers()
        return Response({
            "billing_enabled": settings.BILLING_ENABLED,
            "providers": [{"id": p, "currency": {"toss": "KRW", "stripe": "USD", "mock": "USD"}[p]} for p in providers],
            "toss_client_key": settings.TOSS_CLIENT_KEY if "toss" in providers else "",
            "packs": CreditPackSerializer(CreditPack.objects.filter(active=True), many=True, context=ctx).data,
            "plans": PlanSerializer(Plan.objects.filter(active=True), many=True, context=ctx).data,
        })


class CheckoutView(APIView):
    permission_classes = BUYER

    @extend_schema(tags=["billing"], request=CheckoutSerializer,
                   parameters=[OpenApiParameter("Idempotency-Key", str, OpenApiParameter.HEADER, required=True)],
                   summary="Start a checkout. Returns a redirect URL (Stripe) or SDK parameters (Toss)")
    @idempotent()
    def post(self, request: Request) -> Response:
        ser = CheckoutSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data
        if d["product"] == "pack":
            pack = get_object_or_404(CreditPack, pk=d["product_id"], active=True)
            payment, result = services.start_pack_checkout(request.user, pack, d["provider"])
        else:
            plan = get_object_or_404(Plan, pk=d["product_id"], active=True)
            payment, result = services.start_subscription_checkout(request.user, plan, d["provider"])
        return Response({"order_id": payment.order_id, "provider": result.provider,
                         "redirect_url": result.redirect_url, "client_params": result.client_params},
                        status=status.HTTP_201_CREATED)


class TossConfirmSerializer(serializers.Serializer):
    payment_key = serializers.CharField(max_length=200)
    order_id = serializers.CharField(max_length=64)
    amount = serializers.IntegerField(min_value=1)


class TossConfirmView(APIView):
    permission_classes = BUYER

    @extend_schema(tags=["billing"], request=TossConfirmSerializer, responses=PaymentSerializer,
                   summary="Confirm a Toss payment after the browser redirect (server verifies with Toss)")
    def post(self, request: Request) -> Response:
        ser = TossConfirmSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data
        payment = services.confirm_toss_payment(request.user, payment_key=d["payment_key"], order_id=d["order_id"],
                                                amount=d["amount"])
        return Response(PaymentSerializer(payment).data)


class TossBillingConfirmSerializer(serializers.Serializer):
    auth_key = serializers.CharField(max_length=200)
    customer_key = serializers.CharField(max_length=64)
    order_id = serializers.CharField(max_length=64)


class TossBillingConfirmView(APIView):
    permission_classes = BUYER

    @extend_schema(tags=["billing"], request=TossBillingConfirmSerializer, responses=PaymentSerializer,
                   summary="Finish a Toss subscription: issue the billing key and charge the first month")
    def post(self, request: Request) -> Response:
        ser = TossBillingConfirmSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data
        payment = services.confirm_toss_billing(request.user, auth_key=d["auth_key"], customer_key=d["customer_key"],
                                                order_id=d["order_id"])
        return Response(PaymentSerializer(payment).data)


class MockCompleteView(APIView):
    permission_classes = BUYER

    @extend_schema(exclude=True)
    def post(self, request: Request) -> Response:
        if not settings.DEBUG:
            raise ApiError("Not available.")
        payment = services.complete_mock_payment(request.user, str(request.data.get("order_id", "")))
        return Response(PaymentSerializer(payment).data)


class WebhookView(APIView):
    """Provider webhooks: unauthenticated by design; authenticity is verified per provider."""

    permission_classes = [AllowAny]
    authentication_classes: list = []
    throttle_classes: list = []

    @extend_schema(exclude=True)
    def post(self, request: Request, provider: str) -> Response:
        if provider not in ("stripe", "toss"):
            return Response(status=status.HTTP_404_NOT_FOUND)
        headers = {k.lower(): v for k, v in request.headers.items()}
        count = services.handle_webhook(provider, request.body, headers)
        return Response({"received": count})


class PaymentListView(generics.ListAPIView):
    serializer_class = PaymentSerializer
    permission_classes = [IsAuthenticated, SessionOnly]

    def get_queryset(self):  # type: ignore[no-untyped-def]
        return Payment.objects.filter(user=self.request.user).exclude(status=Payment.Status.PENDING)

    @extend_schema(tags=["billing"], summary="My payments and receipts")
    def get(self, request: Request, *args, **kwargs) -> Response:  # type: ignore[no-untyped-def]
        return super().get(request, *args, **kwargs)


class PaymentStatusView(APIView):
    permission_classes = [IsAuthenticated, SessionOnly]

    @extend_schema(tags=["billing"], responses=PaymentSerializer, summary="Status of one order (after redirect)")
    def get(self, request: Request, order_id: str) -> Response:
        return Response(PaymentSerializer(get_object_or_404(Payment, order_id=order_id, user=request.user)).data)


class SubscriptionView(APIView):
    permission_classes = [IsAuthenticated, SessionOnly]

    def _current(self, request: Request) -> Subscription | None:
        return (Subscription.objects.filter(user=request.user)
                .exclude(status=Subscription.Status.INCOMPLETE).select_related("plan").first())

    @extend_schema(tags=["billing"], responses=SubscriptionSerializer, summary="My current subscription")
    def get(self, request: Request) -> Response:
        sub = self._current(request)
        return Response(SubscriptionSerializer(sub, context={"lang": _lang(request)}).data if sub else None)


class SubscriptionActionView(SubscriptionView):
    @extend_schema(tags=["billing"], request=None, responses=SubscriptionSerializer,
                   summary="cancel (at period end) or resume the subscription")
    def post(self, request: Request, action: str) -> Response:
        sub = self._current(request)
        if sub is None:
            raise ApiError("No subscription.")
        if action == "cancel":
            sub = services.cancel_subscription(sub, actor=request.user)
        elif action == "resume":
            sub = services.resume_subscription(sub, actor=request.user)
        else:
            return Response(status=status.HTTP_404_NOT_FOUND)
        return Response(SubscriptionSerializer(sub, context={"lang": _lang(request)}).data)


class PortalView(APIView):
    permission_classes = [IsAuthenticated, SessionOnly]

    @extend_schema(tags=["billing"], request=None, summary="Stripe customer portal URL (cards, invoices)")
    def post(self, request: Request) -> Response:
        from .providers import get_provider

        url = get_provider("stripe").portal_url(request.user, f"{settings.PUBLIC_WEB_URL}/app/billing")
        if not url:
            raise ApiError("No Stripe billing profile yet.")
        return Response({"url": url})
