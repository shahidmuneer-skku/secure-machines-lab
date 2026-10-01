"""Image studio jobs (owner, 2026-10-01): generate images from a prompt or edit reference images.

* The admin picks one model per mode (Admin → Studio); users never choose or see it. Staff with
  `manage_models` may try any installed model (it is loaded on demand).
* Credits: the quote is images requested × the mode's price; only delivered images are charged.
  Refused prompts, refused references, missing consent and failures are not charged.
* Safeguards: the worker refuses sexual/violent prompts (local LLM) and NSFW references/outputs
  (classifier); reference images showing a face need the user's confirmation that they have the
  person's consent, which is logged with the job.
* Jobs share the detection pipeline: queue, credit hold, history, live progress and cancellation.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any

from django.db import transaction
from django.utils import timezone

from sml.catalog import access
from sml.core.exceptions import ApiError, InvalidMedia
from sml.core.models import PlatformSettings
from sml.core.permissions import has_capability
from sml.credits import pricing
from sml.credits import services as credits
from sml.jobs.models import Job, JobTask
from sml.jobs.retention import priority_for, retention_days_for
from sml.jobs.services import _after_commit_dispatch, _check_platform
from sml.jobs.timeline import emit, push_job_state
from sml.media.models import MediaObject
from sml.queues import STUDIO

from .registry import MODES, StudioModel, publish_keep, registry, server_status

CONSENT_STATEMENT = ("I confirm that I have the consent of every person shown in the reference images to edit "
                     "their likeness, and that I will not use the result to deceive, defame or harass anyone.")
CONSENT_VERSION = "2026-10-01"


class StudioUnavailable(ApiError):
    status_code = 503
    default_code = "STUDIO_UNAVAILABLE"
    default_detail = "The image studio is not available right now. Please try again later."
    title = "Studio unavailable"


@dataclass
class StudioRequest:
    mode: str
    prompt: str
    negative_prompt: str = ""
    aspect_ratio: str = ""
    steps: int | None = None
    guidance: float | None = None
    seed: int | None = None
    count: int = 1
    transparent: bool = False
    references: list[MediaObject] = field(default_factory=list)
    consent: bool = False
    model: str = ""  # staff only: try another model
    locale: str = "en"


def can_choose_model(user: Any) -> bool:
    return has_capability(user, "manage_models")


def active_model(mode: str) -> StudioModel | None:
    """The admin's model for `mode`, or None when the mode is off."""
    cfg = PlatformSettings.load()
    if not cfg.studio_enabled:
        return None
    model_id = cfg.studio_generate_model if mode == "generate" else cfg.studio_edit_model
    model = registry().get(model_id) if model_id else None
    return model if model and model.supports(mode) else None


def keep_models() -> list[str]:
    """Models the studio server keeps loaded: the admin's, generation first."""
    return [m.id for m in (active_model("generate"), active_model("edit")) if m]


def sync_keep() -> None:
    publish_keep(keep_models())


def studio_config(user: Any) -> dict[str, Any]:
    """What the studio page needs: per mode, the controls of the admin's model and the price."""
    reg = registry()
    allowed = access.module_allowed(user, "studio")
    status = server_status()
    modes = {}
    for mode in MODES:
        model = active_model(mode)
        modes[mode] = {
            "available": bool(allowed and model),
            "price": pricing.studio_unit_price(mode),
            "controls": model.controls(mode, reg.limits) if model else None,
        }
    out: dict[str, Any] = {"enabled": allowed and any(m["available"] for m in modes.values()), "modes": modes,
                           "consent_statement": CONSENT_STATEMENT, "consent_version": CONSENT_VERSION,
                           "online": status.get("state") == "ready"}
    if can_choose_model(user):  # staff can try every model; users never see model names
        installed = status.get("models") or {}
        out["models"] = [{"id": m.id, "name": m.name, "vendor": m.vendor, "license": m.license,
                          "commercial": m.commercial, "modes": list(m.modes),
                          "installed": bool((installed.get(m.id) or {}).get("installed")),
                          "loaded": m.id in (status.get("loaded") or []),
                          "controls": {mode: m.controls(mode, reg.limits) for mode in m.modes}}
                         for m in reg.models.values()]
        out["active"] = {mode: (active_model(mode).id if active_model(mode) else None) for mode in MODES}
    return out


