"""Shared pytest fixtures.

Tests run against the PostgreSQL from `docker compose` (row locks and advisory locks are part of
what is being tested). Redis and RabbitMQ are not needed: events go to memory and publishing a task
to the broker is replaced by the `published` fixture.
"""

from __future__ import annotations

import io
import itertools
import time
from collections.abc import Callable
from typing import Any

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from PIL import Image
from rest_framework.test import APIClient

PASSWORD = "Correct-Horse-Battery-2026!"
_emails = itertools.count(1)


@pytest.fixture(scope="session")
def django_db_setup(django_db_setup, django_db_blocker):  # type: ignore[no-untyped-def]
    """Seed roles, prices, packs and plans once for the whole session."""
    with django_db_blocker.unblock():
        call_command("bootstrap", verbosity=0)


@pytest.fixture(autouse=True)
def _isolate(settings) -> None:  # type: ignore[no-untyped-def]
    from django.core.cache import cache

    from sml.core.events import memory_events

    cache.clear()
    memory_events.clear()


@pytest.fixture(autouse=True)
def published(monkeypatch: pytest.MonkeyPatch) -> list[Any]:
    """Tasks the dispatcher would have sent to RabbitMQ."""
    sent: list[Any] = []
    monkeypatch.setattr("sml.jobs.dispatcher._publish", lambda tasks: sent.extend(tasks))
    return sent


@pytest.fixture
def platform(db):  # type: ignore[no-untyped-def]
    """Platform settings with deterministic credit defaults (no daily grant unless a test enables it)."""
    from sml.core.models import PlatformSettings

    cfg = PlatformSettings.load()
    cfg.daily_free_credits = 0
    cfg.save()
    return cfg


@pytest.fixture
def make_user(db, platform) -> Callable[..., Any]:  # type: ignore[no-untyped-def]
    from allauth.account.models import EmailAddress
    from django.contrib.auth.models import Group

    from sml.accounts.models import User
    from sml.accounts.rbac import sync_staff_flag

    def make(email: str | None = None, *, roles: tuple[str, ...] | None = None, verified: bool = True,
             **extra: Any) -> User:
        email = email or f"user{next(_emails)}@example.com"
        user = User.objects.create_user(email=email, password=PASSWORD, **extra)
        if roles is not None:
            user.groups.set(Group.objects.filter(name__in=roles))
            sync_staff_flag(user)
        EmailAddress.objects.create(user=user, email=email, verified=verified, primary=True)
        return user

    return make


@pytest.fixture
def user(make_user):  # type: ignore[no-untyped-def]
    return make_user()


@pytest.fixture
def client_for() -> Callable[..., APIClient]:
    def make(user: Any = None, *, mfa: bool = False) -> APIClient:
        client = APIClient()
        if user is not None:
            client.force_login(user)
            if mfa:
                session = client.session
                session["account_authentication_methods"] = [
                    {"method": "password", "at": time.time()},
                    {"method": "mfa", "type": "totp", "at": time.time()},
                ]
                session.save()
        return client

    return make


@pytest.fixture
def api(client_for, user) -> APIClient:  # type: ignore[no-untyped-def]
    return client_for(user)


def png_bytes(size: tuple[int, int] = (64, 64), color: tuple[int, int, int] = (40, 120, 200)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, "PNG")
    return buf.getvalue()


@pytest.fixture
def png_upload() -> Callable[..., SimpleUploadedFile]:
    def make(name: str = "photo.png") -> SimpleUploadedFile:
        return SimpleUploadedFile(name, png_bytes(), content_type="image/png")

    return make


@pytest.fixture
def make_media(db) -> Callable[..., Any]:  # type: ignore[no-untyped-def]
    """A READY media object owned by `owner` (goes through the real ingest/validation path)."""
    from sml.media import services as media_services

    def make(owner: Any = None, *, name: str = "photo.png", guest_token: str = "") -> Any:
        upload = SimpleUploadedFile(name, png_bytes(), content_type="image/png")
        kwargs: dict[str, Any] = {"original_name": name, "owner": owner}
        if guest_token:
            kwargs["guest_token"] = guest_token
        return media_services.ingest_file(upload, **kwargs)

    return make


