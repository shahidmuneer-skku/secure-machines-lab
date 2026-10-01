"""Per-detector results and accuracy for administrators (owner request, 2026-10-01).

Users see one result per analysis and never the detectors (ADR 0011). Administrators additionally see,
on the result page and in Admin → Models, what each detector said about the file and how accurate each
detector is:

* benchmark figures the administrator enters from the detector's paper (ModelOverride.benchmark_*);
* measured accuracy over the files an administrator labelled with their ground truth (Job.truth). A
  detector is measured on the files labelled authentic or labelled with its own analysis: face-swap
  detectors on authentic + face-swap files, AI-generation detectors on authentic + AI-generated files.
  A file without a face (no score) does not count. The platform's fake threshold decides the verdict.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from sml.catalog.models import ModelOverride
from sml.catalog.registry import registry
from sml.core.models import PlatformSettings

from .models import Artifact, Job, JobTask
from .public import ANALYSIS_IDS, _heatmap_rank

FRAME_POINTS = 120
POSITIVE_TRUTH = {"deepfake": Job.Truth.FACE_SWAP, "ai_generated": Job.Truth.AI_GENERATED}


def _auc(pairs: list[tuple[float, bool]]) -> float | None:
    """Area under the ROC curve from (score, is_fake) pairs (rank statistic; ties count half)."""
    pos = sum(1 for _, p in pairs if p)
    neg = len(pairs) - pos
    if not pos or not neg:
        return None
    ordered = sorted(pairs, key=lambda x: x[0])
    rank_sum, i = 0.0, 0
    while i < len(ordered):
        j = i
        while j < len(ordered) and ordered[j][0] == ordered[i][0]:
            j += 1
        mean_rank = (i + 1 + j) / 2  # ranks i+1 .. j share their mean
        rank_sum += mean_rank * sum(1 for _, p in ordered[i:j] if p)
        i = j
    return (rank_sum - pos * (pos + 1) / 2) / (pos * neg)


def metrics(pairs: list[tuple[float, bool]], threshold: float) -> dict[str, Any]:
    """Accuracy figures for (fake probability, truly fake) pairs."""
    n = len(pairs)
    fake = sum(1 for _, p in pairs if p)
    tp = sum(1 for s, p in pairs if p and s >= threshold)
    fp = sum(1 for s, p in pairs if not p and s >= threshold)
    tn = n - fake - fp
    return {
        "files": n, "fake_files": fake, "authentic_files": n - fake,
        "accuracy": (tp + tn) / n if n else None,
        "precision": tp / (tp + fp) if tp + fp else None,
        "recall": tp / fake if fake else None,
        "specificity": tn / (n - fake) if n - fake else None,
        "auc": _auc(pairs),
    }


def _score(task: JobTask) -> float | None:
    result = task.result or {}
    prob = result.get("fake_prob")
    if result.get("no_face") or prob is None:
        return None
    try:
        return float(prob)
    except (TypeError, ValueError):
        return None


def measured_accuracy(threshold: float | None = None) -> dict[str, dict[str, Any]]:
    """Measured accuracy per detector id over the labelled files (see the module docstring)."""
    reg = registry()
    if threshold is None:
        threshold = PlatformSettings.load().fake_threshold
    pairs: dict[str, list[tuple[float, bool]]] = defaultdict(list)
    tasks = (JobTask.objects.filter(kind=JobTask.Kind.MODEL, status=JobTask.Status.SUCCEEDED,
                                    job__deleted_at__isnull=True)
             .exclude(job__truth="").select_related("job").only("target", "result", "job__truth"))
    for task in tasks:
        spec = reg.get(task.target)
        score = _score(task)
        if spec is None or score is None:
            continue
        truth = task.job.truth
        if truth == Job.Truth.AUTHENTIC:
            pairs[spec.id].append((score, False))
        elif truth == POSITIVE_TRUTH.get(spec.family):
            pairs[spec.id].append((score, True))
    out = {model_id: metrics(p, threshold) for model_id, p in pairs.items()}
    exief_pairs = _exief_pairs()
    if exief_pairs:
        out[EXIEF_ID] = metrics(exief_pairs, threshold)
    return out


def _exief_pairs() -> list[tuple[float, bool]]:
    """EXIEF on files labelled authentic or AI-generated: its vote when it counted, else 0 (it did
    not flag the file - no signal, or metadata it could not trust)."""
    from .results import exief_report, exief_vote

    jobs = (Job.objects.filter(truth__in=[Job.Truth.AUTHENTIC, Job.Truth.AI_GENERATED], deleted_at__isnull=True)
            .prefetch_related("tasks"))
    pairs = []
    for job in jobs:
        tasks = list(job.tasks.all())
        if exief_report(tasks) is None:
            continue  # EXIEF did not run on this file
        vote = exief_vote(tasks, weight=1.0)
        pairs.append((vote[1] if vote else 0.0, job.truth == Job.Truth.AI_GENERATED))
    return pairs


EXIEF_ID = "exief"


def exief_breakdown(tasks: list[JobTask], measured: dict[str, Any] | None) -> dict[str, Any] | None:
    """What the EXIEF metadata scorer found in one file and whether it counted (admin only)."""
    from .results import exief_report, exief_vote

    report = exief_report(tasks)
    if report is None:
        return None
    vote = exief_vote(tasks)
    weight = PlatformSettings.load().exief_weight
    return {"verdict": report.get("verdict"), "score": report.get("score"), "generator": report.get("generator"),
            "signals": [{"id": sig.get("id"), "label": sig.get("label"), "tier": sig.get("tier"),
                         "weight": sig.get("weight"), "evidence": sig.get("evidence") or []}
                        for sig in report.get("signals") or []],
            "untrustworthy": report.get("untrustworthy") or [], "counted": vote is not None,
            "fake_probability": vote[1] if vote else None, "weight": weight, "measured": measured}


def benchmarks() -> dict[str, dict[str, Any]]:
    out = {}
    for o in ModelOverride.objects.all():
        if o.benchmark_accuracy is not None or o.benchmark_auc is not None or o.benchmark_dataset:
            out[o.model_id] = {"accuracy": o.benchmark_accuracy, "auc": o.benchmark_auc,
                               "dataset": o.benchmark_dataset}
    return out


def _frames(task: JobTask, fps: float) -> list[dict[str, float]]:
    """The detector's per-frame fake probability as at most FRAME_POINTS (second, probability) points."""
    points: list[tuple[float, float]] = []
    for idx, f in enumerate((task.result or {}).get("per_frame") or []):
        try:
            second = float(f.get("frame", idx)) / fps
            points.append((second, float(f["fake_prob"])))
        except (TypeError, ValueError, KeyError, AttributeError):
            continue
    if len(points) <= FRAME_POINTS:
        return [{"second": round(s, 3), "fake_probability": round(p, 4)} for s, p in points]
    size = len(points) / FRAME_POINTS
    out = []
    for b in range(FRAME_POINTS):
        chunk = points[int(b * size):int((b + 1) * size)] or points[int(b * size):int(b * size) + 1]
        out.append({"second": round(chunk[0][0], 3),
                    "fake_probability": round(sum(p for _, p in chunk) / len(chunk), 4)})
    return out