def _resolve_model(user: Any, req: StudioRequest) -> StudioModel:
    if req.mode not in MODES:
        raise ApiError("Choose generate or edit.")
    if req.model and req.model != getattr(active_model(req.mode), "id", None):
        if not can_choose_model(user):
            raise ApiError("Only administrators can choose the studio model.")
        model = registry().get(req.model)
        if model is None or not model.supports(req.mode):
            raise ApiError(f"{req.model} does not support {req.mode}.")
        return model
    model = active_model(req.mode)
    if model is None:
        raise StudioUnavailable("Image generation is off right now." if req.mode == "generate"
                                else "Image editing is off right now.")
    return model


def prepare(user: Any, req: StudioRequest) -> tuple[StudioModel, dict[str, Any], pricing.Quote]:
    """Validate a request against the model's controls; returns (model, parameters, quote)."""
    access.assert_module_allowed(user, "studio")
    model = _resolve_model(user, req)
    controls = model.controls(req.mode, registry().limits)
    prompt = req.prompt.strip()
    if not prompt:
        raise ApiError("Describe the image you want.")
    if len(prompt) > controls["prompt_max_chars"]:
        raise ApiError(f"The prompt is limited to {controls['prompt_max_chars']} characters.")
    refs = req.references
    if not controls["references"]["min"] <= len(refs) <= controls["references"]["max"]:
        if req.mode == "edit":
            raise ApiError(f"Add between 1 and {controls['references']['max']} reference images.")
        raise ApiError("Reference images are for editing.")
    max_mb = int(registry().limits.get("reference_max_mb", 25))
    for media in refs:
        if media.status != MediaObject.Status.READY or media.media_type != "image":
            raise InvalidMedia("Reference images must be uploaded images.")
        if media.size_bytes > max_mb * 1024 * 1024:
            raise InvalidMedia(f"Reference images up to {max_mb} MB are supported.")
    if not 1 <= req.count <= controls["max_outputs"]:
        raise ApiError(f"Choose between 1 and {controls['max_outputs']} images.")
    params: dict[str, Any] = {"mode": req.mode, "model": model.id, "prompt": prompt, "count": req.count,
                              "seed": req.seed if req.seed is not None else random.randint(0, 2**31 - 1)}  # noqa: S311
    if not 0 <= params["seed"] < 2**31:
        raise ApiError("The seed must be between 0 and 2147483647.")
    if req.negative_prompt.strip():
        if not controls["negative_prompt"]:
            raise ApiError("This studio does not take a negative prompt.")
        params["negative_prompt"] = req.negative_prompt.strip()[:controls["prompt_max_chars"]]
    if req.aspect_ratio:
        ratio = next((r for r in controls["aspect_ratios"] if r["id"] == req.aspect_ratio), None)
        if ratio is None:
            raise ApiError("Unsupported image format.")
        params.update(aspect_ratio=ratio["id"], width=ratio["width"], height=ratio["height"])
    elif req.mode == "generate" and controls["aspect_ratios"]:
        first = controls["aspect_ratios"][0]
        params.update(aspect_ratio=first["id"], width=first["width"], height=first["height"])
    for name in ("steps", "guidance"):
        value = getattr(req, name)
        spec = controls[name]
        if value is None:
            continue
        if spec is None:
            raise ApiError(f"This studio does not take {name}.")
        if not float(spec["min"]) <= float(value) <= float(spec["max"]):
            raise ApiError(f"{name.capitalize()} must be between {spec['min']} and {spec['max']}.")
        params[name] = int(value) if name == "steps" else float(value)
    if req.transparent:
        if not controls["transparent"] or req.mode != "generate":
            raise ApiError("Transparent backgrounds are not available here.")
        params["transparent"] = True
    return model, params, pricing.quote_studio(req.mode, req.count)


