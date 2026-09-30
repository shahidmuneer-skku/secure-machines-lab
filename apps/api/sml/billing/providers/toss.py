"""Toss Payments adapter (KRW): payment widget + server-side confirm, billing keys for subscriptions.

Flow (packs):   browser SDK requestPayment → successUrl?paymentKey&orderId&amount
                → POST /billing/toss/confirm → we call /v1/payments/confirm (secret key) → credits.
Flow (plans):   browser SDK requestBillingAuth → successUrl?authKey&customerKey
                → POST /billing/toss/billing-confirm → issue billingKey → charge first month.
Renewals are charged by the `renew_subscriptions` beat task with the stored (encrypted) billing key.
Webhooks are not signed by Toss for payment events, so every webhook is verified by re-fetching the payment.
"""

from __future__ import annotations

import base64
import json
from datetime import datetime
from typing import Any

import httpx
from django.conf import settings
from django.utils.dateparse import parse_datetime

from sml.core.exceptions import ProviderError

from ..models import BillingCustomer
from .base import CheckoutResult, ProviderEvent, VerifiedPayment


class TossProvider:
    name = "toss"

    def is_configured(self) -> bool:
        return bool(settings.TOSS_CLIENT_KEY and settings.TOSS_SECRET_KEY)

    def _client(self) -> httpx.Client:
        token = base64.b64encode(f"{settings.TOSS_SECRET_KEY}:".encode()).decode()
        return httpx.Client(base_url=settings.TOSS_API_BASE, timeout=30.0,
                            headers={"Authorization": f"Basic {token}", "Content-Type": "application/json"})

    def _post(self, path: str, body: dict[str, Any], idempotency_key: str | None = None) -> dict[str, Any]:
        headers = {"Idempotency-Key": idempotency_key} if idempotency_key else {}
        with self._client() as client:
            resp = client.post(path, json=body, headers=headers)
        data = resp.json() if resp.content else {}
        if resp.status_code >= 400:
            raise ProviderError(data.get("message") or f"Toss error {resp.status_code}",
                                extra={"provider_code": data.get("code", "")})
        return data

    def _get(self, path: str) -> dict[str, Any]:
        with self._client() as client:
            resp = client.get(path)
        data = resp.json() if resp.content else {}
        if resp.status_code >= 400:
            raise ProviderError(data.get("message") or f"Toss error {resp.status_code}")
        return data

    @staticmethod
    def _verified(data: dict[str, Any]) -> VerifiedPayment:
        receipt = (data.get("receipt") or {}).get("url", "")
        approved = parse_datetime(data["approvedAt"]) if data.get("approvedAt") else None
        return VerifiedPayment(provider_payment_id=data["paymentKey"], amount=int(data.get("totalAmount", 0)),
                               currency=data.get("currency", "KRW"), method=data.get("method", ""),
                               receipt_url=receipt, paid_at=approved, raw=_safe(data))

    def _customer_key(self, user: Any) -> str:
        cust, _ = BillingCustomer.objects.get_or_create(user=user)
        return str(cust.toss_customer_key)

    # --- checkout ---------------------------------------------------------------------

    def create_pack_checkout(self, payment: Any, *, success_url: str, cancel_url: str) -> CheckoutResult:
        return CheckoutResult(self.name, client_params={
            "clientKey": settings.TOSS_CLIENT_KEY, "customerKey": self._customer_key(payment.user),
            "flow": "payment", "orderId": payment.order_id, "orderName": payment.order_name,
            "amount": {"currency": "KRW", "value": payment.amount},
            "successUrl": success_url, "failUrl": cancel_url, "customerEmail": payment.user.email,
        })

    def create_subscription_checkout(self, payment: Any, subscription: Any, *, success_url: str,
                                     cancel_url: str) -> CheckoutResult:
        return CheckoutResult(self.name, client_params={
            "clientKey": settings.TOSS_CLIENT_KEY, "customerKey": self._customer_key(payment.user),
            "flow": "billing", "orderId": payment.order_id, "orderName": payment.order_name,
            "amount": {"currency": "KRW", "value": payment.amount},
            "successUrl": success_url, "failUrl": cancel_url, "customerEmail": payment.user.email,
        })

    def confirm_payment(self, *, payment_key: str, order_id: str, amount: int) -> VerifiedPayment:
        data = self._post("/v1/payments/confirm", {"paymentKey": payment_key, "orderId": order_id,
                                                   "amount": amount}, idempotency_key=f"confirm-{order_id}")
        if data.get("status") != "DONE":
            raise ProviderError(f"Payment not completed (status {data.get('status')}).")
        return self._verified(data)

    def issue_billing_key(self, *, auth_key: str, customer_key: str) -> str:
        data = self._post("/v1/billing/authorizations/issue", {"authKey": auth_key, "customerKey": customer_key})
        return data["billingKey"]

    def charge_billing_key(self, *, billing_key: str, customer_key: str, order_id: str, order_name: str,
                           amount: int, email: str) -> VerifiedPayment:
        data = self._post(f"/v1/billing/{billing_key}", {
            "customerKey": customer_key, "amount": amount, "orderId": order_id, "orderName": order_name,
            "customerEmail": email}, idempotency_key=f"charge-{order_id}")
        if data.get("status") != "DONE":
            raise ProviderError(f"Billing charge not completed (status {data.get('status')}).")
        return self._verified(data)

    def fetch_payment(self, payment_key: str) -> dict[str, Any]:
        return self._get(f"/v1/payments/{payment_key}")

    # --- webhooks / refunds -----------------------------------------------------------

    def parse_webhook(self, body: bytes, headers: dict[str, str]) -> list[ProviderEvent]:
        try:
            payload = json.loads(body)
        except ValueError as exc:
            raise ProviderError("Invalid webhook body.") from exc
        if payload.get("eventType") != "PAYMENT_STATUS_CHANGED":
            return []
        key = (payload.get("data") or {}).get("paymentKey")
        if not key:
            return []
        data = self.fetch_payment(key)  # authoritative state from the API
        status = data.get("status", "")
        mapped = {"DONE": "payment.paid", "CANCELED": "payment.refunded", "PARTIAL_CANCELED": "payment.refunded",
                  "ABORTED": "payment.failed", "EXPIRED": "payment.failed"}.get(status)
        if not mapped:
            return []
        canceled = sum(int(c.get("cancelAmount", 0)) for c in data.get("cancels") or [])
        event_id = f"{key}:{status}:{data.get('lastTransactionKey', '')}"
        return [ProviderEvent(event_id, mapped, order_id=data.get("orderId", ""), provider_payment_id=key,
                              amount=canceled if mapped == "payment.refunded" else int(data.get("totalAmount", 0)),
                              currency=data.get("currency", "KRW"),
                              receipt_url=(data.get("receipt") or {}).get("url", ""), raw=_safe(data))]

    def refund(self, payment: Any, amount: int, reason: str) -> str:
        data = self._post(f"/v1/payments/{payment.provider_payment_id}/cancel",
                          {"cancelReason": reason[:200] or "Refund", "cancelAmount": amount},
                          idempotency_key=f"refund-{payment.order_id}-{payment.refunded_amount + amount}")
        cancels = data.get("cancels") or []
        return cancels[-1].get("transactionKey", "") if cancels else data.get("lastTransactionKey", "")

    def cancel_subscription(self, subscription: Any, *, at_period_end: bool) -> None:
        # Toss has no subscription object: we simply stop charging the billing key.
        return None

    def portal_url(self, user: Any, return_url: str) -> str | None:
        return None


def _safe(data: dict[str, Any]) -> dict[str, Any]:
    """Keep only non-sensitive fields of a Toss payment object."""
    keep = ("paymentKey", "orderId", "orderName", "status", "method", "totalAmount", "balanceAmount", "currency",
            "approvedAt", "requestedAt", "type", "lastTransactionKey")
    out = {k: data.get(k) for k in keep if k in data}
    card = data.get("card") or {}
    if card:
        out["card"] = {"issuerCode": card.get("issuerCode"), "cardType": card.get("cardType"),
                       "number": card.get("number")}  # already masked by Toss
    return out


def parse_iso(value: str | None) -> datetime | None:
    return parse_datetime(value) if value else None
