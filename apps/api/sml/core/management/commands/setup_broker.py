"""Idempotently applies RabbitMQ topology that queue declarations don't cover:
the dead-letter exchange, the dead-letter queue, and the policy routing
rejected/expired messages from every sml.* queue into it.

The policy also raises the delivery-acknowledgement timeout. Workers acknowledge a task when it
ends (acks_late), and a detector can run for an hour or wait for GPU memory before that; past
RabbitMQ's default 30 minutes the broker closes the worker's channel and re-queues every message
it holds, so finished work runs again.
"""

from urllib.parse import quote

import httpx
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

POLICY = {
    "pattern": r"^sml\.(model|audit|longvideo|news|reasoning|results|reports|default|maintenance)",
    "apply-to": "queues",
    "priority": 0,
    "definition": {"dead-letter-exchange": "sml.dlx", "message-ttl": 86_400_000, "consumer-timeout": 86_400_000},
}


class Command(BaseCommand):
    help = "Declare the dead-letter exchange/queue and policy in RabbitMQ (management API)"

    def handle(self, *args, **options):  # type: ignore[no-untyped-def]
        vhost = quote(settings.RABBITMQ_VHOST, safe="")
        base = settings.RABBITMQ_MANAGEMENT_URL.rstrip("/") + "/api"
        auth = (settings.RABBITMQ_MANAGEMENT_USER, settings.RABBITMQ_MANAGEMENT_PASSWORD)
        calls = [
            ("put", f"{base}/exchanges/{vhost}/sml.dlx", {"type": "fanout", "durable": True}),
            ("put", f"{base}/queues/{vhost}/sml.dead", {"durable": True, "arguments": {}}),
            ("post", f"{base}/bindings/{vhost}/e/sml.dlx/q/sml.dead", {"routing_key": ""}),
            ("put", f"{base}/policies/{vhost}/sml-dead-letter", POLICY),
        ]
        with httpx.Client(auth=auth, timeout=10) as client:
            for method, url, body in calls:
                resp = client.request(method, url, json=body)
                if resp.status_code >= 400:
                    raise CommandError(f"{method.upper()} {url} → {resp.status_code}: {resp.text[:200]}")
        self.stdout.write(self.style.SUCCESS("RabbitMQ dead-letter topology applied"))
