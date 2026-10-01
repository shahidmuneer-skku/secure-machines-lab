"""What users see of a job: the verdict and its evidence, never how the analysis works.

The owner's rule: users (web and API) are not told which detectors run, how many, or how they
work. They get the combined verdict and probability, the metadata / C2PA evidence, the results of
the admin's extra checks, unlabelled heatmaps, a combined video timeline, and a progress view in
generic steps. Operators see everything through the admin endpoints (serializers.Admin*).

Each function here builds a plain dict from a job and its prefetched tasks/artifacts/events.
"""

from __future__ import annotations

from collections import defaultdict
from pathlib import PurePosixPath
from typing import Any

from sml.catalog.registry import registry
from sml.core.models import PlatformSettings

from .models import Artifact, Job, JobTask
from .timeline import public_data

ANALYSIS_KINDS = (JobTask.Kind.MODEL, JobTask.Kind.LONG_VIDEO)
PUBLIC_ARTIFACT_KINDS = {Artifact.Kind.XAI: "heatmap", Artifact.Kind.FACE: "face", Artifact.Kind.VIDEO: "video"}
PUBLIC_OPTIONS = ("stream", "interval_seconds", "start_sec", "end_sec", "whole_video")
TIMELINE_POINTS = 200


# --- progress ----------------------------------------------------------------------------------

def _step_status(tasks: list[JobTask]) -> str:
    if not tasks:
        return "skipped"
    if any(t.status == JobTask.Status.RUNNING for t in tasks):
        return "running"
    if all(t.is_terminal for t in tasks):
        if all(t.status in (JobTask.Status.FAILED, JobTask.Status.CANCELED) for t in tasks):
            return "failed" if any(t.status == JobTask.Status.FAILED for t in tasks) else "canceled"
        return "done"
    return "running" if any(t.is_terminal for t in tasks) else "pending"


def _step_progress(tasks: list[JobTask], live: dict[str, dict[str, Any]]) -> float:
    if not tasks:
        return 0.0
    total = 0.0
    for t in tasks:
        if t.is_terminal:
            total += 100.0
        elif t.status == JobTask.Status.RUNNING:
            try:
                total += float((live.get(str(t.pk)) or {}).get("progress", t.progress))
            except (TypeError, ValueError):
                total += t.progress
    return round(total / len(tasks), 1)


