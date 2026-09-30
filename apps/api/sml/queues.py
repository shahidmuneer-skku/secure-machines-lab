"""RabbitMQ queue topology shared by the API side and the model workers.

Every queue is a classic queue with x-max-priority=10 (see ADR 0004). Dead
lettering is applied by a RabbitMQ policy (deploy/rabbitmq/definitions.json),
not by queue arguments, so producers and consumers never disagree on arguments.
"""

from __future__ import annotations

from typing import Any

from kombu import Exchange, Queue

QUEUE_ARGS = {"x-max-priority": 10}

DEFAULT = "sml.default"
RESULTS = "sml.results"
REPORTS = "sml.reports"
MAINTENANCE = "sml.maintenance"
NEWS = "sml.news"
REASONING = "sml.reasoning"
AUDIT_PREFIX = "sml.audit."
MODEL_PREFIX = "sml.model."
LONG_VIDEO_PREFIX = "sml.longvideo."

# Celery task names implemented by the Django-free worker package (apps/worker).
WORKER_TASK = "sml_worker.run_task"
# Celery task names implemented by the API side and called by workers.
RESULT_TASK = "sml.jobs.record_task_event"
EXPLAIN_RESULT_TASK = "sml.jobs.record_explanation_event"


def _q(name: str) -> Queue:
    return Queue(name, Exchange(name, type="direct"), routing_key=name, queue_arguments=QUEUE_ARGS)


def all_queue_names(raw_registry: dict[str, Any]) -> list[str]:
    names = [DEFAULT, RESULTS, REPORTS, MAINTENANCE, NEWS, REASONING]
    names += [MODEL_PREFIX + m["id"] for m in raw_registry.get("models", [])]
    names += [AUDIT_PREFIX + s["id"] for s in raw_registry.get("audit_steps", [])]
    names += [LONG_VIDEO_PREFIX + m["id"] for m in raw_registry.get("long_video_models", [])]
    return names


def build_queues(raw_registry: dict[str, Any]) -> list[Queue]:
    return [_q(n) for n in all_queue_names(raw_registry)]
