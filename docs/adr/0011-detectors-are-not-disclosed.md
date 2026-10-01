# 0011 · Users never see which detectors run or how

**Context.** The detectors are private models. The owner decided (2026-10-01) that only the
administrator chooses what runs, and that users — in the web app, the public API, reports,
explanations and the live processing view — learn the verdict and its evidence but never which
detectors ran, how many, or how the analysis works. Metadata evidence (EXIF / XMP / C2PA) stays
visible because it describes the user's own file. AI-generation markers in metadata flag a file
"likely AI-generated": definite markers always, weak hints only when the detectors already judged
it fake. Long-form scans use one admin-chosen detector.

**Decision.**

- *What runs is configuration.* Admin → Models sets, per detector, whether it runs on every image
  and every video (`ModelOverride.run_on_image/run_on_video`, defaulting to `default_selected` in
  `models.yaml`), whose heatmap users see (`ModelOverride.show_heatmap`, default Center — one image
  per chosen detector), the extra checks every job runs (`PlatformSettings.audit_steps`; metadata
  always), the long-form detector (`PlatformSettings.long_video_model`) and, per long-form detector,
  face cropping (`PlatformSettings.long_video_face_crops`; missing = the detector's default). Requests carry files and options
  only; `models` / `audit_steps` fields are ignored.
- *One projection for users.* `sml/jobs/public.py` builds everything user-facing from a job:
  generic steps, one result per analysis — face swap, AI generation, general (the detectors'
  families, editable on Admin → Models) — with its verdict and probability but never how many
  detectors it combines, verdict reasons, provenance, check results, a video timeline per analysis
  and one heatmap
  (the main blended map) from each detector the admin chose, with generic labels and file names. The user serializers, reports,
  the explanation prompt and the news-agent prompt are all built from it. The detailed serializers
  are named `Admin*` and only admin endpoints use them.
- *Timeline events have two messages.* `JobEvent.message` is the operator's; users see only events
  with a `public_message`, and live (SSE) payloads carry only public messages and whitelisted data.
  Workers no longer publish task progress or log lines to users; they send a `job.activity` ping and
  the page refetches the user view. Task logs are an admin endpoint.
- *Nothing leaks through side doors.* The detector catalogs are gone from the user API, API keys
  have no detector allow-list, the dashboard counts analyses by type, the long-form token names the
  session only (the stream service claims the parameters from the API once) and forwards whitelisted
  engine fields, and the published OpenAPI document omits the admin API.

The headline verdict is fake when any analysis says fake and shows the highest analysis probability
(owner, 2026-10-01); each analysis combines its detectors with their weights.

**Consequences.** Re-running a job uses the current admin configuration. Per-detector scores,
heatmap provenance and logs remain available to staff in the admin console. Adding a field to a
user payload means adding it to the projection deliberately; `sml/jobs/tests/test_privacy.py`
asserts that no detector id or name appears in user responses, live events or reports.
