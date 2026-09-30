# Changelog

All notable changes to this project. The format follows [Keep a Changelog](https://keepachangelog.com/).

## [Unreleased] — first release candidate

### Added
- Detection of images and videos with user-selected models combined into one weighted verdict;
  EXIF / XMP / C2PA AI-generation indicators; Grad-CAM and face maps; optional face, safety and
  anti-spoofing audit steps.
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
- Tests for the API, the model worker and the web app; CI; nginx and systemd deployment files;
  architecture, operations and model-onboarding documentation; decision records.

### Security
- The Django data admin no longer accepts password-only logins; it requires a superuser
  session verified with two-factor authentication.
- API keys cannot raise their own rate limit above the platform limit.
- Payment amount mismatches are persisted and flagged for review.
- Content-Security-Policy with per-request nonces; HSTS; secure cookies; problem-details errors
  without server details.
