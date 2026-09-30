"""Job lifecycle: reserve → dispatch → worker events → one verdict → charge or refund."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest

from sml.catalog.registry import registry
from sml.core.exceptions import Conflict, InsufficientCredits
from sml.credits import services as credits
from sml.credits.models import CreditHold, CreditSource, LedgerKind
from sml.jobs import services
from sml.jobs.dispatcher import dispatch_pending
from sml.jobs.models import Job, JobEvent, JobTask

pytestmark = pytest.mark.django_db


def fund(user, amount: int = 20) -> None:  # type: ignore[no-untyped-def]
    credits.grant(user, amount, source=CreditSource.PURCHASE, kind=LedgerKind.PURCHASE)


def image_models(n: int = 2) -> list[str]:
    """Enabled image models without automatic fallbacks, so outcomes are easy to reason about."""
    ids = [m.id for m in registry().enabled_for("image") if not (m.fallbacks or {})]
    assert len(ids) >= n, "config/models.yaml needs at least two plain image models"
    return ids[:n]


def run(job: Job, worker: Any, outcome: Callable[[JobTask], dict | None]) -> Job:
    """Dispatch and play every task until the job settles. outcome() → result dict, or None to fail."""
    for _ in range(10):
        dispatch_pending()
        active = list(job.tasks.filter(status=JobTask.Status.DISPATCHED))
        if not active:
            break
        for task in active:
            worker.start(task)
            result = outcome(task)
            if result is None:
                worker.fail(task)
            else:
                worker.succeed(task, result)
    job.refresh_from_db()
    return job


def model_score(scores: dict[str, float]) -> Callable[[JobTask], dict]:
    def outcome(task: JobTask) -> dict:
        if task.kind == JobTask.Kind.AUDIT:
            return {"ai_indicators": {}}
        return {"fake_prob": scores[task.target]}

    return outcome


@pytest.fixture
def job_for(make_media) -> Callable[..., Job]:  # type: ignore[no-untyped-def]
    def make(user, models: list[str] | None = None) -> Job:  # type: ignore[no-untyped-def]
        media = make_media(user)
        return services.create_job(user, services.JobRequest(media=media, models=models or image_models()))

    return make


def test_created_job_reserves_quote_and_queues_one_task_per_model(user, job_for):
    fund(user, 5)
    job = job_for(user)
    assert job.status == Job.Status.QUEUED
    assert job.credits_quoted == 1
    assert job.hold.status == CreditHold.Status.HELD
    assert credits.get_balance(user).balance == 4
    kinds = sorted((t.kind, t.target) for t in job.tasks.all())
    assert kinds == sorted([(JobTask.Kind.AUDIT, "metadata")] + [(JobTask.Kind.MODEL, m) for m in image_models()])
    assert JobEvent.objects.filter(job=job, code="job.queued").exists()


def test_dispatch_publishes_tasks_with_attempt_numbers(user, job_for, published,
                                                       django_capture_on_commit_callbacks):
    fund(user)
    job = job_for(user)
    with django_capture_on_commit_callbacks(execute=True):
        assert dispatch_pending() == 3
    assert {t.pk for t in published} == set(job.tasks.values_list("pk", flat=True))
    assert set(job.tasks.values_list("status", "attempt")) == {(JobTask.Status.DISPATCHED, 1)}
    assert dispatch_pending() == 0  # nothing is sent twice


def test_successful_job_gets_one_combined_verdict_and_is_charged(user, job_for, worker):
    fund(user, 5)
    a, b = image_models()
    job = run(job_for(user), worker, model_score({a: 0.9, b: 0.7}))
    assert job.status == Job.Status.SUCCEEDED
    assert job.verdict == Job.Verdict.FAKE
    assert 0.7 <= job.fake_probability <= 0.9
    assert {m["model"] for m in job.summary["models"]} == {a, b}
    assert job.hold.status == CreditHold.Status.CAPTURED
    assert job.credits_charged == 1
    assert credits.get_balance(user).balance == 4
    assert credits.verify_wallet(credits.ensure_wallet(user))


def test_real_verdict_below_threshold(user, job_for, worker):
    fund(user)
    a, b = image_models()
    job = run(job_for(user), worker, model_score({a: 0.1, b: 0.2}))
    assert job.verdict == Job.Verdict.REAL


def test_metadata_ai_indicator_overrides_the_models(user, job_for, worker):
    fund(user)
    a, b = image_models()

    def outcome(task: JobTask) -> dict:
        if task.kind == JobTask.Kind.AUDIT:
            return {"ai_indicators": {"ai_generated": True, "evidence": [{"source": "c2pa", "value": "DALL·E"}]}}
        return {"fake_prob": 0.05}

    job = run(job_for(user), worker, outcome)
    assert job.verdict == Job.Verdict.FAKE
    assert {r["code"] for r in job.verdict_reasons} == {"model_consensus", "metadata_ai_indicator"}
    del a, b


def test_no_face_everywhere_is_not_charged(user, job_for, worker):
    fund(user, 5)

    def outcome(task: JobTask) -> dict:
        return {"ai_indicators": {}} if task.kind == JobTask.Kind.AUDIT else {"no_face": True}

    job = run(job_for(user), worker, outcome)
    assert job.status == Job.Status.SUCCEEDED
    assert job.verdict == Job.Verdict.NO_FACE
    assert job.hold.status == CreditHold.Status.RELEASED
    assert credits.get_balance(user).balance == 5


def test_failed_models_are_retried_once_then_refunded(user, job_for, worker, published):
    fund(user, 5)
    job = run(job_for(user), worker, lambda t: {"ai_indicators": {}} if t.kind == JobTask.Kind.AUDIT else None)
    models = job.tasks.filter(kind=JobTask.Kind.MODEL)
    assert set(models.values_list("status", "attempt")) == {(JobTask.Status.FAILED, 2)}
    assert job.status == Job.Status.FAILED
    assert job.error_code == "ANALYSIS_FAILED"
    assert credits.get_balance(user).balance == 5
    assert JobEvent.objects.filter(job=job, code="task.retry").count() == 2


def test_one_failed_model_still_gives_a_partial_charged_result(user, job_for, worker):
    fund(user, 5)
    a, _ = image_models()

    def outcome(task: JobTask) -> dict | None:
        if task.kind == JobTask.Kind.AUDIT:
            return {"ai_indicators": {}}
        return {"fake_prob": 0.8} if task.target == a else None

    job = run(job_for(user), worker, outcome)
    assert job.status == Job.Status.SUCCEEDED and job.partial
    assert credits.get_balance(user).balance == 4


def test_stale_events_from_an_old_attempt_are_ignored(user, job_for, worker):
    fund(user)
    job = job_for(user)
    dispatch_pending()
    task = job.tasks.filter(kind=JobTask.Kind.MODEL).first()
    from sml.jobs.results import record_task_event

    record_task_event({"event": "finished", "status": "succeeded", "task_id": str(task.pk), "attempt": 7,
                       "result": {"fake_prob": 1.0}})
    task.refresh_from_db()
    assert task.status == JobTask.Status.DISPATCHED


def test_scores_in_percent_are_normalized(user, job_for, worker):
    fund(user)
    a, b = image_models()
    job = run(job_for(user), worker, model_score({a: 80.0, b: 60.0}))
    probs = sorted(m["fake_prob"] for m in job.summary["models"])
    assert probs == [0.6, 0.8]


def test_cancel_before_start_refunds_everything(user, job_for):
    fund(user, 5)
    job = services.cancel_job(job_for(user))
    assert job.status == Job.Status.CANCELED
    assert credits.get_balance(user).balance == 5
    with pytest.raises(Conflict):
        services.cancel_job(job)


def test_not_enough_credits_creates_no_job(user, make_media):
    media = make_media(user)
    with pytest.raises(InsufficientCredits):
        services.create_job(user, services.JobRequest(media=media, models=image_models()))
    assert not Job.objects.exists()


def test_dispatcher_respects_the_per_user_in_flight_cap(user, job_for, platform):
    platform.free_max_inflight_tasks = 4
    platform.save()
    fund(user)
    for _ in range(3):
        job_for(user)  # 3 jobs x 3 tasks
    assert dispatch_pending() == 4
    assert JobTask.objects.filter(status=JobTask.Status.DISPATCHED).count() == 4


def test_higher_priority_users_are_dispatched_first(make_user, job_for, platform):
    platform.free_max_inflight_tasks = 50
    platform.save()
    low, high = make_user(), make_user()
    fund(low)
    fund(high)
    job_for(low)
    job_for(high)
    JobTask.objects.filter(job__user=high).update(priority=9)
    from sml.jobs import dispatcher

    dispatcher.BATCH_LIMIT, old = 3, dispatcher.BATCH_LIMIT
    try:
        dispatch_pending()
    finally:
        dispatcher.BATCH_LIMIT = old
    assert set(JobTask.objects.filter(status=JobTask.Status.DISPATCHED).values_list("job__user", flat=True)) == {
        high.pk}


def test_rerun_creates_a_new_charged_job(user, job_for, worker):
    fund(user, 5)
    a, b = image_models()
    first = run(job_for(user), worker, model_score({a: 0.9, b: 0.9}))
    second = services.rerun_job(first, user=user)
    assert second.parent_id == first.pk and second.run_number == 2
    assert credits.get_balance(user).balance == 3


def test_tasks_never_picked_up_fail_and_refund(user, job_for, settings):
    from datetime import timedelta

    from django.utils import timezone

    from sml.jobs.tasks import requeue_stale

    fund(user, 5)
    job = job_for(user)
    dispatch_pending()
    assert credits.get_balance(user).balance == 4
    JobTask.objects.filter(job=job).update(dispatched_at=timezone.now() - timedelta(hours=settings.STALE_DISPATCH_HOURS,
                                                                                     minutes=1))
    assert requeue_stale() == 3
    job.refresh_from_db()
    assert job.status == Job.Status.FAILED
    assert set(job.tasks.values_list("error_code", flat=True)) == {"QUEUE_TIMEOUT"}
    assert credits.get_balance(user).balance == 5


def test_recently_dispatched_tasks_are_left_alone(user, job_for):
    from sml.jobs.tasks import requeue_stale

    fund(user)
    job = job_for(user)
    dispatch_pending()
    assert requeue_stale() == 0
    assert set(job.tasks.values_list("status", flat=True)) == {JobTask.Status.DISPATCHED}
