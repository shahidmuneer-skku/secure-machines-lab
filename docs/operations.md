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
| Model worker on GPU *n* | `sml-worker@n` | — |
| Infrastructure | `docker compose` (restart: unless-stopped) | 127.0.0.1:55432 / 56379 / 55672 / 55673 / 58333 |

GPU note for this server: GPUs 0, 2 and 3 are RTX A5000s and run the model workers; GPU 1
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
   sudo GPUS="0 2 3" deploy/systemd/install.sh
   sudo systemctl start sml.target sml-worker@0 sml-worker@2 sml-worker@3
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

**Jobs wait in the queue for a long time.** Admin → Queues: if a model queue has messages but
0 consumers, check `systemctl status sml-worker@<gpu>` and `nvidia-smi`. Running tasks whose
worker stopped sending heartbeats fail after the model's timeout plus five minutes and are
retried once; tasks no worker picked up within `STALE_DISPATCH_HOURS` (24 h) fail. Users are
never charged for failures.

**A model fails with `GPU_OOM`.** Lower `SML_WORKER_CONCURRENCY` for that host, or dedicate a
worker to the heavy model: `python -m sml_worker --models <id> --gpu <n>` (a separate unit
with a different `--name`). `GPU_UNSUPPORTED` means the worker landed on the Blackwell GPU.

**Messages in `sml.dead`.** A message the worker rejected (e.g. it could not be decoded).
Inspect it in the RabbitMQ UI. The task itself fails with `QUEUE_TIMEOUT` after
`STALE_DISPATCH_HOURS`, which settles the job and refunds the user.

**A customer paid but has no credits.** Admin → Billing → Payments shows the payment state and
Webhooks shows delivery errors. A payment flagged "Amount mismatch" granted nothing on purpose:
compare with the provider dashboard, then grant credits in Admin → Users → the user → Credits
(with a reason; audited) or refund.

**Refunds.** Admin → Billing → Payments → Refund shows the amount the policy allows; "company
fault" overrides the policy with a full refund. The payment's remaining credits are revoked.

**Audit log shows `credits.ledger_mismatch`.** The nightly audit found a wallet whose buckets no
longer match its ledger, which only happens through direct database edits or a bug. Compare
the user's ledger (Admin → Users → Ledger) with the buckets before correcting via a credit
adjustment.

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