def steps(job: Job, tasks: list[JobTask], live: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    """Generic stages: queued → checks → analysis (→ verification for news) → results."""
    checks = [t for t in tasks if t.kind == JobTask.Kind.AUDIT]
    analysis = [t for t in tasks if t.kind in ANALYSIS_KINDS]
    news = [t for t in tasks if t.kind == JobTask.Kind.NEWS]
    started = any(t.started_at for t in tasks) or job.is_terminal
    if job.status == Job.Status.CANCELED and not started:
        queued_status = "canceled"
    else:
        queued_status = "done" if started else "running"
    out = [{"id": "queued", "status": queued_status, "progress": 100.0 if started else 0.0}]
    if checks:
        out.append({"id": "checks", "status": _step_status(checks), "progress": _step_progress(checks, live)})
    if analysis:
        out.append({"id": "analysis", "status": _step_status(analysis), "progress": _step_progress(analysis, live)})
    if news:
        out.append({"id": "verification", "status": _step_status(news), "progress": _step_progress(news, live)})
    if job.status == Job.Status.SUCCEEDED:
        results = "done"
    elif job.status in (Job.Status.FAILED, Job.Status.CANCELED, Job.Status.EXPIRED):
        results = job.status
    else:
        results = "running" if tasks and all(t.is_terminal for t in tasks) else "pending"
    out.append({"id": "results", "status": results, "progress": 100.0 if results == "done" else 0.0})
    return out


def queue(info: dict[str, Any] | None) -> dict[str, Any] | None:
    if not info:
        return None
    return {"position": info.get("position", 0), "eta_seconds": info.get("eta_seconds", 0),
            "workers_online": bool(info.get("workers_online"))}


# --- results -----------------------------------------------------------------------------------

def reasons(job: Job) -> list[dict[str, Any]]:
    out = []
    for r in job.verdict_reasons or []:
        code = r.get("code")
        if code == "model_consensus":
            out.append({"code": "analysis", "fake_probability": r.get("fake_probability")})
        elif code == "metadata_ai_indicator":
            out.append({"code": code, "strength": r.get("strength") or "strong",
                        "evidence": evidence_items(r.get("evidence"))})
        elif code == "stopped_early":
            out.append({"code": code, "analysed_seconds": r.get("analysed_seconds"),
                        "range_seconds": r.get("range_seconds")})
        elif code == "news_agent":
            out.append({"code": code, "status": r.get("status"), "reasoning": r.get("reasoning", "")})
        elif code == "no_face":
            out.append({"code": code})
    return out


def ai_generated(job: Job) -> bool:
    """A fake verdict backed by a confirmed generator declaration in the metadata (EXIEF). Jobs
    finished before EXIEF counted any metadata reason they carry."""
    return job.verdict == Job.Verdict.FAKE and any(
        r.get("code") == "metadata_ai_indicator" and (r.get("strength") == "strong" or "exief_verdict" not in r)
        for r in job.verdict_reasons or [])


# Detector family → the name of the result users see.
ANALYSIS_IDS = {"deepfake": "face_swap", "ai_generated": "ai_generated"}


def analyses(job: Job) -> list[dict[str, Any]]:
    """The result of each analysis (face swap, AI generation): verdict and probability only.

    Jobs from before 2026-10-01 may also hold a "general" group; it is not shown any more."""
    return [{"id": ANALYSIS_IDS[g["group"]], "status": g.get("status", "done"),
             "verdict": g.get("verdict") or "", "fake_probability": g.get("fake_probability")}
            for g in (job.summary or {}).get("groups") or [] if g.get("group") in ANALYSIS_IDS]


def evidence_items(items: Any) -> list[dict[str, str]]:
    return [{"source": str(e.get("source", "")), "detail": str(e.get("detail", "")),
             "strength": str(e.get("strength", ""))}
            for e in (items or []) if isinstance(e, dict)]


def _task(tasks: list[JobTask], kind: str, target: str | None = None) -> JobTask | None:
    return next((t for t in tasks if t.kind == kind and (target is None or t.target == target)), None)


def provenance(tasks: list[JobTask]) -> dict[str, Any] | None:
    """Metadata / EXIF / C2PA findings (the user's own file; no detector involved)."""
    meta = _task(tasks, JobTask.Kind.AUDIT, "metadata")
    if meta is None or meta.status != JobTask.Status.SUCCEEDED:
        return None
    ind = (meta.result or {}).get("ai_indicators") or {}
    return {"ai_generated": bool(ind.get("ai_generated")), "confidence": str(ind.get("confidence") or "none"),
            "c2pa_status": str(ind.get("c2pa_status") or "none"), "camera": ind.get("camera") or None,
            "software": ind.get("software") or None, "evidence": evidence_items(ind.get("evidence")),
            "notes": [str(n) for n in ind.get("notes") or []]}


def _check_result(task: JobTask) -> dict[str, Any]:
    r = task.result or {}
    data = r.get("data") if isinstance(r.get("data"), dict) else {}
    if task.target == "face":
        return {"faces_found": not r.get("no_face")}
    if task.target == "safety":
        predicted = str(data.get("predicted", "")).upper()
        return {"sensitive_content": predicted == "NSFW"}
    if task.target == "fas":
        labels = [str(x.get("label", "")).upper() for x in data.get("fas_results") or [] if isinstance(x, dict)]
        return {"spoof_detected": any(lb in ("FAKE", "SPOOF") for lb in labels)}
    return {}


def checks(tasks: list[JobTask]) -> list[dict[str, Any]]:
    """The admin's extra checks: what they found, in plain terms."""
    out = []
    for t in tasks:
        if t.kind != JobTask.Kind.AUDIT or t.target == "metadata":
            continue
        status = {JobTask.Status.SUCCEEDED: "done", JobTask.Status.RUNNING: "running",
                  JobTask.Status.FAILED: "failed", JobTask.Status.CANCELED: "canceled",
                  JobTask.Status.SKIPPED: "skipped"}.get(t.status, "pending")
        out.append({"id": t.target, "status": status, "result": _check_result(t) if status == "done" else {}})
    return out


def timeline(job: Job, tasks: list[JobTask]) -> list[dict[str, Any]]:
    """Fake probability over time for videos, one series per analysis (detectors combined within each,
    weighted like the verdict)."""
    reg = registry()
    long_task = _task(tasks, JobTask.Kind.LONG_VIDEO)
    if long_task is not None:
        spec = reg.get(long_task.target)
        group = ANALYSIS_IDS.get(spec.family if spec else "", "ai_generated")
        return [{"analysis": group, "start_sec": float(i.get("start_sec") or 0.0),
                 "end_sec": float(i.get("end_sec") or 0.0), "fake_prob": float(i.get("fake_prob") or 0.0)}
                for i in (long_task.result or {}).get("intervals") or [] if isinstance(i, dict)]
    if job.media_type != "video":
        return []
    media = job.media
    fps = (media.fps if media and media.fps else None) or 25.0
    duration = (media.duration_seconds if media else None) or 0.0
    threshold = PlatformSettings.load().fake_threshold
    series: list[tuple[Any, list[tuple[int, float]]]] = []  # (spec, [(second, fake prob)])
    for t in tasks:
        frames = (t.result or {}).get("per_frame") if t.kind == JobTask.Kind.MODEL else None
        spec = reg.get(t.target)
        if t.status != JobTask.Status.SUCCEEDED or not frames or spec is None:
            continue
        points_of_task = []
        for idx, f in enumerate(frames):
            try:
                second = float(f.get("frame")) / fps
            except (TypeError, ValueError, AttributeError):
                second = duration * idx / max(1, len(frames))
            try:
                points_of_task.append((int(second), float(f.get("fake_prob"))))
            except (TypeError, ValueError, AttributeError):
                continue
        series.append((spec, points_of_task))
    # Weighted like the verdict (results.group_results): an authentic-boosted detector weighs more on
    # frames it calls authentic, and those frames may also count in the other analysis's line, but
    # only where that analysis has frames of its own.
    own = {(spec.family, second) for spec, pts in series for second, _ in pts}
    bins: dict[tuple[str, int], list[tuple[float, float]]] = defaultdict(list)
    for spec, pts in series:
        for second, prob in pts:
            for family in ANALYSIS_IDS:
                if spec.counts_in(family, prob, threshold) and (family, second) in own:
                    bins[(ANALYSIS_IDS[family], second)].append((spec.vote_weight(prob, threshold), prob))
    points = []
    for (group, second) in sorted(bins, key=lambda k: (k[1], k[0])):
        pairs = bins[(group, second)]
        total = sum(w for w, _ in pairs) or 1.0
        points.append({"analysis": group, "start_sec": float(second), "end_sec": float(second + 1),
                       "fake_prob": round(sum(w * p for w, p in pairs) / total, 4)})
    limit = TIMELINE_POINTS * len(ANALYSIS_IDS)
    if len(points) > limit:  # keep the payload small for long clips
        step = len(points) / limit
        points = [points[int(i * step)] for i in range(limit)]
    return points


def long_video(job: Job, tasks: list[JobTask]) -> dict[str, Any] | None:
    stream = (job.summary or {}).get("stream")
    task = _task(tasks, JobTask.Kind.LONG_VIDEO)
    if task is None:
        return None
    result = task.result or {}
    return {"status": (stream or {}).get("status") or task.status,
            "analysed_seconds": (stream or {}).get("analysed_seconds"),
            "range_seconds": (stream or {}).get("range_seconds"),
            "duration_seconds": result.get("duration"), "range": result.get("range")}


def news(job: Job) -> dict[str, Any] | None:
    n = (job.summary or {}).get("news")
    if not n:
        return None
    return {"status": n.get("status"), "confidence": n.get("confidence"),
            "report_markdown": n.get("report_markdown", ""), "meta": n.get("meta") or {}}


def options(job: Job) -> dict[str, Any]:
    return {k: v for k, v in (job.options or {}).items() if k in PUBLIC_OPTIONS}


# --- artifacts and events --------------------------------------------------------------------

def is_public_artifact(artifact: Artifact) -> bool:
    """Heatmaps, face crops and annotated videos; not copies of the input or per-detector data."""
    return (artifact.kind in PUBLIC_ARTIFACT_KINDS and not (artifact.meta or {}).get("preview")
            and artifact.label.strip().lower() not in ("original", "input"))


def _heatmap_rank(artifact: Artifact) -> int:
    """Which of a detector's images is its heatmap: the blended whole-image map first, then other
    whole-image maps, then face-only maps; raw colour maps last."""
    label = artifact.label.strip().lower()
    if label in ("grad-cam", "gradcam", "attention"):
        return 0
    if "overlay" in label:
        return 1
    if "heatmap" in label and "overlay" not in label:
        return 5
    if artifact.kind == Artifact.Kind.XAI and "face" not in label:
        return 2
    return 3 if artifact.kind == Artifact.Kind.XAI else 4


def evidence_artifacts(job: Job, tasks: list[JobTask] | None = None) -> list[Artifact]:
    """One heatmap from each detector whose heatmap the administrator shows to users (Admin → Models).

    Detectors write several images (maps, overlays, per-face crops); users get the single main map
    of each chosen detector, ordered by the detector's weight, and nothing from the others.
    """
    reg = registry()
    shown: dict[Any, float] = {}
    for t in tasks if tasks is not None else job.tasks.all():
        spec = reg.get(t.target)
        if t.kind == JobTask.Kind.MODEL and spec is not None and spec.show_heatmap:
            shown[t.pk] = spec.weight
    by_task: dict[Any, list[Artifact]] = defaultdict(list)
    for art in job.artifacts.all():
        if art.task_id in shown and is_public_artifact(art) and art.content_type.startswith("image/"):
            by_task[art.task_id].append(art)
    chosen = [min(arts, key=lambda a: (_heatmap_rank(a), a.created_at)) for arts in by_task.values()]
    return sorted(chosen, key=lambda a: (-shown[a.task_id], a.created_at))


def is_downloadable(job: Job, artifact: Artifact) -> bool:
    """What a user may download: the selected evidence, and the preview frame of a streamed scan."""
    if (artifact.meta or {}).get("preview"):
        return True
    return any(a.pk == artifact.pk for a in evidence_artifacts(job))


def artifact_label(artifact: Artifact) -> str:
    return PUBLIC_ARTIFACT_KINDS.get(artifact.kind, "other")


def artifact_filename(artifact: Artifact) -> str:
    """A download name that says nothing about the detector that produced the file."""
    suffix = PurePosixPath(artifact.storage_key).suffix.lower()[:8]
    label = "preview" if (artifact.meta or {}).get("preview") else artifact_label(artifact)
    return f"{label}-{str(artifact.pk)[-8:]}{suffix}"


def artifacts(job: Job, url_prefix: str, tasks: list[JobTask] | None = None) -> list[dict[str, Any]]:
    return [{"id": str(art.pk), "kind": PUBLIC_ARTIFACT_KINDS[art.kind], "label": artifact_label(art),
             "content_type": art.content_type, "size_bytes": art.size_bytes,
             "url": f"{url_prefix}/{job.pk}/artifacts/{art.pk}/content", "created_at": art.created_at}
            for art in evidence_artifacts(job, tasks)]


def events(job: Job) -> list[dict[str, Any]]:
    return [{"id": e.pk, "created_at": e.created_at, "level": e.level, "code": e.code, "message": e.public_message,
             "data": public_data(e.data)}
            for e in job.events.all() if e.public_message]
