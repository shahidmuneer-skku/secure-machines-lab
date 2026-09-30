"""Server-Sent Events: live job progress, timeline events and credit updates.

GET /api/v1/events/stream           signed-in user (session cookie or API key)
GET /api/v1/trial/jobs/<id>/stream  guest trial job (trial cookie)
Runs under ASGI; each connection holds one Redis pub/sub subscription.
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncIterator

import redis.asyncio as aioredis
from asgiref.sync import sync_to_async
from django.conf import settings
from django.http import HttpRequest, HttpResponse, JsonResponse, StreamingHttpResponse

from sml.core.events import JOB_CHANNEL, USER_CHANNEL

logger = logging.getLogger(__name__)
HEARTBEAT_SECONDS = 15
MAX_CONNECTION_SECONDS = 60 * 60


def _unauthorized() -> HttpResponse:
    return JsonResponse({"type": "about:blank", "title": "Authentication required", "status": 401,
                         "code": "NOT_AUTHENTICATED", "detail": "Sign in or send an API key."},
                        status=401, content_type="application/problem+json")


async def _stream(channel: str) -> AsyncIterator[str]:
    client = aioredis.from_url(settings.REDIS_URL)
    pubsub = client.pubsub()
    await pubsub.subscribe(channel)
    loop = asyncio.get_running_loop()
    started = loop.time()
    try:
        yield "retry: 5000\n\n"
        yield "event: ready\ndata: {}\n\n"
        while loop.time() - started < MAX_CONNECTION_SECONDS:
            message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=HEARTBEAT_SECONDS)
            if message is None:
                yield ": keep-alive\n\n"
                continue
            try:
                payload = json.loads(message["data"])
                event_type = str(payload.get("type", "message"))
            except (ValueError, TypeError):
                continue
            yield f"event: {event_type}\ndata: {json.dumps(payload, separators=(',', ':'))}\n\n"
    except asyncio.CancelledError:
        raise
    finally:
        try:
            await pubsub.unsubscribe(channel)
            await pubsub.aclose()
            await client.aclose()
        except Exception:  # noqa: BLE001
            logger.debug("SSE cleanup failed", exc_info=True)


def _response(channel: str) -> StreamingHttpResponse:
    resp = StreamingHttpResponse(_stream(channel), content_type="text/event-stream")
    resp["Cache-Control"] = "no-cache, no-transform"
    resp["X-Accel-Buffering"] = "no"
    return resp


async def user_event_stream(request: HttpRequest) -> HttpResponse:
    user = await request.auser()
    if not user.is_authenticated:
        header = request.headers.get("Authorization", "")
        if header.startswith("Bearer sml_"):
            from sml.apikeys.services import verify

            key = await sync_to_async(verify)(header.split(" ", 1)[1])
            if key is None or not key.has_scope("jobs:read"):
                return _unauthorized()
            user_id = key.user_id
        else:
            return _unauthorized()
    else:
        user_id = user.pk
    return _response(USER_CHANNEL.format(user_id))


async def trial_job_event_stream(request: HttpRequest, pk: str) -> HttpResponse:
    from sml.trial.views import guest_token_from

    token = guest_token_from(request)
    if not token:
        return _unauthorized()
    from .models import Job

    exists = await Job.objects.filter(pk=pk, guest_token=token).aexists()
    if not exists:
        return JsonResponse({"status": 404, "code": "NOT_FOUND", "title": "Not found"}, status=404)
    return _response(JOB_CHANNEL.format(pk))
