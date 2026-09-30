# Secure Machines Lab platform: build plan

Source spec: `~/fakedetector/fakedetector/instructions.md`. Where the owner's answers
(2026-09-30) differ from the spec, the owner's answers win. They are recorded in
`docs/decisions/`.

## Confirmed decisions (owner)

| Area | Decision |
|---|---|
| Backend | Django 5.2 LTS, DRF, drf-spectacular, django-allauth headless (sessions, MFA TOTP + WebAuthn passkeys), Argon2id, Celery on RabbitMQ, Redis |
| Frontend | Next.js 16 (App Router) + React 19 + Tailwind v4 + shadcn/ui (Radix) + lucide + TanStack Query + react-hook-form + zod; homepage copied from `dash-lab-website-production` |
| Infra | Docker Compose: PostgreSQL 16, Redis 7, RabbitMQ 3.13, MinIO |
| Models | Real conda envs will be copied to `~/anaconda3/envs/<legacy name>`; a simulated adapter is used until then |
| Media | Images, videos, long-form video, news verification. **No text detection.** |
| Credits | One credit currency; flat price per file, independent of the models chosen; signup bonus + daily free top-up (no carry-over); expiry set by admin per source; guest trial count set by admin (images only) |
| Payments | Toss Payments (KRW) + Stripe (USD) behind one `PaymentProvider` interface; credit packs **and** monthly subscriptions; credits granted only after server-side verification |
| Reasoning | On-demand "Explain why" button using OpenClaude/Qwen; credit cost set by admin |
| News engine | Admin-selectable: local OpenClaude/Qwen or Claude (Anthropic) |
| Modules | Long-form video + news verification ported into the unified worker system |
| Roles | super_admin, admin, billing_admin, support, user (+ guest). Orgs later (schema-ready) |
| v1 scope | MFA, developer API keys, reports (PDF/HWP/CSV), audit chain + XAI |
| i18n | EN + KO + DE |
| Email | SMTP (console backend until creds are provided) |
| Approval | No admin approval; email verification only |
| Model variants | Models with separate deepfake / AI-gen weights are separate selectable variants |
| Retention | Set by admin per plan |
| Deploy | Dev + production config (nginx, systemd, compose) |

### Seed defaults (all admin-editable)
- Guest trial: 3 images/day. Signup bonus: 50 cr (expires in 30 days). Daily free: 10 cr (resets at 00:00 KST).
- Image 1 cr. Video 10 cr up to 1 min, +5 cr per extra started minute. Long-form video 4 cr/min. News case 15 cr. Explain-why 3 cr. Reports free.
- Packs: Starter 100 cr ₩15,000 / $12; Standard 500 cr ₩59,000 / $45; Pro 2,000 cr ₩199,000 / $150 (12-month expiry).
- Plans: Basic 300 cr/mo ₩35,000 / $27 (normal queue, 14 d retention); Pro 1,000 cr/mo ₩99,000 / $75 (priority, 30 d, API);
  Business 5,000 cr/mo ₩399,000 / $299 (highest priority, 90 d). Free-tier retention 7 d.

## Repository layout

```
apps/api       Django project (package `sml`): REST API, auth, RBAC, credits, billing, jobs, SSE
apps/worker    `sml_worker`: Django-free Celery worker runtime + model adapters (fake, subprocess, warm)
apps/web       Next.js frontend (marketing, /login, /app/*, /admin/*, /docs)
config         models.yaml (model registry), roles.yaml (RBAC seed)
deploy         docker-compose (infra), nginx, systemd units
docs           architecture, ADRs, runbooks, API guides, progress notes
packages/contracts  OpenAPI schema + generated TypeScript types
```

## Milestones

1. **Foundation**: repo, compose, Django + Next shells, design tokens, CI config
2. **Auth & RBAC**: /login, signup, verify, reset, sessions, CSRF, MFA (TOTP + passkeys), roles, audit log
3. **API keys**: create/scope/expire/IP-allowlist/rotate/revoke, usage stats, rate limits, Bearer auth
4. **Credits**: wallet, buckets, ledger, reserve/capture/release, daily grant, signup bonus, pricing, quote
5. **Jobs & scheduling**: uploads (presigned + direct), model registry, Celery topology, dispatcher with fairness,
   worker + fake adapter, aggregation, EXIF/C2PA AI indicators, SSE progress, results/history UI
6. **Real models**: subprocess adapters for every model/variant (activate when envs exist), audit chain, XAI
7. **Payments**: Toss + Stripe adapters (test mode), packs, subscriptions, webhooks, invoices
8. **Reports**: PDF / HWP (RTF) / CSV in EN/KO/DE
9. **Reasoning + modules**: Explain-why (OpenClaude), long-form video, news verification
10. **Dashboards**: user dashboard, admin (users, roles, pricing, packs/plans, queues, models, GPUs, audit log, settings)
11. **Docs & hardening**: OpenAPI, developer portal, runbooks, deploy configs, tests

## Open questions / waiting on owner
- [ ] Add user to `docker` group (`sudo usermod -aG docker shahidmuneer`)
- [ ] Copy conda envs to `~/anaconda3/envs/`
- [ ] SMTP credentials, Toss + Stripe test keys, Turnstile keys, production domain/TLS details
- [ ] Anthropic API key (only if the Claude news engine is selected)

## Status
See `CHANGELOG.md` and `docs/progress/`.
