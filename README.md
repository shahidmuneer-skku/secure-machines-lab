# Secure Machines Lab platform

Deepfake and AI-generated media detection as a service: users upload images and videos,
watch the analysis run live, and get one combined verdict with heatmaps, provenance metadata and
downloadable reports. Administrators choose which detectors run; users never see them (ADR 0011). Credits are bought
with Toss Payments or Stripe and spent per file; administrators set prices, packages, free
allowances and access per user.

| Module | What it does |
| --- | --- |
| Detect | Images and videos in one drop zone; admin-chosen detectors per media type; weighted verdict; EXIF / XMP / C2PA markers flag AI generation; heatmaps and face maps |
| Long-form video | Interval-by-interval scoring of long videos |
| News verification | An agent investigates a news item (image/video + claim) and writes a sourced case report |
| Explain why | On-demand AI reasoning over a finished result |
| Reports | PDF, HWP (RTF) and CSV reports, ZIP bundles, in EN/KO/DE |
| Queue & history | Position, ETA and progress in generic steps; full job history with retention per plan (detector logs for staff only) |
| Credits & billing | Wallet with expiring buckets and an append-only ledger; packs and subscriptions; refunds by policy |
| API | Scoped, IP-restrictable API keys; OpenAPI docs at `/api/docs` |
| Guest trial | A few free image checks per day before signing up |
| Admin console | Users, roles, access policies, credit grants, jobs, queues/GPUs, models, pricing, payments, API usage, audit log, platform settings |

The UI is available in English, Korean and German.

## Architecture in one paragraph

A **Next.js** app (`apps/web`) talks to a **Django + DRF** API (`apps/api`). Uploads go to
S3-compatible storage. Creating a job reserves credits and writes one task per model; a fair
dispatcher publishes tasks to per-model **RabbitMQ** priority queues. **Model workers**
(`apps/worker`, Django-free Celery) run the existing model scripts from their own conda
environments on pinned GPUs, stream progress through **Redis**, and report results back. The
API combines the results into one verdict, charges or refunds the reserved credits, and pushes
every change to the browser over Server-Sent Events. See [docs/architecture.md](docs/architecture.md).

```
apps/api        Django 5.2 LTS · DRF · allauth (headless, MFA, passkeys) · Celery
apps/worker     Model worker runtime: adapters for subprocess models, metadata/C2PA, agents
apps/web        Next.js 16 · React 19 · Tailwind v4 · shadcn/ui · TanStack Query · next-intl
packages/contracts  OpenAPI schema and generated TypeScript types (npm run gen:api)
config          models.yaml (model registry), roles.yaml (RBAC)
deploy          docker compose (infrastructure), nginx, systemd units
docs            Architecture, operations, adding a model, ADRs
scripts         init_env.py (generate .env), dev.sh (run everything locally)
```

## Quick start (development)

Requirements: Docker, Python with [uv](https://docs.astral.sh/uv/), Node.js 24, and for real
detections the model repositories and conda environments listed in `config/models.yaml`
(missing environments are simulated and flagged as such).

```bash
python3 scripts/init_env.py                 # .env with random secrets (+ apps/web/.env.local)
docker compose -f deploy/compose/docker-compose.yml --env-file .env up -d

cd apps/api
uv sync
uv run python manage.py migrate
uv run python manage.py setup_broker        # dead-letter policy on RabbitMQ
uv run python manage.py bootstrap           # roles, prices, packs, plans (idempotent)
# set SUPERADMIN_EMAIL / SUPERADMIN_PASSWORD in .env first:
uv run python manage.py create_superadmin

(cd ../worker && uv sync) && (cd ../web && npm ci)
cd ../.. && scripts/dev.sh                  # API, background worker, model worker, web
```

Open http://localhost:3000. Emails (verification, password reset) are printed to
`var/log/api.log` until SMTP is configured. Staff accounts must enrol an authenticator app
before the admin console opens.

## Quality checks

```bash
cd apps/api    && uv run ruff check . && uv run pytest          # needs the compose Postgres
cd apps/worker && uv run ruff check sml_worker tests && uv run pytest tests
cd apps/web    && npx eslint . --max-warnings 0 && npx tsc --noEmit && npx vitest run
cd apps/web    && npm run gen:api && git diff --exit-code ../../packages/contracts
# end to end, against a running stack (signed-in tests need an account):
cd apps/web    && E2E_EMAIL=... E2E_PASSWORD=... npm run test:e2e
```

CI runs the same checks (`.github/workflows/ci.yml`).

## Documentation

- [Architecture](docs/architecture.md): components, job lifecycle, credits, queues, security
- [Adding a model](docs/adding-a-model.md)
- [Operations](docs/operations.md): production deployment, configuration, backups, runbooks
- [Decision records](docs/adr/)
- [Changelog](CHANGELOG.md)

## Before launch

The following are placeholders until the owner provides them: company legal details
(`apps/web/lib/company.ts`), SMTP credentials, live Toss and Stripe keys, Cloudflare Turnstile
keys, and the production domains/TLS certificates.
