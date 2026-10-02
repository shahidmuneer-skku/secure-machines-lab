"""The chat assistant (owner, 2026-10-02): conversations, streamed replies, analyses at the normal price,
results summaries — and the model never learns or tells how the analysis works."""

from __future__ import annotations

import json
from typing import Any

import pytest

from sml.assistant import llm, prompts
from sml.assistant.models import Conversation, Message
from sml.catalog.registry import registry
from sml.credits import pricing
from sml.credits import services as credits
from sml.credits.models import CreditSource, LedgerKind, PriceRule
from sml.jobs.dispatcher import dispatch_pending
from sml.jobs.models import Job, JobTask
from sml.jobs.results import record_task_event

pytestmark = [
    pytest.mark.django_db,
    # The sync test client reads the (async) event stream itself; production serves it over ASGI.
    pytest.mark.filterwarnings("ignore:StreamingHttpResponse must consume asynchronous iterators"),
]

STRONG = {"ai_generated": True, "confidence": "strong",
          "evidence": [{"source": "C2PA", "strength": "strong", "detail": "Content Credentials declare AI"}],
          "exief": {"status": "ok", "verdict": "confirmed", "score": 108, "untrustworthy": [], "signals": []}}
METHOD_WORDS = ("metadata", "c2pa", "exif", "content credentials", "provenance", "detector", "faces_found", "exief")


@pytest.fixture
def model(monkeypatch):  # type: ignore[no-untyped-def]
    """A stand-in for Ollama: records what it is sent and streams a scripted answer."""
    calls: list[list[dict[str, Any]]] = []
    script = {"chunks": ["The photo shows a man in a suit. ", "Its EXIF data names an AI tool. ",
                         "The result reads likely manipulated."]}

    async def fake(messages):  # type: ignore[no-untyped-def]
        calls.append(messages)
        for chunk in script["chunks"]:
            yield chunk

    monkeypatch.setattr(llm, "chat_stream", fake)
    return {"calls": calls, "script": script}


@pytest.fixture
def detectors(use_detectors):  # type: ignore[no-untyped-def]
    return use_detectors([m.id for m in registry().enabled_for("image") if not m.fallbacks][:2])


def events(response) -> list[tuple[str, dict[str, Any]]]:  # type: ignore[no-untyped-def]
    assert response["Content-Type"].startswith("text/event-stream")
    # proxies must pass it through uncompressed, or the events arrive only when the reply ends
    assert "no-transform" in response["Cache-Control"] and response["X-Accel-Buffering"] == "no"
    body = b"".join(response).decode()
    out = []
    for block in body.strip().split("\n\n"):
        if block.startswith(":"):  # a comment (keep-alive)
            out.append(("comment", {"text": block[1:].strip()}))
            continue
        lines = dict(line.split(": ", 1) for line in block.split("\n"))
        out.append((lines["event"], json.loads(lines["data"])))
    return out


def send(api, url: str, body: dict[str, Any]):  # type: ignore[no-untyped-def]
    """POSTs as the browser does: asking for an event stream."""
    return api.post(url, body, format="json", HTTP_ACCEPT="text/event-stream")


def conversation(api) -> str:  # type: ignore[no-untyped-def]
    res = api.post("/api/v1/assistant/conversations", {}, format="json")
    assert res.status_code == 201, res.content
    return res.json()["id"]


def finish(job: Job, indicators: dict[str, Any] | None = None, prob: float = 0.9) -> None:
    dispatch_pending()
    for task in job.tasks.all():
        record_task_event({"event": "started", "task_id": str(task.pk), "attempt": 1})
    for task in job.tasks.all():
        result = {"ai_indicators": indicators or {}} if task.kind == JobTask.Kind.AUDIT else {"fake_prob": prob}
        record_task_event({"event": "finished", "status": "succeeded", "task_id": str(task.pk), "attempt": 1,
                           "result": result, "artifacts": []})


# --- conversations -------------------------------------------------------------------------------

def test_conversations_are_listed_once_they_have_a_message_and_stay_private(api, client_for, make_user, model):
    cid = conversation(api)
    assert api.get("/api/v1/assistant/conversations").json()["results"] == []
    events(api.post(f"/api/v1/assistant/conversations/{cid}/messages", {"content": "What is a deepfake?"},
                    format="json"))
    listed = api.get("/api/v1/assistant/conversations").json()["results"]
    assert [c["id"] for c in listed] == [cid] and listed[0]["title"] == "What is a deepfake?"
    renamed = api.patch(f"/api/v1/assistant/conversations/{cid}", {"title": "Basics"}, format="json")
    assert renamed.json()["title"] == "Basics"
    other = client_for(make_user())
    assert other.get(f"/api/v1/assistant/conversations/{cid}").status_code == 404
    assert other.post(f"/api/v1/assistant/conversations/{cid}/messages", {"content": "hi"},
                      format="json").status_code == 404
    assert api.delete(f"/api/v1/assistant/conversations/{cid}").status_code == 204
    assert not Conversation.objects.filter(pk=cid).exists()


