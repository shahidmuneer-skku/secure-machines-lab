# 0006 · Flat price per file, charged only when a model produced a score

**Context.** Users choose how many models analyse a file. Some results are "no face found" or
fail on our side (GPU errors, timeouts).

**Decision.** The price depends on the file, not on the models: an image costs a fixed amount, a
video a base amount for the first minute plus a per-minute amount, long-form video per minute,
news verification per case, "explain why" per request (all admin-editable). The quote is
reserved when the job is created. The job is charged only if at least one model produced a
score; otherwise (no face everywhere, failures, cancellation) the hold is released in full.

**Consequences.** Prices are predictable and shown before submission; choosing more models is
encouraged rather than penalised. GPU cost per job varies with the selection, which the plan
in-flight caps and admin model controls keep in check.
