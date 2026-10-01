"""User dashboard: KPIs and chart series computed in the database."""

from __future__ import annotations

from datetime import timedelta

from django.db.models import Avg, Count, DurationField, ExpressionWrapper, F, Sum
from django.db.models.functions import TruncDate
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from sml import api_schemas as schemas
from sml.apikeys.models import ApiKeyUsageDaily
from sml.credits.models import LedgerEntry, LedgerKind
from sml.credits.services import get_balance
from sml.jobs.models import Job, JobTask
from sml.jobs.serializers import JobListSerializer


class DashboardSummaryView(APIView):
    @extend_schema(tags=["account"], responses=schemas.DashboardSummarySerializer,
                   summary="Dashboard KPIs and chart data (last N days, default 30)")
    def get(self, request: Request) -> Response:
        user = request.user
        days = min(max(int(request.query_params.get("days", 30)), 7), 365)
        since = timezone.now() - timedelta(days=days)
        jobs = Job.objects.filter(user=user, deleted_at__isnull=True)
        period = jobs.filter(created_at__gte=since)
        done = period.filter(status=Job.Status.SUCCEEDED)
        verdicts = dict(done.values_list("verdict").annotate(n=Count("id")))
        scored = verdicts.get(Job.Verdict.FAKE, 0) + verdicts.get(Job.Verdict.REAL, 0)
        turnaround = done.exclude(started_at=None).annotate(
            d=ExpressionWrapper(F("finished_at") - F("created_at"), output_field=DurationField())
        ).aggregate(avg=Avg("d"))["avg"]
        balance = get_balance(user)

        by_day = {}
        for row in (period.annotate(day=TruncDate("created_at")).values("day", "verdict").annotate(n=Count("id"))):
            entry = by_day.setdefault(row["day"].isoformat(), {"date": row["day"].isoformat(), "fake": 0, "real": 0,
                                                                "other": 0})
            key = row["verdict"] if row["verdict"] in ("fake", "real") else "other"
            entry[key] += row["n"]

        usage: dict[str, int] = {}
        for row in period.values("kind", "media_type").annotate(n=Count("id")):
            key = row["media_type"] if row["kind"] == Job.Kind.DETECT and row["media_type"] else row["kind"]
            usage[key] = usage.get(key, 0) + row["n"]

        credit_rows = (LedgerEntry.objects.filter(wallet__user=user, created_at__gte=since)
                       .annotate(day=TruncDate("created_at")).values("day", "kind").annotate(total=Sum("delta")))
        credits_by_day: dict[str, dict] = {}
        for row in credit_rows:
            entry = credits_by_day.setdefault(row["day"].isoformat(), {"date": row["day"].isoformat(), "spent": 0,
                                                                        "added": 0})
            if row["kind"] in (LedgerKind.RESERVE, LedgerKind.RELEASE, LedgerKind.ADMIN_DEDUCT):
                entry["spent"] -= row["total"]
            elif row["kind"] in (LedgerKind.PURCHASE, LedgerKind.SUBSCRIPTION_GRANT, LedgerKind.SIGNUP_BONUS,
                                 LedgerKind.DAILY_GRANT, LedgerKind.PROMO, LedgerKind.ADMIN_GRANT):
                entry["added"] += row["total"]

        waits = (JobTask.objects.filter(job__user=user, created_at__gte=since, started_at__isnull=False)
                 .annotate(day=TruncDate("created_at"),
                           w=ExpressionWrapper(F("started_at") - F("created_at"), output_field=DurationField()))
                 .values("day").annotate(avg=Avg("w")).order_by("day"))
        api = ApiKeyUsageDaily.objects.filter(api_key__user=user, date__gte=since.date()).aggregate(
            requests=Sum("requests"), jobs=Sum("jobs_created"), credits=Sum("credits_spent"))
        recent = jobs.select_related("media").prefetch_related("tasks")[:6]
        return Response({
            "kpis": {
                "balance": balance.balance, "held": balance.held, "unlimited": balance.unlimited,
                "low_balance": not balance.unlimited and balance.balance < 10,
                "jobs_in_period": period.count(),
                "fake_rate": round(verdicts.get(Job.Verdict.FAKE, 0) / scored, 4) if scored else None,
                "avg_turnaround_seconds": int(turnaround.total_seconds()) if turnaround else None,
                "in_queue": jobs.filter(status__in=[Job.Status.QUEUED, Job.Status.RUNNING]).count(),
                "credits_spent": sum(v["spent"] for v in credits_by_day.values()),
            },
            "jobs_by_day": sorted(by_day.values(), key=lambda r: r["date"]),
            "usage_by_type": [{"type": k, "jobs": v} for k, v in sorted(usage.items(), key=lambda kv: -kv[1])],
            "credits_by_day": sorted(credits_by_day.values(), key=lambda r: r["date"]),
            "queue_wait_by_day": [{"date": w["day"].isoformat(), "avg_seconds": int(w["avg"].total_seconds())}
                                  for w in waits if w["avg"] is not None],
            "api_usage": {k: v or 0 for k, v in api.items()},
            "recent_jobs": JobListSerializer(recent, many=True, context={"request": request}).data,
        })
