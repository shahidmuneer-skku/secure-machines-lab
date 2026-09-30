from __future__ import annotations

import hashlib
import ipaddress
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.db.models import F
from django.utils import timezone

from sml.catalog.registry import registry
from sml.core.exceptions import InvalidMedia, TrialExhausted
from sml.core.models import PlatformSettings
from sml.credits import pricing
from sml.credits.services import business_today
from sml.jobs import services as job_services
from sml.jobs.models import Job
from sml.media.models import MediaObject

from .models import TrialUsage

IP_MULTIPLIER = 3  # households/offices share an IP


def ip_fingerprint(ip: str | None) -> str:
    """Hash of the /24 (IPv4) or /48 (IPv6) network: coarse, not personally identifying on its own."""
    if not ip:
        return "unknown"
    addr = ipaddress.ip_address(ip)
    prefix = 24 if addr.version == 4 else 48
    net = ipaddress.ip_network(f"{ip}/{prefix}", strict=False)
    return hashlib.sha256(f"{settings.SECRET_KEY}:{net}".encode()).hexdigest()[:32]


def remaining(device: str, ip: str | None) -> int:
    cfg = PlatformSettings.load()
    if not cfg.guest_trial_enabled:
        return 0
    today = business_today()
    used_device = TrialUsage.objects.filter(kind="device", identifier=device, date=today).values_list(
        "count", flat=True).first() or 0
    used_ip = TrialUsage.objects.filter(kind="ip", identifier=ip_fingerprint(ip), date=today).values_list(
        "count", flat=True).first() or 0
    limit = cfg.guest_trial_images_per_day
    return max(0, min(limit - used_device, limit * IP_MULTIPLIER - used_ip))


def _consume(device: str, ip: str | None) -> None:
    today = business_today()
    for kind, ident in (("device", device), ("ip", ip_fingerprint(ip))):
        row, _ = TrialUsage.objects.select_for_update().get_or_create(kind=kind, identifier=ident, date=today)
        TrialUsage.objects.filter(pk=row.pk).update(count=F("count") + 1)


def create_trial_job(media: MediaObject, *, device: str, ip: str | None, locale: str) -> Job:
    if media.media_type != "image":
        raise InvalidMedia("The free trial supports images only. Create a free account to analyze videos.")
    with transaction.atomic():
        if remaining(device, ip) <= 0:
            raise TrialExhausted()
        _consume(device, ip)
        cfg = PlatformSettings.load()
        reg = registry()
        models = [m for m in (cfg.guest_trial_models or reg.trial_selection()) if reg.get(m) and reg.get(m).enabled]
        if not models:
            models = reg.default_selection("image")[:3]
        req = job_services.JobRequest(media=media, models=models, locale=locale)
        prepared = job_services.PreparedJob(req, models, list(job_services.ALWAYS_AUDIT), pricing.Quote())
        job = job_services._create_job(None, prepared, source=Job.Source.TRIAL, guest_token=device)
        job.expires_at = timezone.now() + timedelta(days=1)
        job.save(update_fields=["expires_at"])
        job_services._after_commit_dispatch()
    return job
