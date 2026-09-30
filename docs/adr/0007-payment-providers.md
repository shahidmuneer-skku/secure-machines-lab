# 0007 · One provider interface; grants only from server-verified payments

**Context.** Korean customers pay with Toss Payments (KRW), international customers with Stripe
(USD). Both packs (one-off) and subscriptions are sold.

**Decision.** A `PaymentProvider` interface (`sml/billing/providers/base.py`) with Toss, Stripe
and a development-only mock. Orders and amounts are created on the server. Credits are granted
only from verified payments: Stripe webhooks are signature-checked and the object is re-fetched
from Stripe; Toss payments are confirmed server-to-server and Toss webhooks are re-fetched too.
Webhooks are de-duplicated by event id, grants are idempotent per payment, and an amount or
currency mismatch is flagged for review and grants nothing. Toss billing keys are encrypted at
rest. Hosted checkout pages are used, so card data never reaches our servers.

**Consequences.** Adding a provider means implementing one class. Browser redirects are never
trusted as proof of payment, which makes return pages poll briefly for Stripe. PCI scope stays
at the SAQ-A level.
