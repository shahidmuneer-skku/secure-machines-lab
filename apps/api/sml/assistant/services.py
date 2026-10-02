"""What the assistant does: conversations, messages, the analyses they start, and what the model knows.

The model is told only what users see of a result — file name and type, status, verdict label,
overall probability, the result of each analysis, a plain "no face found" note — and it may look at
the images themselves. It is never told which detectors ran, what a file's metadata showed or which
checks ran (owner, 2026-10-02); its answer is filtered all the same (sml.core.confidential).
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any

from asgiref.sync import sync_to_async
from django.db import transaction
from django.db.models import Count, QuerySet
from django.utils import timezone

from sml.catalog.access import assert_module_allowed
from sml.core.confidential import StreamGuard, drop_empty_sections, scrub
from sml.core.exceptions import ApiError, Conflict
from sml.core.models import PlatformSettings
from sml.credits import pricing
from sml.jobs import public
from sml.jobs import services as job_services
from sml.jobs.models import Job
from sml.media import storage
from sml.media.models import MediaObject

from . import llm, prompts
from .models import Conversation, Message

logger = logging.getLogger(__name__)

HISTORY_LIMIT = 24
MAX_CONTENT = 4000
MAX_FILES = 10
TITLE_LENGTH = 60
UNAVAILABLE = "The assistant is not available right now. Please try again shortly."
# While the model is silent (it serves one request at a time), a comment keeps proxies from closing the stream.
HEARTBEAT_SECONDS = 15.0
# Each analysis as users see it: its name, what its probability measures, and its verdict labels.
ANALYSES = {
    "face_swap": ("face-swap analysis", "probability of a face swap", "Likely manipulated"),
    "ai_generated": ("AI-generation analysis", "probability of AI generation", "Likely AI-generated"),
}
VERDICT_LABELS = {"real": "Likely authentic", "inconclusive": "Inconclusive", "no_face": "No face detected"}


# --- conversations ------------------------------------------------------------------------------

def conversations_for(user: Any) -> QuerySet[Conversation]:
    """The user's conversations that have at least one message, newest first."""
    return (Conversation.objects.filter(user=user).annotate(message_count=Count("messages"))
            .filter(message_count__gt=0).order_by("-updated_at"))


def _title(content: str, media: list[MediaObject]) -> str:
    text = " ".join(content.split())
    if text:
        return text if len(text) <= TITLE_LENGTH else text[: TITLE_LENGTH - 1].rstrip() + "…"
    if media:
        more = f" +{len(media) - 1}" if len(media) > 1 else ""
        return f"{media[0].original_name}{more}"[:TITLE_LENGTH]
    return ""


# --- what the model knows ------------------------------------------------------------------------

def _pct(value: float | None) -> str:
    return "—" if value is None else f"{value * 100:.0f}%"


def analysis_line(job: Job) -> str:
    """One file's state as users see it (sml.jobs.public); never the method."""
    head = f"- {job.title} ({job.media_type or 'file'}): "
    if job.status in (Job.Status.QUEUED, Job.Status.RUNNING):
        return head + f"analysis in progress ({job.progress:.0f}%)"
    if job.status == Job.Status.CANCELED:
        return head + "the analysis was canceled"
    if job.status == Job.Status.EXPIRED:
        return head + "the file and its results were deleted after the retention period"
    if job.status in (Job.Status.FAILED, Job.Status.EXPIRED) or job.status != Job.Status.SUCCEEDED:
        return head + "the analysis could not be completed (not charged)"
    if job.verdict == Job.Verdict.NO_FACE:
        parts = ["no face was found, so face swapping could not be assessed"]
    else:
        label = "Likely AI-generated" if public.ai_generated(job) else job.get_verdict_display()
        parts = [f"verdict: {label}", f"overall probability of manipulation: {_pct(job.fake_probability)}"]
    for a in public.analyses(job):
        name, measures, fake_label = ANALYSES.get(a["id"], ANALYSES["ai_generated"])
        if a.get("status") == "no_face":
            parts.append(f"{name}: no face found")
        elif a.get("fake_probability") is None:
            parts.append(f"{name}: not completed")
        else:
            verdict = (fake_label if a.get("verdict") == "fake"
                       else VERDICT_LABELS.get(str(a.get("verdict")), "Inconclusive"))
            parts.append(f"{name}: {verdict}, {measures} {_pct(a.get('fake_probability'))}")
    if job.partial:
        parts.append("part of the analysis could not be completed")
    return head + "; ".join(parts)


def _files(conversation: Conversation) -> str:
    jobs = Job.objects.filter(assistant_messages__conversation=conversation).distinct().order_by("created_at")
    lines = [analysis_line(j) for j in jobs]
    return "\n".join(lines) if lines else prompts.NO_FILES


def _attachment_note(message: Message) -> str:
    names = [f"{m.original_name} ({m.media_type})" for m in message.media.all()]
    return f"\n[Attached: {', '.join(names)}]" if names else ""