def test_without_the_capability_there_is_no_assistant(client_for, make_user):
    nobody = client_for(make_user(roles=()))
    assert nobody.post("/api/v1/assistant/conversations", {}, format="json").status_code == 403


# --- replies ---------------------------------------------------------------------------------------

def test_a_reply_streams_sentence_by_sentence_and_never_tells_the_method(api, model):
    cid = conversation(api)
    stream = events(send(api, f"/api/v1/assistant/conversations/{cid}/messages", {"content": "Is this photo real?"}))
    kinds = [k for k, _ in stream]
    assert kinds[0] == "meta" and kinds[-1] == "done" and "delta" in kinds
    said = "".join(d["text"] for k, d in stream if k == "delta")
    assert "EXIF" not in said and "man in a suit" in said and "likely manipulated" in said
    stored = Message.objects.get(pk=stream[-1][1]["message"]["id"])
    assert stored.role == Message.Role.ASSISTANT and "EXIF" not in stored.content
    detail = api.get(f"/api/v1/assistant/conversations/{cid}").json()
    assert [m["role"] for m in detail["messages"]] == ["user", "assistant"]
    # What the model is told: its rules, and nothing about how the analysis works.
    system = model["calls"][0][0]
    assert system["role"] == "system" and "Strictly confidential" in system["content"]
    assert "(none yet)" in system["content"]


def test_attached_files_are_analysed_at_the_normal_price(api, user, make_media, detectors, model):
    credits.grant(user, 5, source=CreditSource.PURCHASE, kind=LedgerKind.PURCHASE)
    before = credits.get_balance(user).balance
    media = [make_media(user, name="a.png"), make_media(user, name="b.png")]
    cid = conversation(api)
    stream = events(api.post(f"/api/v1/assistant/conversations/{cid}/messages",
                             {"content": "Check these", "media_ids": [str(m.pk) for m in media]}, format="json"))
    jobs = stream[0][1]["user_message"]["jobs"]
    assert len(jobs) == 2 and {j["title"] for j in jobs} == {"a.png", "b.png"}
    assert credits.get_balance(user).balance == before - 2  # one image costs one credit; chatting is free
    # The model saw the images and knew they were being analysed.
    user_turn = model["calls"][0][-1]
    assert user_turn["role"] == "user" and len(user_turn["images"]) == 2
    assert "analysis in progress" in model["calls"][0][0]["content"]


def test_without_enough_credits_nothing_is_sent(api, user, make_media, detectors, model):
    media = make_media(user)
    cid = conversation(api)
    res = send(api, f"/api/v1/assistant/conversations/{cid}/messages", {"content": "x", "media_ids": [str(media.pk)]})
    # asked for an event stream, answered with JSON problem details (not 406)
    assert res.status_code == 402 and res.json()["code"] == "INSUFFICIENT_CREDITS"
    assert not Message.objects.filter(conversation_id=cid).exists() and not model["calls"]


def test_the_results_are_explained_once_and_without_the_method(api, user, make_media, detectors, model):
    credits.grant(user, 5, source=CreditSource.PURCHASE, kind=LedgerKind.PURCHASE)
    media = make_media(user)
    cid = conversation(api)
    sent = events(api.post(f"/api/v1/assistant/conversations/{cid}/messages",
                           {"content": "Is it real?", "media_ids": [str(media.pk)]}, format="json"))
    message_id = sent[0][1]["user_message"]["id"]
    url = f"/api/v1/assistant/conversations/{cid}/messages/{message_id}/results"
    assert api.post(url, {}, format="json").status_code == 409  # still running
    finish(Job.objects.get(pk=sent[0][1]["user_message"]["jobs"][0]["id"]), indicators=STRONG)
    summary = events(send(api, url, {}))
    assert summary[-1][0] == "done" and summary[-1][1]["message"]["jobs"][0]["verdict"] == "fake"
    system = model["calls"][-1][0]["content"].lower()
    files = system.split("files in this conversation")[-1]
    assert "likely ai-generated" in files and "90%" in files
    assert not any(w in files for w in METHOD_WORDS)
    assert api.post(url, {}, format="json").status_code == 409  # written once
    assert str(Message.objects.get(pk=message_id).results_reply_id) == summary[-1][1]["message"]["id"]


