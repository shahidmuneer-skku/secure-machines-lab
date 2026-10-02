# Architecture decision records

Short records of decisions that shape the code. Each states the context, the decision and its
consequences. Add a new record instead of rewriting an accepted one; mark the old one superseded.

| # | Decision | Status |
| --- | --- | --- |
| [0001](0001-django-backend.md) | Django + DRF for the backend (instead of FastAPI) | Accepted |
| [0002](0002-web-stack-and-contract.md) | Next.js App Router, shadcn/ui, OpenAPI-generated client | Accepted (homepage note superseded by 0013) |
| [0003](0003-object-storage.md) | S3 API for media; SeaweedFS on the single host | Accepted |
| [0004](0004-queues-and-dispatch.md) | Per-model RabbitMQ priority queues fed by a fair dispatcher | Accepted |
| [0005](0005-credit-ledger.md) | Credits as expiring buckets, holds and an append-only ledger | Accepted |
| [0006](0006-charging-rule.md) | Flat price per file, charged only when a model produced a score | Accepted |
| [0007](0007-payment-providers.md) | One provider interface; grants only from server-verified payments | Accepted |
| [0008](0008-model-workers.md) | Django-free workers running existing model scripts as subprocesses | Accepted |
| [0009](0009-authentication.md) | Sessions for browsers, API keys for machines, MFA for staff | Accepted |
| [0010](0010-long-form-streaming.md) | Long-form video streamed to a GPU service, charged per minute analysed | Accepted |
| [0011](0011-detectors-are-not-disclosed.md) | Users never see which detectors run; the admin chooses them | Accepted |
| [0012](0012-image-studio.md) | Image studio: generation and editing with the admin's model | Accepted |
| [0013](0013-design-system.md) | Material UI (Modernize) with shadcn/ui; dark theme by default (updated) | Accepted (homepage part superseded by 0014) |
| [0014](0014-3d-scan-homepage.md) | 3D scan homepage; previous design kept at /landing-legacy | Accepted |
