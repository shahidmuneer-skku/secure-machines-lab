# Operations

Single-host production layout (the current GPU server): PostgreSQL, Redis, RabbitMQ and S3
storage run in Docker Compose bound to 127.0.0.1; the API, background worker, scheduler, web app
and one model worker per GPU run as systemd services behind nginx.

| Service | Unit | Listens |
| --- | --- | --- |
| Django API (uvicorn) | `sml-api` | 127.0.0.1:8000 |
| Background worker (dispatch, results, reports, maintenance) | `sml-celery` | — |
| Scheduler (Celery beat, exactly one) | `sml-beat` | — |
| Next.js | `sml-web` | 127.0.0.1:3000 |
| Detector worker on GPU *n* (GPU admission) | `sml-worker@n` | — |
| Agent worker (news, explain-why; shared Ollama model) | `sml-agents` | — |
| Long-form stream service (GPU 2, `safe` env) | `sml-stream` | 127.0.0.1:8100 (`/stream/ws` via nginx) |
| Infrastructure | `docker compose` (restart: unless-stopped) | 127.0.0.1:55432 / 56379 / 55672 / 55673 / 58333 |

GPU note for this server: GPUs 0 and 3 (RTX A5000) run the model workers, GPU 2 (A5000) is
dedicated to long-form streaming (`SML_STREAM_GPU`), and GPU 1
(Blackwell, sm_120) is reserved for Ollama because the legacy model environments ship
PyTorch builds without kernels for it (they fail with `GPU_UNSUPPORTED`).

## First deployment