def test_when_the_model_is_unavailable_the_user_is_told_and_nothing_is_stored(api, monkeypatch):
    async def down(messages):  # type: ignore[no-untyped-def]
        raise llm.AssistantUnavailable("connection refused")
        yield ""  # pragma: no cover - makes this an async generator

    monkeypatch.setattr(llm, "chat_stream", down)
    cid = conversation(api)
    stream = events(api.post(f"/api/v1/assistant/conversations/{cid}/messages", {"content": "hi"}, format="json"))
    assert stream[-1][0] == "error" and stream[-1][1]["code"] == "ASSISTANT_UNAVAILABLE"
    assert list(Message.objects.filter(conversation_id=cid).values_list("role", flat=True)) == ["user"]


def test_an_earlier_result_can_be_discussed_without_analysing_it_again(api, user, make_media, detectors, model):
    from sml.jobs import services as job_services

    credits.grant(user, 5, source=CreditSource.PURCHASE, kind=LedgerKind.PURCHASE)
    job = job_services.create_job(user, job_services.JobRequest(media=make_media(user, name="old.png")))
    finish(job)
    balance, jobs = credits.get_balance(user).balance, Job.objects.count()
    cid = conversation(api)
    stream = events(api.post(f"/api/v1/assistant/conversations/{cid}/messages",
                             {"content": "Explain this result", "job_ids": [str(job.pk)]}, format="json"))
    assert stream[-1][0] == "done"
    assert (credits.get_balance(user).balance, Job.objects.count()) == (balance, jobs)  # nothing new, no charge
    sent = stream[0][1]["user_message"]
    assert sent["started_analyses"] is False and [j["id"] for j in sent["jobs"]] == [str(job.pk)]
    system = model["calls"][0][0]["content"]
    assert "old.png (image): verdict: Likely manipulated" in system
    # each analysis says what its probability measures (it is never a probability of authenticity)
    assert "face-swap analysis: Likely manipulated, probability of a face swap 90%" in system
    # no automatic summary for an earlier result: the reply above is the explanation
    url = f"/api/v1/assistant/conversations/{cid}/messages/{sent['id']}/results"
    assert api.post(url, {}, format="json").status_code == 400
    # someone else's result cannot be brought in
    other = job_services.create_job(user, job_services.JobRequest(media=make_media(user)))
    Job.objects.filter(pk=other.pk).update(user=None)
    res = api.post(f"/api/v1/assistant/conversations/{cid}/messages", {"job_ids": [str(other.pk)]}, format="json")
    assert res.status_code == 400



def test_a_reply_that_only_talks_about_the_method_is_replaced_by_a_short_note(api, model):
    model["script"]["chunks"] = ["The detectors read the EXIF data and the C2PA manifest. ",
                                 "Then the face-swap detector ensemble votes."]
    cid = conversation(api)
    stream = events(send(api, f"/api/v1/assistant/conversations/{cid}/messages",
                         {"content": "Wie funktioniert die Analyse?", "locale": "de"}))
    said = "".join(d["text"] for k, d in stream if k == "delta")
    assert stream[-1][0] == "done" and said == prompts.WITHHELD["de"]
    assert stream[-1][1]["message"]["content"] == prompts.WITHHELD["de"]


def test_the_model_knows_the_prices_the_admins_set(api, model):
    PriceRule.objects.update_or_create(key=PriceRule.Key.IMAGE, defaults={"credits": 7})
    pricing.invalidate()
    cid = conversation(api)
    events(send(api, f"/api/v1/assistant/conversations/{cid}/messages", {"content": "How much is an image?"}))
    assert "Image analysis: 7 per image" in model["calls"][0][0]["content"]


def test_a_silent_model_does_not_let_the_stream_go_quiet(api, monkeypatch):
    import asyncio

    from sml.assistant import services

    async def busy(messages):  # type: ignore[no-untyped-def]
        await asyncio.sleep(0.3)  # e.g. waiting behind another request
        yield "Here is the answer."

    monkeypatch.setattr(llm, "chat_stream", busy)
    monkeypatch.setattr(services, "HEARTBEAT_SECONDS", 0.05)
    cid = conversation(api)
    stream = events(send(api, f"/api/v1/assistant/conversations/{cid}/messages", {"content": "hi"}))
    kinds = [k for k, _ in stream]
    assert kinds[0] == "meta" and "comment" in kinds and kinds[-1] == "done"
    assert kinds.index("comment") < kinds.index("delta")
    assert stream[-1][1]["message"]["content"] == "Here is the answer."