def truth(job: Job) -> dict[str, Any]:
    return {"truth": job.truth or None, "labeled_by": job.truth_by.email if job.truth_by else None,
            "labeled_at": job.truth_at}


def breakdown(job: Job, artifact_url: str) -> dict[str, Any]:
    """Every detector's result for one job, for administrators. `artifact_url` is formatted with the
    artifact id to link each detector's heatmap."""
    reg = registry()
    threshold = PlatformSettings.load().fake_threshold
    tasks = [t for t in job.tasks.all() if t.kind == JobTask.Kind.MODEL]
    heatmaps: dict[Any, Artifact] = {}
    for art in job.artifacts.all():
        if art.task_id is None or art.kind != Artifact.Kind.XAI or not art.content_type.startswith("image/"):
            continue
        best = heatmaps.get(art.task_id)
        if best is None or (_heatmap_rank(art), art.created_at) < (_heatmap_rank(best), best.created_at):
            heatmaps[art.task_id] = art
    measured = measured_accuracy(threshold)
    bench = benchmarks()
    fps = (job.media.fps if job.media and job.media.fps else None) or 25.0
    # Analyses with a score from one of their own detectors (others' authentic answers only join those).
    scored_families = {spec.family for t in tasks if (spec := reg.get(t.target)) and _score(t) is not None}
    rows: list[dict[str, Any]] = []
    for t in tasks:
        spec = reg.get(t.target)
        family = spec.family if spec else "ai_generated"
        result = t.result or {}
        score = _score(t)
        verdict = ("no_face" if result.get("no_face") else
                   None if score is None else "fake" if score >= threshold else "real")
        heatmap = heatmaps.get(t.pk)
        counted_in = ([ANALYSIS_IDS[f] for f in ANALYSIS_IDS
                       if f in scored_families and spec.counts_in(f, score, threshold)]
                      if spec and score is not None else [])
        rows.append({
            "id": t.target, "task_id": t.pk, "name": spec.name("en") if spec else t.target,
            "analysis": ANALYSIS_IDS.get(family, "ai_generated"), "status": t.status,
            "fake_probability": score, "verdict": verdict,
            "weight": (spec.vote_weight(score, threshold) if score is not None else spec.weight) if spec else None,
            "counted_in": counted_in,
            "duration_ms": t.duration_ms, "gpu": t.gpu, "attempt": t.attempt, "fallback_for": t.fallback_for_id,
            "error_code": t.error_code, "error_message": t.error_message,
            "heatmap_url": artifact_url.format(artifact_id=heatmap.pk) if heatmap else None,
            "per_frame": _frames(t, fps) if job.media_type == "video" else [],
            "benchmark": bench.get(t.target), "measured": measured.get(t.target),
        })
    order = list(ANALYSIS_IDS.values())
    rows.sort(key=lambda r: (order.index(str(r["analysis"])), r["fake_probability"] is None,
                             -float(r["fake_probability"] or 0.0), str(r["name"])))
    return {"job_id": job.pk, "media_type": job.media_type, "threshold": threshold,
            "duration_seconds": job.media.duration_seconds if job.media else None,
            "truth": truth(job), "detectors": rows,
            "exief": exief_breakdown(list(job.tasks.all()), measured.get(EXIEF_ID))}
