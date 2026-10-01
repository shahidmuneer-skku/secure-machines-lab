# Changelog

All notable changes to this project. The format follows [Keep a Changelog](https://keepachangelog.com/).

## [Unreleased] — first release candidate

### Added
- Detection of images and videos combined into one weighted verdict; EXIF / XMP / C2PA
  AI-generation markers; heatmaps and face maps; face, safety and anti-spoofing checks.
- Long-form video scanning, news verification agent, on-demand "Explain why".
- Job queue with per-model priority queues, fair per-user dispatching, live progress over SSE
  (queue position, ETA, per-model progress, processing log), history with retention per plan.
- Credits: expiring buckets, holds, append-only ledger, daily free credits, signup bonus,
  admin grants; nightly ledger audit.
- Payments: Toss Payments and Stripe, credit packs and subscriptions, receipts, refunds by policy.
- Accounts: email verification, password reset, sessions management, TOTP, recovery codes,
  passkeys; role-based access with capability permissions and per-user access policies.
- API keys with scopes, IP and model allow-lists, expiry, rotation, rate limits, usage stats.
- Reports in PDF, HWP (RTF) and CSV, ZIP bundles, in English, Korean and German.
- Guest trial on the homepage; pricing, terms, privacy, refund-policy and API docs pages.
- Admin console: users, roles, jobs, queues and GPUs, models, pricing, packs and plans,
  payments and refunds, webhooks, API usage, audit log, platform settings, maintenance mode.
- Korean and German translations with automated ICU parity checks.
- Branded account emails and security notifications in three languages.
- Admin: add or remove credits for any account including one's own (explicit direction,
  balance preview, confirmation for removals); block and unblock users with a reason from the
  list or the user page; a Blocked filter; a system health panel with service checks, per-GPU
  running and waiting work, the long-video GPU, the loaded AI model and launch-readiness settings.
- Tests for the API, the model worker and the web app; CI; nginx and systemd deployment files;
  architecture, operations and model-onboarding documentation; decision records.
- Administrators see each detector's answer on result pages (admin-only *Detector breakdown*:
  verdict, probability, weight, time, heatmap, per-frame curve), label files with their ground truth,
  and compare each detector's measured accuracy (accuracy, AUC, precision, recall over labelled files)
  with benchmark figures they enter on Admin → Models. Users still see only the two analyses.
- A detector can count more when it says authentic (*Authentic ×*), and that answer can also count in
  the other analysis. SKKU-P2 counts 2× in both, as it recognises authentic images best.
- XB-DFD face-swap detector (explanation bottleneck: CLIP + BLIP captions, with a heatmap of forgery
  cues) for images and videos. Videos are scored frame by frame: up to 128 frames spread over the clip,
  with the per-frame timeline and the most suspicious frame's heatmap.

### Changed
- Users no longer choose detectors or checks: the administrator sets which detectors run on every
  image and every video, the extra checks, and the long-form detector (Admin → Models). Users and
  API clients see the verdict, its evidence and generic progress steps only — no detector names,
  counts, per-detector scores, logs or methods in the app, the API, live events, reports or the AI
  explanations (ADR 0011). Staff keep the full detail in the admin console, including per-task logs.
- Results are reported per analysis — face swap and AI generation — each with its own verdict
  and probability (no detector counts); the headline ("Analysis Result") is fake when any analysis is
  fake. SKKU (BEYBI), B2 and XB-DFD count towards face swap, Center and Inzi towards AI generation. The
  administrator can move a detector to another analysis. Reports, the AI explanation and the news
  agent use the same split; video timelines show one line per analysis.
- Heatmaps: the administrator chooses whose heatmap users see (one image per detector; Center by
  default). Face cropping for long-form scans is set per detector.
- Metadata markers: a definite AI-generation marker labels a file "Likely AI-generated" regardless
  of the detectors; a weak hint only when the detectors judged it fake.
- The detect page is upload → review; the dashboard shows analyses by type.
- Xception is offered for video only until its image weights are restored.

### Security
- The Django data admin no longer accepts password-only logins; it requires a superuser
  session verified with two-factor authentication.
- API keys cannot raise their own rate limit above the platform limit.
- Payment amount mismatches are persisted and flagged for review.
- Model failures show users a classified message only; stack traces and server paths are kept
  for staff. Model scripts receive an allow-listed environment without platform secrets.
- Tasks never picked up by a worker fail after 24 hours so credits are always released.
- Only a super admin can block another super admin; removing credits from an empty wallet is
  refused instead of writing a zero entry.
- The long-form session token names the session only; the stream service claims the paid
  parameters from the API once. The published OpenAPI document omits the admin API.

### Fixed
- Video detectors failed on this server: conda envs copied from another machine could not verify
  HTTPS certificates, BEYBI's dlib could not find its own libraries, and two weight sets that the
  old machine had downloaded at runtime were missing. The anti-spoofing check now reports a
  configuration error instead of "completed" when its code is not installed.
- Development API reloads no longer hang on open live-update connections.
- Video jobs could stay "running": a worker's result was lost when the API failed to record it (a
  migration ran before the API worker restarted). Recording now retries, and workers keep each final
  result in Redis for the stale-task sweep to replay.
- Restarting a model worker (deploys, systemctl) lost the tasks it was running or holding: the pool
  processes received the stop signal and Celery acknowledged their messages as failed. Tasks now go
  back to the queue, and the model subprocess is stopped instead of running on without a worker.
- Per-frame video scores: per-frame percentages such as `73%` (SKKU/BEYBI) were dropped, so its
  timeline was empty; a total row of frame counts above 100 (`Total result,145,0`) lost the count;
  the `processing` placeholder row counted as a frame scored 0.5; and `Total result,0,0,no_face` read
  as 0% fake instead of "no face".
- SKKU (BEYBI) video: dlib loaded CUDA 12.9 cuSOLVER against PyTorch's cuBLAS 12.1; the env now puts
  PyTorch's CUDA libraries first.
- Content-Security-Policy with per-request nonces; HSTS; secure cookies; problem-details errors
  without server details.