def create_studio_job(user: Any, req: StudioRequest, *, source: str = "web", api_key: Any = None,
                      consent_meta: dict[str, Any] | None = None) -> Job:
    _check_platform()
    model, params, quote = prepare(user, req)
    priority = priority_for(user, source)
    options: dict[str, Any] = {"studio": {**params, "references": [str(m.pk) for m in req.references],
                                          "unit_credits": pricing.studio_unit_price(req.mode)}}
    if req.references:
        options["consent"] = {"confirmed": bool(req.consent), "statement_version": CONSENT_VERSION,
                              "at": timezone.now().isoformat(), **(consent_meta or {})}
    with transaction.atomic():
        job = Job.objects.create(
            user=user, api_key=api_key if hasattr(api_key, "prefix") else None, source=source, kind=Job.Kind.STUDIO,
            media=req.references[0] if req.references else None, media_type="image", title=params["prompt"][:255],
            models_selected=[model.id], options=options, locale=req.locale, priority=priority,
            credits_quoted=quote.credits,
            quote_lines=[{"label": ln.label, "credits": ln.credits} for ln in quote.lines],
            expires_at=timezone.now() + timedelta(days=retention_days_for(user)),
        )
        job.hold = credits.reserve(user, quote.credits, reference_type="job", reference_id=str(job.pk))
        job.save(update_fields=["hold"])
        JobTask.objects.create(job=job, kind=JobTask.Kind.STUDIO, target=model.id, media_type="image", queue=STUDIO,
                               priority=priority, max_attempts=2)
        what = "Image generation" if req.mode == "generate" else "Image edit"
        emit(job, "job.created", f"{what} with {model.name}: {req.count} image(s)",
             public=f"{what} requested ({req.count} image{'s' if req.count > 1 else ''})",
             data={"models": [model.id], "count": req.count})
        if req.references and req.consent:
            emit(job, "studio.consent", "The user confirmed having the consent of the people shown "
                 f"(statement {CONSENT_VERSION})", public="You confirmed you have consent from the people shown",
                 data=options["consent"])
        if quote.credits:
            message = f"{quote.credits} credits reserved"
            emit(job, "credits.reserved", message, public=message, data={"credits": quote.credits})
        emit(job, "job.queued", "Queued for the studio", public="Queued", data={"priority": priority})
        push_job_state(job)
        _after_commit_dispatch()
    if api_key is not None and hasattr(api_key, "prefix"):
        from sml.apikeys.services import bump_usage

        bump_usage(api_key, jobs=1, credits=quote.credits)
    return job


# --- results ---------------------------------------------------------------------------------------

def finalize_studio(job: Job, task: JobTask, reasons: list[dict[str, Any]]) -> None:
    """Register the delivered images as the user's media and charge for them only."""
    result = task.result or {}
    outputs = (result.get("outputs") or []) if task.status == JobTask.Status.SUCCEEDED else []
    blocked = int(result.get("blocked") or 0)
    if not outputs:
        job.status = Job.Status.FAILED
        job.error_code = task.error_code or "STUDIO_FAILED"
        from sml.jobs.errors import user_message

        job.error_message = (user_message(job.error_code) + " You were not charged.")[:500]
        _settle(job, 0, "Image studio: nothing delivered — credits released")
        return
    short = str(job.pk)[:8]
    media = [MediaObject.objects.create(
        id=o["id"], owner=job.user, status=MediaObject.Status.READY, media_type="image",
        original_name=f"studio-{short}-{i + 1}.png", extension="png", content_type=o.get("content_type") or "image/png",
        size_bytes=int(o.get("size_bytes") or 0), sha256=o.get("sha256") or "", storage_key=o["storage_key"],
        thumbnail_key=o.get("thumbnail_key") or "", width=o.get("width"), height=o.get("height"),
        generated_by=job, expires_at=job.expires_at,
    ) for i, o in enumerate(outputs)]
    unit = int((job.options.get("studio") or {}).get("unit_credits") or 0)
    job.summary = {"studio": {"outputs": [str(m.pk) for m in media], "blocked": blocked,
                              "seeds": [o.get("seed") for o in outputs], "faces": int(result.get("faces") or 0)}}
    reasons.append({"code": "studio", "delivered": len(media), "blocked": blocked})
    job.status = Job.Status.SUCCEEDED
    if blocked:
        message = f"{blocked} image{'s' if blocked > 1 else ''} withheld by the safety filter — not charged"
        emit(job, "studio.blocked", message, public=message, level="warning", task=task)
    _settle(job, unit * len(media), f"Image studio: {len(media)} image(s)")


def _settle(job: Job, amount: int, memo: str) -> None:
    if not job.hold_id:
        return
    quoted = job.hold.amount
    hold = credits.settle(job.hold, amount, memo=memo[:255])
    job.credits_charged = hold.amount if hold.status == hold.Status.CAPTURED else 0
    if job.credits_charged:
        message = f"{job.credits_charged} credits charged"
        emit(job, "credits.charged", message, public=message)
    if quoted - job.credits_charged:
        message = f"{quoted - job.credits_charged} credits returned to your balance"
        emit(job, "credits.released", message, public=message)
