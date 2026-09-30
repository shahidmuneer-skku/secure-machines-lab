"""Celery app for the API side (orchestration, results, reports, maintenance)."""

from __future__ import annotations

import os
from pathlib import Path

import yaml
from celery import Celery
from celery.schedules import crontab

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "sml.settings.dev")

app = Celery("sml")
app.config_from_object("django.conf:settings", namespace="CELERY")


def _configure_queues() -> None:
    from django.conf import settings

    from sml import queues

    raw = yaml.safe_load(Path(settings.MODELS_CONFIG_PATH).read_text())
    app.conf.task_queues = queues.build_queues(raw)
    app.conf.task_default_queue = queues.DEFAULT
    app.conf.task_default_exchange = queues.DEFAULT
    app.conf.task_default_routing_key = queues.DEFAULT
    app.conf.task_queue_max_priority = 10
    app.conf.task_default_priority = 4
    app.conf.task_routes = {
        "sml.jobs.record_task_event": {"queue": queues.RESULTS},
        "sml.jobs.record_explanation_event": {"queue": queues.RESULTS},
        "sml.jobs.dispatch": {"queue": queues.DEFAULT},
        "sml.reports.*": {"queue": queues.REPORTS},
        "sml.maintenance.*": {"queue": queues.MAINTENANCE},
    }


app.on_after_configure.connect(lambda **_: _configure_queues(), weak=False)
app.autodiscover_tasks()

app.conf.beat_schedule = {
    "dispatch-sweep": {"task": "sml.jobs.dispatch", "schedule": 5.0},
    "requeue-stale-dispatches": {"task": "sml.maintenance.requeue_stale", "schedule": 60.0},
    "expire-credits": {"task": "sml.maintenance.expire_credits", "schedule": crontab(minute="*/15")},
    "release-stale-holds": {"task": "sml.maintenance.release_stale_holds", "schedule": crontab(minute=10, hour="*/6")},
    "purge-expired-media": {"task": "sml.maintenance.purge_expired", "schedule": crontab(minute=20)},
    "renew-toss-subscriptions": {"task": "sml.maintenance.renew_subscriptions", "schedule": crontab(minute="*/30")},
    "prune-logs": {"task": "sml.maintenance.prune_logs", "schedule": crontab(minute=40, hour=3)},
    "audit-ledgers": {"task": "sml.maintenance.audit_ledgers", "schedule": crontab(minute=10, hour=4)},
}
