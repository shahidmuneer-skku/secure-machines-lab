"""Administration endpoints (/api/v1/admin/*).

Every view requires: a browser session (no API keys), a session verified with
MFA for staff roles, and the listed capability. Every mutation is audited.
"""

from __future__ import annotations

import csv
from datetime import timedelta

import httpx
from allauth.mfa.models import Authenticator
from allauth.usersessions.models import UserSession
from django.conf import settings
from django.contrib.auth.models import Group, Permission
from django.db.models import Count, Q, Sum
from django.http import StreamingHttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django_filters import rest_framework as filters
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import generics, mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from sml import api_schemas as schemas
from sml.accounts.models import CAPABILITY_CODENAMES, AccessPolicy, User
from sml.accounts.rbac import sync_staff_flag
from sml.apikeys.models import ApiKey, ApiKeyUsageDaily
from sml.billing import services as billing
from sml.billing.models import CreditPack, Payment, Plan, WebhookEvent
from sml.catalog.models import ModelOverride
from sml.catalog.registry import invalidate_overrides, registry
from sml.core import audit
from sml.core.exceptions import ApiError, Conflict
from sml.core.models import AuditLog, PlatformSettings
from sml.core.pagination import DefaultCursorPagination
from sml.core.permissions import admin_permissions, has_capability
from sml.credits import pricing
from sml.credits import services as credits
from sml.credits.models import LedgerEntry, PriceRule
from sml.jobs import live, streams
from sml.jobs.models import Job, JobTask
from sml.jobs.serializers import AdminJobDetailSerializer, AdminJobListSerializer
from sml.jobs.services import cancel_job

from . import system
from .serializers import (
    AccessPolicySerializer,
    AdminUserSerializer,
    AuditLogSerializer,
    BlockUserSerializer,
    CreditAdjustSerializer,
    CreditPackAdminSerializer,
    PaymentAdminSerializer,
    PlanAdminSerializer,
    PlatformSettingsSerializer,
    PriceRuleUpdateSerializer,
    RefundRequestSerializer,
    RoleSerializer,
    WebhookEventSerializer,
)

TAG = ["admin"]


class DateJoinedCursor(DefaultCursorPagination):
    ordering = "-date_joined"


class ReceivedAtCursor(DefaultCursorPagination):
    ordering = "-received_at"
SUPPORT_REFUND_LIMIT = {"KRW": 100_000, "USD": 10_000}


# --- overview -----------------------------------------------------------------------

class OverviewView(APIView):
    permission_classes = admin_permissions("view_users")

    @extend_schema(tags=TAG, responses=schemas.AdminOverviewSerializer, summary="Platform overview KPIs")
    def get(self, request: Request) -> Response:
        now = timezone.now()
        day, week, month = now - timedelta(days=1), now - timedelta(days=7), now - timedelta(days=30)
        tasks = JobTask.objects.values("status").annotate(n=Count("id"))
        revenue = (Payment.objects.filter(status__in=["paid", "partially_refunded"], paid_at__gte=month)
                   .values("currency").annotate(total=Sum("amount"), refunded=Sum("refunded_amount")))
        workers = live.workers()
        return Response({
            "users": {"total": User.objects.filter(is_active=True).count(),
                      "new_7d": User.objects.filter(date_joined__gte=week).count(),
                      "active_24h": User.objects.filter(last_login__gte=day).count()},
            "jobs_24h": dict(Job.objects.filter(created_at__gte=day).values_list("status").annotate(n=Count("id"))),
            "tasks_now": {r["status"]: r["n"] for r in tasks if r["status"] in ("pending", "dispatched", "running")},
            "failed_tasks_24h": JobTask.objects.filter(status="failed", finished_at__gte=day).count(),
            "revenue_30d": list(revenue),
            "credits_spent_30d": -(LedgerEntry.objects.filter(created_at__gte=month, kind__in=["reserve", "release"])
                                   .aggregate(t=Sum("delta"))["t"] or 0),
            "workers_online": len(workers),
            "gpus": sorted({f"{w.get('hostname')}:{w.get('gpu')}" for w in workers if w.get("gpu") not in (None, "")}),
            "maintenance_mode": PlatformSettings.load().maintenance_mode,
        })


# --- users ------------------------------------------------------------------------------

class UserFilter(filters.FilterSet):
    q = filters.CharFilter(method="search")
    role = filters.CharFilter(field_name="groups__name")
    is_active = filters.BooleanFilter()

    class Meta:
        model = User
        fields: list[str] = []

    def search(self, qs, name, value):  # type: ignore[no-untyped-def]
        return qs.filter(Q(email__icontains=value) | Q(display_name__icontains=value))


