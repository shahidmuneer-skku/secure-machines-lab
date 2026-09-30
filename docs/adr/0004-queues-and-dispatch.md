# 0004 · Per-model RabbitMQ priority queues fed by a fair dispatcher

**Context.** Each detection model has its own conda environment and GPU memory needs; some
models are much slower than others. Paying plans must be served first, and one user's batch
must not starve everyone else. Users need a queue position and an ETA.

**Decision.** One queue per model (`sml.model.<id>`), per audit step, and for long-video,
news and reasoning work, all classic queues with `x-max-priority=10`; dead-lettering by a broker
policy (`manage.py setup_broker`). Job tasks are stored in PostgreSQL first (transactional
outbox). A dispatcher, run on every job change and every 5 s, publishes `PENDING` tasks in
priority order under an advisory lock, skipping principals at their in-flight cap. Workers
prefetch one message and acknowledge late.

**Consequences.** Adding a model adds a queue without code changes, and a worker can be
dedicated to a heavy model. Queue state is reconstructible from the database; a sweep fails
tasks whose worker vanished or that were never picked up, so jobs always settle. Priorities are
coarse (plan level), which is enough at this scale; per-tenant weighted fairness would need a
scheduler of its own.
