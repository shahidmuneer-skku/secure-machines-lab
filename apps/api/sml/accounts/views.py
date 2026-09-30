from __future__ import annotations

from django.conf import settings
from django.contrib.auth import logout
from django.db.models import Count
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import serializers, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from sml import api_schemas as schemas
from sml.catalog import access
from sml.core import audit
from sml.core.captcha import captcha_enabled
from sml.core.exceptions import ApiError
from sml.core.models import PlatformSettings
from sml.core.permissions import SessionOnly

from .models import TrainingConsent
from .serializers import ConsentSerializer, MeSerializer


class PublicConfigView(APIView):
    permission_classes = [AllowAny]
    authentication_classes: list = []

    @extend_schema(tags=["account"], responses=schemas.PublicConfigSerializer, summary="Public client configuration")
    def get(self, request: Request) -> Response:
        cfg = PlatformSettings.load()
        return Response({
            "signups_enabled": cfg.signups_enabled, "maintenance_mode": cfg.maintenance_mode,
            "announcement": cfg.announcement, "captcha_site_key": settings.TURNSTILE_SITE_KEY,
            "captcha_enabled": captcha_enabled(), "billing_enabled": settings.BILLING_ENABLED,
            "languages": [code for code, _ in settings.LANGUAGES], "guest_trial_enabled": cfg.guest_trial_enabled,
        })


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=["account"], responses=schemas.MeResponseSerializer,
                   summary="Current user, roles and capabilities")
    def get(self, request: Request) -> Response:
        data = MeSerializer(request.user).data
        policy = getattr(request.user, "access_policy", None)
        data["access"] = {
            "modules": {m: access.module_allowed(request.user, m) for m in ("detect", "long_video", "news")},
            "audit_steps": access.allowed_audit_steps(request.user),
            "unlimited_credits": bool(policy and policy.unlimited_credits),
        }
        return Response(data)

    @extend_schema(tags=["account"], request=MeSerializer, responses=MeSerializer, summary="Update profile")
    def patch(self, request: Request) -> Response:
        if not isinstance(getattr(request, "auth", None), type(None)) and hasattr(request.auth, "prefix"):
            raise ApiError("API keys cannot change the profile.")
        ser = MeSerializer(request.user, data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        ser.save()
        return Response(ser.data)


class ConsentView(APIView):
    permission_classes = [IsAuthenticated, SessionOnly]

    @extend_schema(tags=["account"], responses=ConsentSerializer, summary="AI-training consent status")
    def get(self, request: Request) -> Response:
        consent, _ = TrainingConsent.objects.get_or_create(user=request.user)
        return Response(ConsentSerializer(consent).data)

    @extend_schema(tags=["account"], request=ConsentSerializer, responses=ConsentSerializer,
                   summary="Grant or withdraw consent to use your uploads for model improvement")
    def put(self, request: Request) -> Response:
        consent, _ = TrainingConsent.objects.get_or_create(user=request.user)
        granted = bool(request.data.get("granted"))
        before = {"granted": consent.granted}
        consent.set(granted)
        if not granted:
            request.user.media.filter(training_consent=True).update(training_consent=False)
        audit.record("privacy.training_consent", request=request, target=request.user, before=before,
                     after={"granted": granted})
        return Response(ConsentSerializer(consent).data)


class DataExportView(APIView):
    permission_classes = [IsAuthenticated, SessionOnly]

    @extend_schema(tags=["account"], responses={200: dict},
                   summary="Download a JSON export of your personal data (PIPA/GDPR)")
    def get(self, request: Request) -> Response:
        user = request.user
        from sml.billing.models import Payment
        from sml.credits.models import LedgerEntry
        from sml.jobs.models import Job

        data = {
            "exported_at": timezone.now().isoformat(),
            "profile": MeSerializer(user).data,
            "jobs": list(Job.objects.filter(user=user).values(
                "id", "created_at", "kind", "status", "title", "media_type", "models_selected", "verdict",
                "fake_probability", "credits_charged")),
            "credit_ledger": list(LedgerEntry.objects.filter(wallet__user=user).values(
                "created_at", "kind", "delta", "balance_after", "memo")),
            "payments": list(Payment.objects.filter(user=user).values(
                "order_id", "created_at", "provider", "kind", "status", "currency", "amount", "credits")),
            "api_keys": list(user.api_keys.values("name", "created_at", "scopes", "revoked_at", "last_used_at")),
            "job_counts": dict(Job.objects.filter(user=user).values_list("status").annotate(n=Count("id"))),
        }
        resp = Response(data)
        resp["Content-Disposition"] = 'attachment; filename="sml-data-export.json"'
        return resp


class DeleteAccountSerializer(serializers.Serializer):
    password = serializers.CharField()
    confirm = serializers.CharField(help_text='Type "DELETE" to confirm.')


class DeleteAccountView(APIView):
    permission_classes = [IsAuthenticated, SessionOnly]

    @extend_schema(tags=["account"], request=DeleteAccountSerializer, responses={204: None},
                   summary="Delete my account: media is purged, API keys revoked, "
                           "billing records kept as required by law")
    def post(self, request: Request) -> Response:
        ser = DeleteAccountSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        user = request.user
        if ser.validated_data["confirm"] != "DELETE" or not user.check_password(ser.validated_data["password"]):
            raise ApiError("Password incorrect or confirmation text missing.")
        from sml.apikeys.services import revoke
        from sml.jobs.retention_tasks import purge_job_files

        for key in user.api_keys.filter(revoked_at__isnull=True):
            revoke(key)
        for job in user.jobs.filter(purged_at__isnull=True):
            purge_job_files(job)
        from allauth.account.models import EmailAddress
        from allauth.mfa.models import Authenticator

        EmailAddress.objects.filter(user=user).delete()
        Authenticator.objects.filter(user=user).delete()
        user.is_active = False
        user.deletion_requested_at = timezone.now()
        user.disabled_reason = "Deleted by user"
        user.email = f"deleted+{user.pk}@deleted.invalid"
        user.display_name = ""
        user.set_unusable_password()
        user.save()
        audit.record("account.deleted", request=request, actor=None, target_type="accounts.user",
                     target_id=str(user.pk))
        logout(request)
        return Response(status=status.HTTP_204_NO_CONTENT)