@extend_schema_view(list=extend_schema(tags=TAG), retrieve=extend_schema(tags=TAG),
                    partial_update=extend_schema(tags=TAG))
class UserViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.UpdateModelMixin,
                  viewsets.GenericViewSet):
    serializer_class = AdminUserSerializer
    filterset_class = UserFilter
    pagination_class = DateJoinedCursor
    http_method_names = ["get", "patch", "post", "put"]

    def get_permissions(self):  # type: ignore[no-untyped-def]
        write = self.request.method not in ("GET", "HEAD", "OPTIONS")
        caps = {"roles": "manage_roles", "access": "manage_user_access", "credits": "grant_credits"}.get(
            self.action or "", "manage_users" if write else "view_users")
        if self.action == "access" and not write:
            caps = "view_users"
        return [p() for p in admin_permissions(caps)]

    def get_queryset(self):  # type: ignore[no-untyped-def]
        return (User.objects.select_related("wallet").prefetch_related("groups")
                .annotate(jobs_count=Count("jobs")).order_by("-date_joined"))

    def perform_update(self, serializer):  # type: ignore[no-untyped-def]
        before = {k: getattr(serializer.instance, k) for k in ("display_name", "locale", "is_active")}
        user = serializer.save()
        audit.record("admin.user_updated", request=self.request, target=user, before=before,
                     after={k: getattr(user, k) for k in before})

    def _set_active(self, request: Request, active: bool) -> Response:
        user = self.get_object()
        if user == request.user:
            raise Conflict("You cannot block your own account.")
        if user.groups.filter(name="super_admin").exists() and not request.user.groups.filter(
                name="super_admin").exists():
            raise PermissionDenied("Only a super admin can block or unblock a super admin.")
        user.is_active = active
        user.disabled_reason = "" if active else str(request.data.get("reason", ""))[:255]
        user.save(update_fields=["is_active", "disabled_reason"])
        if not active:
            for session in UserSession.objects.filter(user=user):
                session.end()
        audit.record("admin.user_enabled" if active else "admin.user_disabled", request=request, target=user,
                     after={"reason": user.disabled_reason})
        return Response(AdminUserSerializer(user).data)

    @extend_schema(tags=TAG, request=BlockUserSerializer, responses=AdminUserSerializer,
                   summary="Block a user: they are signed out everywhere and cannot sign in or use API keys")
    @action(detail=True, methods=["post"])
    def disable(self, request: Request, pk: str) -> Response:
        BlockUserSerializer(data=request.data).is_valid(raise_exception=True)
        return self._set_active(request, False)

    @extend_schema(tags=TAG, request=None, responses=AdminUserSerializer, summary="Unblock a user")
    @action(detail=True, methods=["post"])
    def enable(self, request: Request, pk: str) -> Response:
        return self._set_active(request, True)

    @extend_schema(tags=TAG, request={"application/json": {"type": "object", "properties": {
        "roles": {"type": "array", "items": {"type": "string"}}}}})
    @action(detail=True, methods=["put"])
    def roles(self, request: Request, pk: str) -> Response:
        user = self.get_object()
        names = list(dict.fromkeys(request.data.get("roles") or []))
        groups = list(Group.objects.filter(name__in=names))
        if len(groups) != len(names):
            raise ApiError("Unknown role in list.")
        if "super_admin" in names and not request.user.groups.filter(name="super_admin").exists():
            raise ApiError("Only a super admin can grant super_admin.")
        before = user.role_names
        user.groups.set(groups)
        sync_staff_flag(user)
        # Privilege change: force re-authentication everywhere.
        for session in UserSession.objects.filter(user=user):
            session.end()
        audit.record("admin.user_roles", request=request, target=user, before={"roles": before},
                     after={"roles": names})
        return Response(AdminUserSerializer(User.objects.get(pk=user.pk)).data)

    @extend_schema(tags=TAG, request=AccessPolicySerializer, responses=AccessPolicySerializer)
    @action(detail=True, methods=["get", "put"])
    def access(self, request: Request, pk: str) -> Response:
        user = self.get_object()
        policy, _ = AccessPolicy.objects.get_or_create(user=user)
        if request.method == "GET":
            return Response(AccessPolicySerializer(policy).data)
        before = AccessPolicySerializer(policy).data
        ser = AccessPolicySerializer(policy, data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        ser.save()
        audit.record("admin.user_access", request=request, target=user, before=dict(before), after=dict(ser.data))
        return Response(ser.data)

    @extend_schema(tags=TAG, request=CreditAdjustSerializer, responses=schemas.CreditAdjustResultSerializer)
    @action(detail=True, methods=["post"])
    def credits(self, request: Request, pk: str) -> Response:
        user = self.get_object()
        ser = CreditAdjustSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data
        expires = timezone.now() + timedelta(days=d["expires_in_days"]) if d.get("expires_in_days") else None
        entry = credits.admin_adjust(user, d["delta"], actor=request.user, reason=d["reason"], expires_at=expires)
        audit.record("admin.credits_adjusted", request=request, target=user,
                     after={"requested": d["delta"], "applied": entry.delta, "reason": d["reason"]})
        return Response({"balance": credits.get_balance(user).balance, "applied": entry.delta,
                         "entry_id": str(entry.pk)})

    @extend_schema(tags=TAG, request=None, responses=schemas.CountSerializer)
    @action(detail=True, methods=["post"], url_path="reset-mfa")
    def reset_mfa(self, request: Request, pk: str) -> Response:
        user = self.get_object()
        count, _ = Authenticator.objects.filter(user=user).delete()
        for session in UserSession.objects.filter(user=user):
            session.end()
        audit.record("admin.mfa_reset", request=request, target=user, after={"removed": count})
        return Response({"removed": count})

    @extend_schema(tags=TAG, request=None, responses=schemas.CountSerializer)
    @action(detail=True, methods=["post"], url_path="revoke-sessions")
    def revoke_sessions(self, request: Request, pk: str) -> Response:
        user = self.get_object()
        n = 0
        for session in UserSession.objects.filter(user=user):
            session.end()
            n += 1
        audit.record("admin.sessions_revoked", request=request, target=user, after={"count": n})
        return Response({"revoked": n})

    @extend_schema(tags=TAG, responses={200: dict})
    @action(detail=True, methods=["get"])
    def ledger(self, request: Request, pk: str) -> Response:
        user = self.get_object()
        rows = LedgerEntry.objects.filter(wallet__user=user).values(
            "id", "created_at", "kind", "delta", "balance_after", "reference_type", "reference_id", "memo",
            "actor__email")[:200]
        return Response(list(rows))


# --- roles ----------------------------------------------------------------------------------

class RoleListView(APIView):
    permission_classes = admin_permissions("view_users")

    @extend_schema(tags=TAG, responses=RoleSerializer(many=True))
    def get(self, request: Request) -> Response:
        groups = Group.objects.select_related("role_profile").prefetch_related("permissions").annotate(
            members=Count("user"))
        from sml.accounts.models import CAPABILITIES

        return Response({"roles": RoleSerializer(groups, many=True).data,
                         "capabilities": [{"id": c, "label": label} for c, label in CAPABILITIES]})


class RoleDetailView(APIView):
    permission_classes = admin_permissions("manage_roles")

    @extend_schema(tags=TAG, request={"application/json": {"type": "object", "properties": {
        "capabilities": {"type": "array", "items": {"type": "string"}}}}}, responses=RoleSerializer)
    def put(self, request: Request, pk: int) -> Response:
        group = get_object_or_404(Group, pk=pk)
        if group.name == "super_admin":
            raise Conflict("super_admin always holds every capability.")
        caps = list(dict.fromkeys(request.data.get("capabilities") or []))
        unknown = set(caps) - set(CAPABILITY_CODENAMES)
        if unknown:
            raise ApiError(f"Unknown capabilities: {', '.join(sorted(unknown))}")
        before = sorted(group.permissions.values_list("codename", flat=True))
        group.permissions.set(Permission.objects.filter(content_type__app_label="accounts", codename__in=caps))
        audit.record("admin.role_updated", request=request, target_type="auth.group", target_id=str(group.pk),
                     target_label=group.name, before={"capabilities": before}, after={"capabilities": sorted(caps)})
        return Response(RoleSerializer(group).data)


# --- jobs ---------------------------------------------------------------------------------------

class AdminJobFilter(filters.FilterSet):
    status = filters.MultipleChoiceFilter(choices=Job.Status.choices)
    kind = filters.MultipleChoiceFilter(choices=Job.Kind.choices)
    source = filters.ChoiceFilter(choices=Job.Source.choices)
    user = filters.UUIDFilter(field_name="user_id")
    q = filters.CharFilter(method="search")

    class Meta:
        model = Job
        fields: list[str] = []

    def search(self, qs, name, value):  # type: ignore[no-untyped-def]
        return qs.filter(Q(title__icontains=value) | Q(user__email__icontains=value))


class AdminJobListView(generics.ListAPIView):
    serializer_class = AdminJobListSerializer
    filterset_class = AdminJobFilter
    permission_classes = admin_permissions("view_all_jobs")
    queryset = Job.objects.select_related("media", "user").prefetch_related("tasks")

    @extend_schema(tags=TAG)
    def get(self, request: Request, *args, **kwargs) -> Response:  # type: ignore[no-untyped-def]
        return super().get(request, *args, **kwargs)


class AdminJobDetailView(APIView):
    def get_permissions(self):  # type: ignore[no-untyped-def]
        cap = "manage_all_jobs" if self.request.method == "POST" else "view_all_jobs"
        return [p() for p in admin_permissions(cap)]

    @extend_schema(tags=TAG, responses=schemas.AdminJobViewSerializer)
    def get(self, request: Request, pk: str) -> Response:
        job = get_object_or_404(Job.objects.prefetch_related("tasks", "events", "artifacts"), pk=pk)
        data = AdminJobDetailSerializer(job, context={"request": request}).data
        data["user_email"] = job.user.email if job.user else None
        if not has_capability(request.user, "view_all_media"):
            data["media"] = None
            data["artifacts"] = []
        data["tasks_internal"] = list(job.tasks.values("id", "target", "status", "worker", "gpu", "attempt",
                                                       "error_code", "error_message", "error_detail",
                                                       "duration_ms"))
        return Response(data)

    @extend_schema(tags=TAG, request=None, responses=AdminJobListSerializer)
    def post(self, request: Request, pk: str) -> Response:
        job = cancel_job(get_object_or_404(Job, pk=pk), actor=request.user)
        audit.record("admin.job_canceled", request=request, target=job)
        return Response(AdminJobListSerializer(job, context={"request": request}).data)


class AdminTaskLogView(APIView):
    permission_classes = admin_permissions("view_all_jobs")

    @extend_schema(tags=TAG, responses=schemas.TaskLogSerializer,
                   summary="Live processing log of one task (detector output, GPU admission)")
    def get(self, request: Request, pk: str, task_id: str) -> Response:
        task = get_object_or_404(JobTask, pk=task_id, job_id=pk)
        return Response({"task_id": str(task.pk), "status": task.status, "lines": live.task_log(str(task.pk))})


# --- queues / workers / models --------------------------------------------------------------

class QueueView(APIView):
    permission_classes = admin_permissions("view_queues")

    @extend_schema(tags=TAG, responses=schemas.AdminQueuesSerializer,
                   summary="Queue depth and consumers (RabbitMQ) + task states (DB)")
    def get(self, request: Request) -> Response:
        rabbit: list[dict] = []
        error = None
        try:
            resp = httpx.get(
                f"{settings.RABBITMQ_MANAGEMENT_URL}/api/queues/{settings.RABBITMQ_VHOST}",
                auth=(settings.RABBITMQ_MANAGEMENT_USER, settings.RABBITMQ_MANAGEMENT_PASSWORD), timeout=5)
            resp.raise_for_status()
            for q in resp.json():
                if not q["name"].startswith("sml."):
                    continue  # skip Celery's internal pidbox / event queues
                stats = q.get("message_stats") or {}
                rabbit.append({
                    "name": q["name"], "messages": q.get("messages", 0), "ready": q.get("messages_ready", 0),
                    "unacked": q.get("messages_unacknowledged", 0), "consumers": q.get("consumers", 0),
                    "publish_rate": (stats.get("publish_details") or {}).get("rate", 0),
                    "deliver_rate": (stats.get("deliver_get_details") or {}).get("rate", 0),
                    "idle_since": q.get("idle_since"),
                })
        except (httpx.HTTPError, ValueError) as exc:
            error = f"RabbitMQ management API unavailable: {exc}"
        db = (JobTask.objects.exclude(status__in=list(JobTask.TERMINAL)).values("queue", "status")
              .annotate(n=Count("id")))
        by_queue: dict[str, dict] = {}
        for row in db:
            by_queue.setdefault(row["queue"], {})[row["status"]] = row["n"]
        oldest = JobTask.objects.filter(status__in=["pending", "dispatched"]).order_by("created_at").first()
        return Response({"rabbitmq": sorted(rabbit, key=lambda q: q["name"]), "rabbitmq_error": error,
                         "tasks_by_queue": by_queue,
                         "oldest_waiting_seconds": int((timezone.now() - oldest.created_at).total_seconds())
                         if oldest else 0})


class SystemView(APIView):
    permission_classes = admin_permissions("view_system")

    @extend_schema(tags=TAG, responses=schemas.AdminSystemSerializer,
                   summary="Service health, GPUs with their queues, loaded AI model and configuration")
    def get(self, request: Request) -> Response:
        return Response(system.snapshot())


class WorkerView(APIView):
    permission_classes = admin_permissions("view_system")

    @extend_schema(tags=TAG, responses=schemas.WorkerInfoSerializer(many=True),
                   summary="Online workers, their queues, GPUs and current task")
    def get(self, request: Request) -> Response:
        return Response(sorted(live.workers(), key=lambda w: (w.get("hostname", ""), str(w.get("gpu", "")))))


class ModelAdminView(APIView):
    def get_permissions(self):  # type: ignore[no-untyped-def]
        cap = "manage_models" if self.request.method == "PATCH" else "view_queues"
        return [p() for p in admin_permissions(cap)]

    @extend_schema(tags=TAG, responses=schemas.AdminModelSerializer(many=True),
                   summary="Models with overrides and 24h stats")
    def get(self, request: Request) -> Response:
        since = timezone.now() - timedelta(days=1)
        stats = {r["target"]: r for r in JobTask.objects.filter(kind="model", created_at__gte=since)
                 .values("target").annotate(runs=Count("id"), failed=Count("id", filter=Q(status="failed")),
                                            waiting=Count("id", filter=Q(status__in=["pending", "dispatched"])))}
        overrides = {o.model_id: o for o in ModelOverride.objects.all()}
        consumers = {}
        for w in live.workers():
            for q in w.get("queues", []):
                consumers[q] = consumers.get(q, 0) + 1
        out = []
        for spec in registry().models.values():
            o = overrides.get(spec.id)
            out.append({
                "id": spec.id, "name": spec.name("en"), "family": spec.family, "media": sorted(spec.media),
                "enabled": spec.enabled, "weight": spec.weight, "run_on": sorted(spec.runs_on),
                "trial": spec.trial, "gpu_mem_mb": spec.gpu_mem_mb, "queue": spec.queue,
                "consumers": consumers.get(spec.queue, 0), "note": o.note if o else "",
                "stats_24h": stats.get(spec.id, {"runs": 0, "failed": 0, "waiting": 0}),
                "conda_envs": sorted({m.get("conda_env", "") for m in spec.media.values()}),
            })
        return Response(out)

    @extend_schema(tags=TAG, request={"application/json": {"type": "object", "properties": {
        "model_id": {"type": "string"}, "enabled": {"type": "boolean"}, "weight": {"type": "number"},
        "run_on_image": {"type": "boolean"}, "run_on_video": {"type": "boolean"}, "trial": {"type": "boolean"},
        "note": {"type": "string"}}}},
        responses=schemas.OkSerializer)
    def patch(self, request: Request) -> Response:
        model_id = str(request.data.get("model_id", ""))
        spec = registry().get(model_id)
        if spec is None:
            raise ApiError("Unknown model.")
        for media in ("image", "video"):
            if request.data.get(f"run_on_{media}") and not spec.supports(media):
                raise ApiError(f"{spec.name('en')} cannot analyse {media}s.")
        o, _ = ModelOverride.objects.get_or_create(model_id=spec.id)
        fields = ("enabled", "run_on_image", "run_on_video", "trial")
        before = {"weight": o.weight, **{f: getattr(o, f) for f in fields}}
        for field in fields:
            if field in request.data:
                setattr(o, field, bool(request.data[field]))
        if "weight" in request.data:
            weight = float(request.data["weight"])
            if not 0 <= weight <= 10:
                raise ApiError("weight must be between 0 and 10.")
            o.weight = weight
        if "note" in request.data:
            o.note = str(request.data["note"])[:255]
        o.save()
        invalidate_overrides()
        audit.record("admin.model_updated", request=request, target_type="catalog.model", target_id=spec.id,
                     before=before, after={"weight": o.weight, **{f: getattr(o, f) for f in fields}})
        return Response({"ok": True})


class DetectionSetupView(APIView):
    """What every job runs besides the per-media detectors: extra checks and the long-form detector."""

    def get_permissions(self):  # type: ignore[no-untyped-def]
        cap = "manage_models" if self.request.method == "PATCH" else "view_queues"
        return [p() for p in admin_permissions(cap)]

    def _payload(self) -> dict:
        cfg = PlatformSettings.load()
        reg = registry()
        try:
            stream_models, online = streams.available_models(use_cache=False), True
        except streams.StreamServiceUnavailable:
            stream_models, online = [], False
        return {
            "checks": [{"id": a.id, "name": a.name("en"), "description": a.description.get("en", ""),
                        "always": a.builtin, "enabled": a.builtin or a.id in (cfg.audit_steps or [])}
                       for a in reg.audit_steps.values()],
            "long_video": {
                "online": online, "model": cfg.long_video_model, "face_crop": cfg.long_video_face_crop,
                "models": [{"model_id": m["model_id"], "name": m.get("name") or m["model_id"],
                            "available": bool(m.get("available")), "reason": m.get("reason") or "",
                            "face_crop": (m.get("face_crop") or {}).get("support", "none")}
                           for m in stream_models],
            },
        }

    @extend_schema(tags=TAG, responses=schemas.DetectionSetupSerializer,
                   summary="Extra checks run on every job and the long-form video detector")
    def get(self, request: Request) -> Response:
        return Response(self._payload())

    @extend_schema(tags=TAG, request=schemas.DetectionSetupUpdateSerializer, responses=schemas.DetectionSetupSerializer)
    def patch(self, request: Request) -> Response:
        ser = schemas.DetectionSetupUpdateSerializer(data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data
        cfg = PlatformSettings.load()
        before = {"audit_steps": cfg.audit_steps, "long_video_model": cfg.long_video_model,
                  "long_video_face_crop": cfg.long_video_face_crop}
        if "audit_steps" in d:
            reg = registry()
            unknown = [s for s in d["audit_steps"] if s not in reg.audit_steps]
            if unknown:
                raise ApiError(f"Unknown checks: {', '.join(unknown)}")
            cfg.audit_steps = [s for s in dict.fromkeys(d["audit_steps"]) if not reg.audit_steps[s].builtin]
        if "long_video_model" in d:
            if d["long_video_model"]:
                offered = {m["model_id"] for m in streams.available_models(use_cache=False)}
                if d["long_video_model"] not in offered:
                    raise ApiError("The stream service does not offer that detector.")
            cfg.long_video_model = d["long_video_model"]
        if "long_video_face_crop" in d:
            cfg.long_video_face_crop = d["long_video_face_crop"]
        cfg.save()
        after = {"audit_steps": cfg.audit_steps, "long_video_model": cfg.long_video_model,
                 "long_video_face_crop": cfg.long_video_face_crop}
        audit.record("admin.detection_setup", request=request, target_type="core.platformsettings", target_id="1",
                     before=before, after=after)
        return Response(self._payload())


class FailedTaskRetryView(APIView):
    permission_classes = admin_permissions("manage_queues")

    @extend_schema(tags=TAG, request=None, responses=schemas.OkSerializer,
                   summary="Retry a failed task (the job is re-opened)")
    def post(self, request: Request, pk: str) -> Response:
        task = get_object_or_404(JobTask.objects.select_related("job"), pk=pk, status=JobTask.Status.FAILED)
        job = task.job
        if job.status in (Job.Status.EXPIRED, Job.Status.CANCELED):
            raise Conflict("The job is canceled or expired.")
        if job.is_terminal:
            raise Conflict("The job is already settled; ask the user to re-run it instead.")
        task.status = JobTask.Status.PENDING
        task.max_attempts = task.attempt + 1
        task.save(update_fields=["status", "max_attempts", "updated_at"])
        from sml.jobs.tasks import dispatch

        dispatch.delay()
        audit.record("admin.task_retry", request=request, target=task)
        return Response({"ok": True})


# --- pricing / settings ---------------------------------------------------------------------------

class PricingView(APIView):
    def get_permissions(self):  # type: ignore[no-untyped-def]
        cap = "manage_pricing" if self.request.method == "PUT" else "view_billing"
        return [p() for p in admin_permissions(cap)]

    @extend_schema(tags=TAG, responses=schemas.PriceItemSerializer(many=True), summary="Credit prices")
    def get(self, request: Request) -> Response:
        labels = dict(PriceRule.Key.choices)
        return Response([{"key": k, "label": labels.get(k, k), "credits": v}
                         for k, v in pricing.price_table().items()])

    @extend_schema(tags=TAG, request=PriceRuleUpdateSerializer, responses=schemas.PriceItemSerializer(many=True))
    def put(self, request: Request) -> Response:
        ser = PriceRuleUpdateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        before = pricing.price_table()
        for key, value in ser.validated_data["prices"].items():
            PriceRule.objects.update_or_create(key=key, defaults={"credits": value})
        pricing.invalidate()
        audit.record("admin.pricing_updated", request=request, target_type="credits.pricing", before=before,
                     after=pricing.price_table())
        return self.get(request)


class PlatformSettingsView(APIView):
    def get_permissions(self):  # type: ignore[no-untyped-def]
        cap = "manage_settings" if self.request.method == "PATCH" else "view_users"
        return [p() for p in admin_permissions(cap)]

    @extend_schema(tags=TAG, responses=PlatformSettingsSerializer)
    def get(self, request: Request) -> Response:
        return Response(PlatformSettingsSerializer(PlatformSettings.load()).data)

    @extend_schema(tags=TAG, request=PlatformSettingsSerializer, responses=PlatformSettingsSerializer)
    def patch(self, request: Request) -> Response:
        obj, _ = PlatformSettings.objects.get_or_create(pk=1)
        before = PlatformSettingsSerializer(obj).data
        ser = PlatformSettingsSerializer(obj, data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        ser.save()
        audit.record("admin.settings_updated", request=request, target_type="core.platformsettings",
                     target_id="1", before=dict(before), after=dict(ser.data))
        return Response(ser.data)


# --- billing ----------------------------------------------------------------------------------------

class _BillingCrud(viewsets.ModelViewSet):
    http_method_names = ["get", "post", "patch", "delete"]

    def get_permissions(self):  # type: ignore[no-untyped-def]
        cap = "view_billing" if self.request.method == "GET" else "manage_billing"
        return [p() for p in admin_permissions(cap)]

    def perform_create(self, serializer):  # type: ignore[no-untyped-def]
        obj = serializer.save()
        audit.record(f"admin.{obj._meta.model_name}_created", request=self.request, target=obj,
                     after=serializer.data)

    def perform_update(self, serializer):  # type: ignore[no-untyped-def]
        before = type(serializer)(serializer.instance).data
        obj = serializer.save()
        audit.record(f"admin.{obj._meta.model_name}_updated", request=self.request, target=obj,
                     before=dict(before), after=dict(serializer.data))

    def perform_destroy(self, instance):  # type: ignore[no-untyped-def]
        # Products referenced by payments are archived, never deleted.
        instance.active = False
        instance.save(update_fields=["active", "updated_at"])
        audit.record(f"admin.{instance._meta.model_name}_archived", request=self.request, target=instance)


@extend_schema_view(list=extend_schema(tags=TAG), create=extend_schema(tags=TAG),
                    partial_update=extend_schema(tags=TAG), destroy=extend_schema(tags=TAG),
                    retrieve=extend_schema(tags=TAG))
class CreditPackAdminViewSet(_BillingCrud):
    serializer_class = CreditPackAdminSerializer
    queryset = CreditPack.objects.all()
    pagination_class = None


@extend_schema_view(list=extend_schema(tags=TAG), create=extend_schema(tags=TAG),
                    partial_update=extend_schema(tags=TAG), destroy=extend_schema(tags=TAG),
                    retrieve=extend_schema(tags=TAG))
class PlanAdminViewSet(_BillingCrud):
    serializer_class = PlanAdminSerializer
    queryset = Plan.objects.all()
    pagination_class = None


class PaymentFilter(filters.FilterSet):
    status = filters.MultipleChoiceFilter(choices=Payment.Status.choices)
    provider = filters.ChoiceFilter(choices=[("toss", "toss"), ("stripe", "stripe"), ("mock", "mock")])
    user = filters.UUIDFilter(field_name="user_id")
    q = filters.CharFilter(method="search")

    class Meta:
        model = Payment
        fields: list[str] = []

    def search(self, qs, name, value):  # type: ignore[no-untyped-def]
        return qs.filter(Q(order_id__icontains=value) | Q(user__email__icontains=value))


class AdminPaymentListView(generics.ListAPIView):
    serializer_class = PaymentAdminSerializer
    filterset_class = PaymentFilter
    permission_classes = admin_permissions("view_billing")
    queryset = Payment.objects.select_related("user")

    @extend_schema(tags=TAG)
    def get(self, request: Request, *args, **kwargs) -> Response:  # type: ignore[no-untyped-def]
        return super().get(request, *args, **kwargs)


class AdminRefundView(APIView):
    permission_classes = admin_permissions("view_billing")

    @extend_schema(tags=TAG, responses=schemas.RefundQuoteSerializer, summary="Refund quote under the refund policy")
    def get(self, request: Request, pk: str) -> Response:
        payment = get_object_or_404(Payment, pk=pk)
        q = billing.refund_quote(payment, override_full=request.query_params.get("override_full") == "true")
        return Response({"eligible": q.eligible, "amount": q.amount, "credits_to_revoke": q.credits_to_revoke,
                         "reason": q.reason, "currency": payment.currency})

    @extend_schema(tags=TAG, request=RefundRequestSerializer, responses={201: schemas.RefundResultSerializer},
                   summary="Issue a refund")
    def post(self, request: Request, pk: str) -> Response:
        payment = get_object_or_404(Payment, pk=pk)
        ser = RefundRequestSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data
        full_power = has_capability(request.user, "manage_billing")
        if not full_power:
            if not has_capability(request.user, "refund_limited"):
                raise ApiError("You cannot issue refunds.")
            quote = billing.refund_quote(payment, override_full=d["override_full"])
            if min(d.get("amount") or quote.amount, quote.amount) > SUPPORT_REFUND_LIMIT.get(payment.currency, 0):
                raise ApiError("Amount exceeds the support refund limit; ask a billing admin.")
        refund = billing.refund_payment(payment, actor=request.user, reason=d["reason"],
                                        override_full=d["override_full"], amount=d.get("amount"))
        return Response({"refund_id": str(refund.pk), "amount": refund.amount,
                         "credits_revoked": refund.credits_revoked, "status": refund.status},
                        status=status.HTTP_201_CREATED)


class WebhookLogView(generics.ListAPIView):
    serializer_class = WebhookEventSerializer
    permission_classes = admin_permissions("view_billing")
    queryset = WebhookEvent.objects.all()

    pagination_class = ReceivedAtCursor

    @extend_schema(tags=TAG)
    def get(self, request: Request, *args, **kwargs) -> Response:  # type: ignore[no-untyped-def]
        return super().get(request, *args, **kwargs)


# --- audit log / api usage ---------------------------------------------------------------------

class AuditFilter(filters.FilterSet):
    action = filters.CharFilter(lookup_expr="startswith")
    actor = filters.UUIDFilter(field_name="actor_id")
    target_id = filters.CharFilter()
    created_after = filters.IsoDateTimeFilter(field_name="created_at", lookup_expr="gte")
    created_before = filters.IsoDateTimeFilter(field_name="created_at", lookup_expr="lt")

    class Meta:
        model = AuditLog
        fields: list[str] = []


class AuditLogView(generics.ListAPIView):
    serializer_class = AuditLogSerializer
    filterset_class = AuditFilter
    permission_classes = admin_permissions("view_audit_log")
    queryset = AuditLog.objects.all()

    @extend_schema(tags=TAG)
    def get(self, request: Request, *args, **kwargs) -> Response:  # type: ignore[no-untyped-def]
        if request.query_params.get("format") == "csv":
            qs = self.filter_queryset(self.get_queryset())[:50_000]

            class Echo:
                def write(self, v: str) -> str:
                    return v

            writer = csv.writer(Echo())

            def rows():  # type: ignore[no-untyped-def]
                yield writer.writerow(["created_at", "actor", "action", "target_type", "target_id", "ip",
                                       "request_id"])
                for e in qs.iterator():
                    yield writer.writerow([e.created_at.isoformat(), e.actor_label, e.action, e.target_type,
                                           e.target_id, e.ip or "", e.request_id])

            resp = StreamingHttpResponse(rows(), content_type="text/csv")
            resp["Content-Disposition"] = 'attachment; filename="audit-log.csv"'
            return resp
        return super().get(request, *args, **kwargs)


class ApiUsageView(APIView):
    permission_classes = admin_permissions("view_api_usage")

    @extend_schema(tags=TAG, responses=schemas.AdminApiUsageSerializer, summary="API usage per key (last 30 days)")
    def get(self, request: Request) -> Response:
        since = timezone.localdate() - timedelta(days=30)
        rows = (ApiKeyUsageDaily.objects.filter(date__gte=since)
                .values("api_key_id", "api_key__name", "api_key__prefix", "api_key__user__email")
                .annotate(requests=Sum("requests"), errors=Sum("errors"), jobs=Sum("jobs_created"),
                          credits=Sum("credits_spent")).order_by("-requests")[:200])
        return Response({"keys": list(rows), "active_keys": ApiKey.objects.filter(revoked_at__isnull=True).count()})
