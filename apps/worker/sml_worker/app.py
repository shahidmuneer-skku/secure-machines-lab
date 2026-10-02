"""Celery app for model workers. Declares queues identically to the API (x-max-priority=10)."""

from __future__ import annotations

import logging
from typing import Any

from celery import Celery
from celery.exceptions import Reject
from celery.signals import worker_process_init, worker_shutdown
from kombu import Exchange, Queue

from .config import config
from .registry import queue_names

logger = logging.getLogger(__name__)
QUEUE_ARGS = {"x-max-priority": 10}

app = Celery("sml_worker", broker=config().broker_url)
app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    task_queue_max_priority=10,
    broker_connection_retry_on_startup=True,
    worker_hijack_root_logger=False,
    result_backend=None,
    task_ignore_result=True,
    broker_transport_options={"confirm_publish": True},
)
_all = [*queue_names(), "sml.results"]
app.conf.task_queues = [Queue(n, Exchange(n, type="direct"), routing_key=n, queue_arguments=QUEUE_ARGS)
                        for n in _all]


@app.task(name="sml_worker.run_task", bind=True, acks_late=True)
def run_task(self: Any, envelope: dict[str, Any]) -> None:
    from .runner import run_envelope

    try:
        run_envelope(app, envelope)
    except (SystemExit, KeyboardInterrupt) as exc:
        # A restart (deploy, systemctl) signals the pool processes too; Celery would record that as a
        # failed task and acknowledge the message, losing it. Hand it back to the queue instead.
        logger.warning("Worker shutting down; requeueing task %s", envelope.get("task_id"))
        raise Reject(exc, requeue=True) from exc


@worker_process_init.connect
def _init(**_: Any) -> None:
    import faulthandler
    import signal

    from .runner import ensure_scratch

    faulthandler.register(signal.SIGUSR2, all_threads=True)  # `kill -USR2 <pid>`: stacks to the log
    ensure_scratch()


@worker_shutdown.connect
def _shutdown(**_: Any) -> None:
    logger.info("sml worker shutting down")