Prerequisites: Docker, NVIDIA driver, nginx, certbot, Node.js 24, [uv](https://docs.astral.sh/uv/),
the model repositories under `MODELS_ROOT`, and the conda environments under `CONDA_ROOT/envs`.

1. **Configuration**

   ```bash
   python3 scripts/init_env.py --production --app-domain app.example.com --media-domain media.example.com
   ```

   Then fill in `SUPERADMIN_*`, SMTP, `TOSS_*`, `STRIPE_*`, `TURNSTILE_*`, and set
   `SML_WORKER_SIMULATE=0`. Keep a copy of `.env` in your password manager: `FIELD_ENCRYPTION_KEY`
   and `API_KEY_PEPPER` cannot be recovered (see *Secrets* below).

2. **Infrastructure**

   ```bash
   docker compose -f deploy/compose/docker-compose.yml --env-file .env up -d
   ```

3. **Build, migrate, seed**

   ```bash
   deploy/release.sh      # the final restart step fails harmlessly until step 4 installs the units
   cd apps/api && set -a && . ../../.env && set +a && .venv/bin/python manage.py create_superadmin
   ```

   Sign in as the super admin right away and enrol an authenticator app (staff roles cannot use
   the admin console until they do). Then remove `SUPERADMIN_PASSWORD` from `.env`.

4. **Services**

   ```bash
   sudo GPUS="0 3" deploy/systemd/install.sh
   sudo systemctl start sml.target sml-worker@0 sml-worker@3
   ```

5. **nginx and TLS**: edit the two `server_name` values and certificate paths in
   `deploy/nginx/sml.conf`, obtain certificates (`sudo certbot certonly --nginx -d app.example.com
   -d media.example.com`), link the file into `/etc/nginx/sites-enabled/`, `sudo nginx -t`,
   `sudo systemctl reload nginx`.

6. **Payment providers**
   - Stripe: add a webhook endpoint `https://app.example.com/api/v1/billing/webhooks/stripe` for
     `checkout.session.completed`, `invoice.paid`, `invoice.payment_failed`,
     `customer.subscription.updated`, `customer.subscription.deleted`, `charge.refunded`, and put
     its signing secret in `STRIPE_WEBHOOK_SECRET`.
   - Toss Payments: register `https://app.example.com/api/v1/billing/webhooks/toss` for payment
     status changes. Card payments are confirmed server-to-server on return, so the webhook is a
     safety net for cancellations and delayed results.

7. **Smoke test**: `curl https://app.example.com/api/readyz` shows database, redis and broker
   `ok`; sign up with a real address, verify the email, run an image through Detect, and buy the
   smallest pack in test mode before switching the keys to live.

## Releasing a new version

```bash
git pull
deploy/release.sh
```

The script installs locked dependencies, runs `check --deploy`, migrates, collects static files,
re-applies roles/prices/broker policy (idempotent; admin edits are preserved), builds the web
app and restarts the services. Model workers finish running detections before they restart.
Write migrations so the previous release keeps working against the new schema.

## Configuration

Every setting is documented in `.env.example`. Runtime business settings (prices, free credits,
trial allowance, retention, engines, maintenance mode, announcement) are edited in
**Admin → Pricing / Settings** and take effect immediately; they are not environment variables.

## Monitoring

- `GET /api/healthz` (process up) and `GET /api/readyz` (database, Redis, broker).
- **Admin → Overview → System health** (refreshes every 15 s): database, Redis, task queue,
  file storage, long-video service and AI model server; each detector GPU with memory in use,
  running tasks, tasks waiting for memory and reserved memory; the long-video GPU; the loaded
  Ollama model; and settings that still need attention before launch (email delivery, payment
  keys in test mode, CAPTCHA, debug). Backed by `GET /api/v1/admin/system` (`view_system`).
- **Admin → Queues**: depth and consumers per queue, the oldest waiting task, and workers with
  GPU temperature, utilisation and memory. **Admin → Overview**: jobs, failures and revenue.
- Logs: `journalctl -u sml-api -u sml-celery -u sml-worker@0 -f`. Production logs are JSON and
  carry the request id that users see in error messages.
- RabbitMQ management UI: `ssh -L 55673:127.0.0.1:55673 server`, then http://localhost:55673.
- The audit log (**Admin → Audit log**) records logins, MFA changes, role, credit, price and
  settings changes, refunds and API-key events.

## Backups

| What | How | Frequency |
| --- | --- | --- |
| PostgreSQL | `docker compose -f deploy/compose/docker-compose.yml exec -T postgres pg_dump -U sml -Fc sml > /backup/sml-$(date +%F).dump` | daily, keep 30 |
| Object storage | `aws --endpoint-url http://127.0.0.1:58333 s3 sync s3://sml-media /backup/media` | daily |
| `.env` | password manager / sealed copy | on change |

Restore: stop the services, `pg_restore --clean -d sml` into the compose Postgres, sync the
bucket back, start the services. Media older than its retention period is deleted by design,
so a restore can reference files that no longer exist; affected jobs show as purged.

## Runbooks

**Choosing what runs.** Admin → Models: per detector, *Images* and *Videos* switch whether it runs
on every job of that type (the cards above the table show how many run; a type with none is
refused with a generic message). *Category* puts a detector in the face-swap or the AI-generation
analysis: users see one result per analysis (never how many detectors it combines), and the file is
flagged when any analysis says fake. *Heatmap* chooses whose heatmap users see (one image per
detector, its main blended map; Center by default). The cards below choose the extra checks every
job runs (face detection, content safety, anti-spoofing; metadata / C2PA always runs), the
long-form detector, and face cropping for each long-form detector that supports it. Users never see detector names, counts or logs (ADR 0011); per-task results,
logs and errors are in Admin → Jobs → the job.

**Seeing each detector's answer.** On a result page, administrators (capability `view_all_jobs`)
get a *Detector breakdown* card under Analysis Result: every detector's verdict and probability,
the weight it got, its run time and GPU, its heatmap (with `view_all_media`), its per-frame curve
for videos, and its benchmark and measured accuracy. Users never get the card or its endpoint
(`/api/v1/admin/jobs/{id}/detectors`).

**Measuring accuracy.** On the same card, *Ground truth* labels what the file really is (authentic,
face swap, AI-generated; capability `manage_models`). Admin → Models → *Accuracy and weighting* then
shows, per detector, accuracy, AUC, precision and recall over the labelled files: face-swap
detectors are measured on files labelled authentic or face swap, AI-generation detectors on files
labelled authentic or AI-generated, at the platform's fake threshold; files without a face do not
count. The same card holds the benchmark figures you enter from each detector's paper.

**Trusting a detector's "authentic".** *Authentic ×* multiplies a detector's weight when it says
authentic (score below the threshold); *Authentic counts in both* adds that answer to the other
analysis too, but only alongside that analysis's own detectors. SKKU-P2 is set to 2× in both
(owner, 2026-10-01; `config/models.yaml`). Verdicts and video timelines use the same rule; jobs that
already finished keep their result.

**AI-generation markers (EXIEF).** The metadata check runs ExifTool (from the `meta_data` conda env,
or `EXIFTOOL_PATH`) and scores every tag with EXIEF, the owner's signal set copied into
`apps/worker/sml_worker/exief` (to update it, copy `signals.py` and `pipeline.py` from
`~/exief_signals/aigc-studio/server/analyzer` over the copies unchanged and restart the workers). Its
verdict is a weighted vote in the AI-generation analysis: confirmed counts as 100 % fake, suspect 80 %,
weak 60 %, and "no signal" adds nothing, because stripped metadata proves nothing. The weight (default 3,
relative to one detector of weight 1; 0 turns it off) is under Admin → Models → *Checks on every job*. It
is not counted when the metadata is damaged or altered: an ExifTool error or corruption warning, or a C2PA
manifest whose `validation_state` is Invalid (a signer that is merely not on c2patool's trust list, like
OpenAI's, is still valid). Admins see what EXIEF found on the result page and its measured accuracy on
Admin → Models. Invisible pixel watermarks are not decoded.

**Anti-spoofing check fails with CONFIG_ERROR.** The `CVPR24-FAS` code and weights are not on this
server (`run_fas_analysis.py` looks in `fakedetector/fakedetector/CVPR24-FAS`). Leave the check off
in Admin → Models until they are copied there.

**Heatmaps of SKKU-P2, SKKU-P3 and XB-DFD are their predicted masks** (owner, 2026-10-01), labelled
"Predicted mask": P2/P3 show each pixel's probability of a fake class from their class masks (fixed 0-1
scale), XB-DFD its decoder's manipulation mask on the face (fixed 0-0.5 scale). Blue is untouched, red
manipulated; nothing is stretched per image, so authentic files stay mostly blue. The edits to the model
scripts are listed in `~/fakedetector/path-migration-20260930/README.txt` (originals backed up there).

**Resident models (kept loaded on the GPUs).** `python -m sml_worker --resident` (started by
`scripts/dev.sh` and `sml-resident.service`) runs one server per script listed under `resident` in
`config/models.yaml`, in the model's conda env on the listed GPU, loads its weights once and keeps them.
A task still launches the model exactly as before; the launch of that script is handed to its server
(`sml_worker/resident/hook/sitecustomize.py`), so the wrappers, output files and scores are unchanged,
and resident runs skip GPU admission. Placement today: SKKU-P2 and Center on GPU 0, SKKU-AIGC on GPU 1 (only
its env runs on the RTX PRO 6000), SKKU-P3 on GPU 2, XB-DFD and SKKU-SNET on GPU 3. Admin → Models shows
"Loaded on GPU n" per detector. A server that is loading, down or restarting is skipped: its model loads
per task until it is back. A server runs one task at a time; a run that exceeds the model's time limit
(plus 2 minutes) restarts it, and a canceled task still finishes inside it. Logs:
`var/log/resident.log` and `var/log/resident-<server>.log`. After changing a model's code or weights, restart
the resident service.

**Starting and restarting the background services.** `apps/worker/run_services.sh` stops any running
copy of each service, then starts the Celery API worker (`apps/api/run_celery_api.sh`), the detector
workers (`GPUS`, default "0 3"), the agents, the resident supervisor (detectors + image studio server),
the studio worker and the long-form stream service, each detached and logging to `var/log/`. Run it
again at any time: nothing ever runs twice (the resident supervisor also refuses to start a second
copy). `run_services.sh workers` restarts only the workers after a code change, keeping the loaded
models; `run_services.sh stop` stops everything. A task that arrives while its model's resident server
is still loading waits for it (up to 15 min) instead of loading a second copy, which would not fit on
the GPU (`GPU_OOM`). Canceling a job also stops its run inside a resident server.

**Video frame budget.** SKKU-P2, SKKU-P3 and Center score at most 128 frames per video, spread evenly
(owner, 2026-10-02; `env: {FAKEDETECTOR_VIDEO_MAX_FRAMES: "128"}` in their video blocks of
`config/models.yaml`; XB-DFD uses the same budget). Scoring every frame took about 20 minutes per minute
of video for SKKU-P2 and held up every other job waiting for that model.

**Image studio (ADR 0012).** Two processes: the studio server (started by the resident supervisor
above, log `var/log/resident-studio.log`) and the studio worker (`python -m sml_worker --studio
--concurrency 2`, `sml-studio.service`, log `var/log/studio.log`). The server needs the `imagegen`
conda env and the model weights in the Hugging Face cache of the service user:

```bash
conda create -y -n imagegen python=3.12
~/anaconda3/envs/imagegen/bin/python -m pip install --index-url https://download.pytorch.org/whl/cu128 torch torchvision
~/anaconda3/envs/imagegen/bin/python -m pip install "git+https://github.com/huggingface/diffusers" "transformers>=5.17" \
    accelerate safetensors sentencepiece protobuf pillow timm insightface onnxruntime
for repo in Qwen/Qwen-Image-2512 Qwen/Qwen-Image-Edit-2511 Qwen/Qwen-Image-2.1 black-forest-labs/FLUX.2-klein-4B; do
  hf download "$repo"; done   # ~155 GB in total
```

Diffusers comes from source until a release includes `QwenImage21Pipeline`. Admin → Studio picks the
model per mode, shows what is loaded, free GPU memory and which models are installed; prices are on
Admin → Pricing (`studio_generate`, `studio_edit`). Models, controls, the GPU, the memory budget and the
safety thresholds are in `config/studio.yaml` (restart the resident service after editing it). Failure
codes users see: `PROMPT_BLOCKED`, `INPUT_BLOCKED` and `OUTPUT_BLOCKED` (content filter),
`CONSENT_REQUIRED` (a reference shows a face and consent was not confirmed), `SAFETY_UNAVAILABLE` (Ollama
did not answer the prompt check: the studio fails closed), `STUDIO_UNAVAILABLE` (server not running),
`MODEL_UNAVAILABLE` (weights missing), `GPU_OOM`. None is charged. If GPU 1 is short of memory, check
`nvidia-smi` for other processes (Ollama keeps its model loaded) before lowering `memory_budget_gb`.
Qwen-Image-2.1 is licensed for research only: buy a commercial license or switch models before charging
real customers for it.

**Finished tasks run again, or a worker logs `PRECONDITION_FAILED - delivery acknowledgement …
timed out` and shuts down.** Workers acknowledge a task when it ends, and RabbitMQ's default limit is
30 minutes; a long detector run (or a long wait for GPU memory) exceeds it, the broker closes the
channel and re-queues everything that worker held. `manage.py setup_broker` raises the limit to 24 h
on every `sml.*` queue (run it after recreating RabbitMQ). Workers also skip a delivery whose attempt
already has a final result.

**Video detectors fail right after starting.** Usually the environment: a conda env copied from
another machine (`SSL: CERTIFICATE_VERIFY_FAILED`; the worker sets `SSL_CERT_FILE` to the env's
own bundle), dlib missing `libopenblas.so.0` / `libcublas.so.12` (add the env to `conda_envs` in
`config/models.yaml` with `LD_LIBRARY_PATH: "{env_prefix}/lib"`), `undefined symbol:
cublasSetEnvironmentMode` (the env's lib/ has newer CUDA libraries than PyTorch: put PyTorch's
`site-packages/nvidia/*/lib` folders first, as for BEYBI), or weights a script downloads at
first use (`auxillary/*.pth`, `insightface/models/antelopev2/models/buffalo_l/*.onnx` in the models
root). The task's `error_detail` in Admin → Jobs shows the last stderr lines.

**A task stays "running" although the worker finished it.** The API did not record the result
message (for example a migration ran while the old API Celery worker was still up). Recording
retries for about an hour, and every minute `requeue_stale` replays the copy the worker keeps in
Redis (`sml:task-result:<task id>`, 24 h) once it is a minute old, so the job completes on its own.
Deploy order: migrate, then restart `sml-celery` and the workers straight away (`deploy/release.sh`).
Restarting a model worker is safe at any time: the tasks it was running or waiting to start go back
to the queue (they restart from the beginning on the next worker) and their model processes are
stopped.

**A video model waits for "20 GB free".** Admission reserves a model's highest observed GPU memory
for that media type (×1.25, capped at the card): Xception once used 19 GB on a long video, so its
video runs take the whole card and run alone. To re-measure after a fix:
`redis-cli HDEL sml:gpu-model-peak model:xception:video`.

**Jobs wait in the queue for a long time.** Admin → Queues: if a model queue has messages but
0 consumers, check `systemctl status sml-worker@<gpu>` and `nvidia-smi`. Running tasks whose
worker stopped sending heartbeats fail after the model's timeout plus five minutes and are
retried once; tasks no worker picked up within `STALE_DISPATCH_HOURS` (24 h) fail. Users are
never charged for failures.

**Tasks wait with "Waiting for GPU memory".** Expected while the card is full; they start as
others finish. Reservations: `redis-cli HGETALL sml:gpu-reservations:<host>:<gpu>`; learned peaks:
`redis-cli HGETALL sml:gpu-model-peak`. `SML_GPU_MARGIN_MB` (default 1024) keeps a safety margin;
`SML_WORKER_CONCURRENCY` is only an upper bound. If a model still hits `GPU_OOM`, raise its
`gpu_mem_mb` or delete its learned peak so it is re-measured. `GPU_UNSUPPORTED` means the worker
landed on the Blackwell GPU (or the model cannot fit on the card).

**News / explain-why runs wait.** At most `SML_AGENT_PARALLEL` (default 2) share the loaded model;
`curl localhost:11434/api/ps` shows what Ollama has loaded.

**Messages in `sml.dead`.** A message the worker rejected (e.g. it could not be decoded).
Inspect it in the RabbitMQ UI. The task itself fails with `QUEUE_TIMEOUT` after
`STALE_DISPATCH_HOURS`, which settles the job and refunds the user.

**A customer paid but has no credits.** Admin → Billing → Payments shows the payment state and
Webhooks shows delivery errors. A payment flagged "Amount mismatch" granted nothing on purpose:
compare with the provider dashboard, then add credits in Admin → Users → the user → Credits
(with a reason; audited) or refund.

**Adding or removing credits.** Admin → Users → the user (or **My account** for your own) →
Credits: choose Add or Remove, the amount and a reason. Added credits can expire after a number
of days. A removal is confirmed first and takes at most the available balance; credits held by
running jobs are not touched. Every change appears in the user's ledger with your name and in
the audit log (`admin.credits_adjusted`). Needs the `grant_credits` capability.

**Blocking a user.** Admin → Users → the row menu (or the user's page) → Block user, with a
reason. The user is signed out everywhere, cannot sign in and their API keys are rejected; data
and credits are kept. Unblock restores access. Nobody can block their own account, and only a
super admin can block another super admin. Filter the list by **Blocked** to review them.

**Refunds.** Admin → Billing → Payments → Refund shows the amount the policy allows; "company
fault" overrides the policy with a full refund. The payment's remaining credits are revoked.

**Audit log shows `credits.ledger_mismatch`.** The nightly audit found a wallet whose buckets no
longer match its ledger, which only happens through direct database edits or a bug. Compare
the user's ledger (Admin → Users → Ledger) with the buckets before correcting via a credit
adjustment.

**Long-form scans fail or stay "waiting".** `curl http://127.0.0.1:8100/stream/health` shows
whether the service is up, busy, and whether SKKU-AIGC is loaded; `journalctl -u sml-stream`.
Scans whose video never arrived are refunded after 60 minutes, scans that stopped reporting
after 20 minutes. The external detectors need `ffmpeg` for range trimming (set
`STREAM_FFMPEG_BIN`, or install ffmpeg system-wide).

**Maintenance.** Admin → Settings → Maintenance mode rejects new writes with 503 and a
Retry-After header; reads, downloads and running jobs continue.

**A staff member lost their second factor.** Another admin with the user-management capability
uses Admin → Users → Reset MFA (audited); the person signs in and enrols again. For the last
super admin: `manage.py shell -c "from allauth.mfa.models import Authenticator;
Authenticator.objects.filter(user__email='x@y').delete()"`, then re-enrol immediately.

**Opening the Django data admin** (`/api/django-admin/`). Superusers only, and only from a
session that passed two-factor authentication; there is no separate password form.

## Secrets

| Secret | Effect of rotating |
| --- | --- |
| `DJANGO_SECRET_KEY` | Everyone is signed out; password-reset links and trial cookies become invalid |
| `API_KEY_PEPPER` | Every API key stops working. Rotate only after a compromise, and tell API customers |
| `FIELD_ENCRYPTION_KEY` | Stored Toss billing keys become unreadable; Toss subscribers must re-register their card |
| Database / Redis / RabbitMQ / S3 credentials | Update `.env`, recreate the containers, restart the services |
| Payment and Turnstile keys | Replace in `.env` and restart `sml-api` and `sml-celery` |

## Scaling out

Everything except the scheduler is stateless and can run more copies. To add GPU hosts, run
only model workers there with the same `.env`, and bind Redis, RabbitMQ and S3 to a private
network interface instead of 127.0.0.1 (with firewall rules) so the new hosts can reach them.
More API throughput: raise `SML_API_WORKERS` or run the API on more hosts behind nginx.
