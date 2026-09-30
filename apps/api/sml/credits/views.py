from __future__ import annotations

import csv

from django.http import StreamingHttpResponse
from django_filters import rest_framework as filters
from drf_spectacular.utils import extend_schema
from rest_framework import generics
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from sml import api_schemas as schemas
from sml.core.models import PlatformSettings

from .models import LedgerEntry, PriceRule
from .pricing import price_table
from .serializers import BalanceSerializer, LedgerEntrySerializer, PriceRuleSerializer
from .services import get_balance

LOW_BALANCE_THRESHOLD = 10


class BalanceView(APIView):
    @extend_schema(tags=["credits"], responses=BalanceSerializer, summary="Current credit balance")
    def get(self, request: Request) -> Response:
        s = get_balance(request.user)
        data = {
            "balance": s.balance, "held": s.held, "unlimited": s.unlimited, "by_source": s.by_source,
            "next_expiry_at": s.next_expiry_at, "next_expiry_amount": s.next_expiry_amount,
            "daily_free_credits": PlatformSettings.load().daily_free_credits,
            "low_balance": (not s.unlimited) and s.balance < LOW_BALANCE_THRESHOLD,
        }
        return Response(BalanceSerializer(data).data)


class LedgerFilter(filters.FilterSet):
    kind = filters.MultipleChoiceFilter(choices=LedgerEntry._meta.get_field("kind").choices)
    created_after = filters.IsoDateTimeFilter(field_name="created_at", lookup_expr="gte")
    created_before = filters.IsoDateTimeFilter(field_name="created_at", lookup_expr="lt")

    class Meta:
        model = LedgerEntry
        fields = ["kind", "reference_type", "reference_id"]


class LedgerView(generics.ListAPIView):
    serializer_class = LedgerEntrySerializer
    queryset = LedgerEntry.objects.none()
    filterset_class = LedgerFilter

    def get_queryset(self):  # type: ignore[no-untyped-def]
        return LedgerEntry.objects.filter(wallet__user=self.request.user)

    @extend_schema(tags=["credits"], summary="Credit ledger (newest first)")
    def get(self, request: Request, *args, **kwargs) -> Response:  # type: ignore[no-untyped-def]
        return super().get(request, *args, **kwargs)


class _Echo:
    def write(self, value: str) -> str:
        return value


class LedgerExportView(APIView):
    @extend_schema(tags=["credits"], summary="Export ledger as CSV", responses={200: bytes})
    def get(self, request: Request) -> StreamingHttpResponse:
        qs = LedgerFilter(request.GET, LedgerEntry.objects.filter(wallet__user=request.user)).qs
        writer = csv.writer(_Echo())

        def rows():  # type: ignore[no-untyped-def]
            yield writer.writerow(["created_at", "kind", "delta", "balance_after", "reference", "memo"])
            for e in qs.order_by("-created_at").iterator():
                yield writer.writerow([e.created_at.isoformat(), e.kind, e.delta, e.balance_after,
                                       f"{e.reference_type}:{e.reference_id}".strip(":"), e.memo])

        resp = StreamingHttpResponse(rows(), content_type="text/csv; charset=utf-8")
        resp["Content-Disposition"] = 'attachment; filename="credit-ledger.csv"'
        return resp


class PriceListView(APIView):
    """Public price list (used by the pricing page)."""

    permission_classes = [AllowAny]

    @extend_schema(tags=["credits"], responses=schemas.PriceListSerializer, summary="Credit prices")
    def get(self, request: Request) -> Response:
        table = price_table()
        labels = dict(PriceRule.Key.choices)
        cfg = PlatformSettings.load()
        return Response({
            "prices": [{"key": k, "label": labels.get(k, k), "credits": v} for k, v in table.items()],
            "free": {
                "guest_trial_images_per_day": cfg.guest_trial_images_per_day if cfg.guest_trial_enabled else 0,
                "signup_bonus_credits": cfg.signup_bonus_credits,
                "signup_bonus_expiry_days": cfg.signup_bonus_expiry_days,
                "daily_free_credits": cfg.daily_free_credits,
            },
        })