def _history(conversation: Conversation, *, until: Message | None = None) -> list[dict[str, Any]]:
    qs = conversation.messages.exclude(status=Message.Status.FAILED).prefetch_related("media")
    if until is not None:
        qs = qs.filter(created_at__lte=until.created_at)
    recent = list(qs.order_by("-created_at")[:HISTORY_LIMIT])[::-1]
    out = []
    for m in recent:
        content = m.content if m.role == Message.Role.USER else scrub(m.content)
        if m.role == Message.Role.USER:
            content += _attachment_note(m)
        if content.strip():
            out.append({"role": m.role, "content": content})
    return out


def _images(media: list[MediaObject]) -> list[str]:
    """The files themselves (videos: their preview frame), small enough for the model."""
    images: list[str] = []
    for m in media:
        key = m.storage_key if m.media_type == MediaObject.MediaType.IMAGE else m.thumbnail_key
        if not key:
            continue
        try:
            with storage.open_file(key) as fh:
                encoded = llm.image_b64(fh.read())
        except Exception:  # a missing file is simply not shown to the model
            logger.warning("Could not read %s for the assistant", key, exc_info=True)
            continue
        if encoded:
            images.append(encoded)
        if len(images) >= llm.MAX_IMAGES:
            break
    return images


def _prices() -> str:
    """The prices the admins set (credits.pricing), so answers about cost are exact."""
    p = {k: (str(v) if v else "free") for k, v in pricing.price_table().items()}
    text = prompts.PRICES.format(
        image=p["image"], video_base=p["video_base"], video_minutes=max(1, pricing.price("video_base_seconds") // 60),
        video_extra=p["video_per_extra_minute"], long_video=p["long_video_per_minute"], news=p["news_case"],
        explain=p["explain"], report_pdf=p["report_pdf"], report_hwp=p["report_hwp"], report_csv=p["report_csv"],
        studio_generate=p["studio_generate"], studio_edit=p["studio_edit"])
    daily = PlatformSettings.load().daily_free_credits
    return text + ("\n" + prompts.DAILY_FREE.format(daily=daily) if daily else "")


def _system(conversation: Conversation, locale: str) -> dict[str, Any]:
    text = prompts.SYSTEM.replace("{language}", prompts.LANG_NAMES.get(locale, "English"))
    text = text.replace("{prices}", _prices())
    return {"role": "system", "content": text.replace("{files}", _files(conversation))}


# --- sending ---------------------------------------------------------------------------------------

@dataclass
class Turn:
    """Everything a reply needs, prepared synchronously before the model is called."""

    conversation: Conversation
    user_message: Message | None
    messages: list[dict[str, Any]]
    jobs: list[Job] = field(default_factory=list)
    results_for: Message | None = None
    locale: str = "en"


def send(user: Any, conversation: Conversation, content: str, media_ids: list[str], locale: str,
         job_ids: list[str] | None = None) -> Turn:
    """A user message. Attached files are analysed (normal price per file); `job_ids` brings the user's
    earlier results into the conversation without analysing anything again."""
    content = (content or "").strip()
    job_ids = job_ids or []
    if not content and not media_ids and not job_ids:
        raise ApiError("Write a message or attach a file.")
    if len(content) > MAX_CONTENT:
        raise ApiError(f"Messages are limited to {MAX_CONTENT} characters.")
    if len(media_ids) + len(job_ids) > MAX_FILES:
        raise ApiError(f"Attach at most {MAX_FILES} files per message.")
    assert_module_allowed(user, "assistant")
    earlier = list(Job.objects.filter(user=user, kind=Job.Kind.DETECT, pk__in=job_ids).select_related("media"))
    if len(earlier) != len(set(map(str, job_ids))):
        raise ApiError("Unknown result.")
    media: list[MediaObject] = []
    if media_ids:
        assert_module_allowed(user, "detect")
        found = {str(m.pk): m for m in MediaObject.objects.filter(owner=user, pk__in=media_ids,
                                                                  status=MediaObject.Status.READY)}
        missing = [str(i) for i in media_ids if str(i) not in found]
        if missing:
            raise ApiError(f"Unknown media: {', '.join(missing)}", extra={"media_ids": missing})
        media = [found[str(i)] for i in media_ids]
    with transaction.atomic():
        # Each file is analysed like any detection, at the normal price (owner: chatting is free).
        reqs = [job_services.JobRequest(media=m, locale=locale) for m in media]
        if len(reqs) == 1:
            jobs = [job_services.create_job(user, reqs[0], source=Job.Source.WEB)]
        elif reqs:
            jobs = job_services.create_batch(user, reqs, source=Job.Source.WEB, name=_title(content, media))[1]
        else:
            jobs = []
        message = Message.objects.create(conversation=conversation, role=Message.Role.USER, content=content,
                                         started_analyses=bool(jobs))
        message.media.set(media)
        message.jobs.set([*jobs, *earlier])
        if not conversation.title:
            conversation.title = _title(content, media)
        conversation.updated_at = timezone.now()
        conversation.save(update_fields=["title", "updated_at"])
    history = _history(conversation, until=message)
    if history and history[-1]["role"] == "user":
        images = _images([*media, *[j.media for j in earlier if j.media and not j.purged_at]])
        if images:
            history[-1]["images"] = images
    return Turn(conversation, message, [_system(conversation, locale), *history], jobs=jobs, locale=locale)


def prepare_results(user: Any, conversation: Conversation, message: Message, locale: str) -> Turn:
    """The assistant's summary once every analysis a message started has finished (written once)."""
    assert_module_allowed(user, "assistant")
    jobs = list(message.jobs.all())
    if message.role != Message.Role.USER or not message.started_analyses:
        raise ApiError("This message did not start an analysis.")
    if message.results_reply_id:
        raise Conflict("The results of this message have been summarised already.")
    if not all(j.is_terminal for j in jobs):
        raise Conflict("The analysis is still running.")
    history = _history(conversation)
    turn: dict[str, Any] = {"role": "user", "content": prompts.RESULTS_REQUEST}
    images = _images(list(message.media.all()))
    if images:
        turn["images"] = images
    return Turn(conversation, None, [_system(conversation, locale), *history, turn], jobs=jobs, results_for=message,
                locale=locale)


# --- the reply ---------------------------------------------------------------------------------------

def record_reply(turn: Turn, text: str, status: str) -> Message | None:
    with transaction.atomic():
        if turn.results_for is not None:
            # Two windows may ask at once: only the first summary is kept.
            source = Message.objects.select_for_update().get(pk=turn.results_for.pk)
            if source.results_reply_id:
                return None
        reply = Message.objects.create(conversation=turn.conversation, role=Message.Role.ASSISTANT,
                                       content=scrub(text).strip(), status=status)
        if turn.results_for is not None:
            reply.jobs.set(turn.jobs)
            source.results_reply = reply
            source.save(update_fields=["results_reply", "updated_at"])
        Conversation.objects.filter(pk=turn.conversation.pk).update(updated_at=timezone.now())
    return reply


async def _heartbeats(source: AsyncIterator[str], every: float) -> AsyncIterator[str | None]:
    """The source's items, and None each time it has been silent for `every` seconds. The pending read
    is never cancelled by the wait, only when the stream ends early."""
    it = aiter(source)
    pending: asyncio.Future[str] | None = None
    try:
        while True:
            pending = pending or asyncio.ensure_future(anext(it))
            done, _ = await asyncio.wait({pending}, timeout=every)
            if not done:
                yield None
                continue
            finished, pending = pending, None
            try:
                item = finished.result()
            except StopAsyncIteration:
                return
            yield item
    finally:
        if pending is not None:
            pending.cancel()
            with contextlib.suppress(BaseException):
                await pending


def sse(event: str, data: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False, default=str)}\n\n"


