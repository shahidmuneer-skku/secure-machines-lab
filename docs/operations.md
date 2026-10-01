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

**AI-generation markers.** A definite marker in the file's metadata (C2PA / IPTC declaration,
embedded Stable Diffusion / ComfyUI parameters, a generator in the Software tag) labels the file
"Likely AI-generated" whatever the detectors say; a weak hint (a generator merely mentioned in the
metadata) does so only when the detectors judged the file fake. Invisible pixel watermarks are not
decoded.

**Anti-spoofing check fails with CONFIG_ERROR.** The `CVPR24-FAS` code and weights are not on this
server (`run_fas_analysis.py` looks in `fakedetector/fakedetector/CVPR24-FAS`). Leave the check off
in Admin → Models until they are copied there.

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