@pytest.fixture
def use_detectors(db) -> Callable[..., list[str]]:  # type: ignore[no-untyped-def]
    """Set what every job of a media type runs, as an admin would on Admin → Models."""
    from sml.catalog.models import ModelOverride
    from sml.catalog.registry import invalidate_overrides, registry

    def configure(ids: list[str], media_type: str = "image") -> list[str]:
        for spec in registry().models.values():
            if spec.supports(media_type):
                ModelOverride.objects.update_or_create(model_id=spec.id,
                                                       defaults={f"run_on_{media_type}": spec.id in ids})
        invalidate_overrides()
        return ids

    return configure


@pytest.fixture
def run_job(user, make_media, use_detectors, platform) -> Callable[..., Any]:  # type: ignore[no-untyped-def]
    """Runs one image job for `user`; `outcomes` maps detector id → fake probability, or "no_face", and
    optionally "metadata" → the metadata check's `ai_indicators`."""
    from sml.credits import services as credits
    from sml.credits.models import CreditSource, LedgerKind
    from sml.jobs import services
    from sml.jobs.dispatcher import dispatch_pending
    from sml.jobs.models import JobTask
    from sml.jobs.results import record_task_event

    platform.free_max_inflight_tasks = 20
    platform.save()

    def run(outcomes: dict[str, float | str]) -> Any:
        use_detectors([k for k in outcomes if k != "metadata"])
        credits.grant(user, 5, source=CreditSource.PURCHASE, kind=LedgerKind.PURCHASE)
        job = services.create_job(user, services.JobRequest(media=make_media(user)))
        dispatch_pending()
        for task in job.tasks.all():
            record_task_event({"event": "started", "task_id": str(task.pk), "attempt": 1})
            outcome = outcomes.get(task.target)
            if task.kind == JobTask.Kind.AUDIT:
                result = {"ai_indicators": outcome} if isinstance(outcome, dict) else {}
            else:
                result = {"no_face": True} if outcome == "no_face" else {"fake_prob": outcome}
            record_task_event({"event": "finished", "status": "succeeded", "task_id": str(task.pk), "attempt": 1,
                               "result": result})
        job.refresh_from_db()
        return job

    return run


@pytest.fixture
def show_heatmaps(db) -> Callable[..., list[str]]:  # type: ignore[no-untyped-def]
    """Choose whose heatmaps users see, as an admin would on Admin → Models."""
    from sml.catalog.models import ModelOverride
    from sml.catalog.registry import invalidate_overrides, registry

    def configure(ids: list[str]) -> list[str]:
        for spec in registry().models.values():
            ModelOverride.objects.update_or_create(model_id=spec.id, defaults={"show_heatmap": spec.id in ids})
        invalidate_overrides()
        return ids

    return configure


@pytest.fixture
def worker() -> Any:
    """Plays the model worker: reports task events the way sml_worker does."""
    from sml.jobs.results import record_task_event

    class FakeWorker:
        def start(self, task: Any) -> None:
            task.refresh_from_db()
            record_task_event({"event": "started", "task_id": str(task.pk), "attempt": task.attempt,
                               "worker": "test@host", "gpu": "0"})

        def succeed(self, task: Any, result: dict[str, Any] | None = None) -> None:
            task.refresh_from_db()
            record_task_event({"event": "finished", "status": "succeeded", "task_id": str(task.pk),
                               "attempt": task.attempt, "duration_ms": 1200, "result": result or {}})

        def fail(self, task: Any, code: str = "RUNTIME_ERROR", message: str = "boom") -> None:
            task.refresh_from_db()
            record_task_event({"event": "finished", "status": "failed", "task_id": str(task.pk),
                               "attempt": task.attempt, "error_code": code, "error_message": message})

    return FakeWorker()