async def stream_reply(turn: Turn, meta: dict[str, Any], serialize: Any) -> AsyncIterator[str]:
    """Server-Sent Events: `meta`, then `delta` text as it is written (sentence by sentence, filtered),
    then `done` with the stored message — or `error`. Stopping (closing the request) keeps what was said."""
    yield sse("meta", meta)
    guard = StreamGuard()
    parts: list[str] = []
    status = Message.Status.COMPLETE
    error: str | None = None
    try:
        async for chunk in _heartbeats(llm.chat_stream(turn.messages), HEARTBEAT_SECONDS):
            if chunk is None:
                yield ": keep-alive\n\n"
                continue
            for safe in guard.feed(chunk):
                parts.append(safe)
                yield sse("delta", {"text": safe})
        for safe in guard.flush():
            parts.append(safe)
            yield sse("delta", {"text": safe})
    except llm.AssistantUnavailable:
        logger.warning("Assistant reply failed", exc_info=True)
        status, error = Message.Status.FAILED, UNAVAILABLE
    except (asyncio.CancelledError, GeneratorExit):
        if parts:
            await sync_to_async(record_reply)(turn, "".join(parts), Message.Status.STOPPED)
        raise
    text = "".join(parts)
    if guard.dropped:
        logger.info("Assistant reply: %d sentence(s) about the method withheld", guard.dropped)
        text = drop_empty_sections(text)
    if not text.strip():
        if error or not guard.dropped:  # nothing was said: nothing is stored
            yield sse("error", {"code": "ASSISTANT_UNAVAILABLE", "detail": error or UNAVAILABLE})
            return
        # Every sentence touched on the method: say so rather than show an empty reply.
        text = prompts.WITHHELD.get(turn.locale, prompts.WITHHELD["en"])
        yield sse("delta", {"text": text})
    reply = await sync_to_async(record_reply)(turn, text, status)
    if reply is None:
        yield sse("error", {"code": "CONFLICT", "detail": "The results have been summarised already."})
        return
    yield sse("done", {"message": await sync_to_async(serialize)(reply)})
