# 0005 · Credits as expiring buckets, holds and an append-only ledger

**Context.** Credits come from several sources with different expiry rules (signup bonus, daily
free credits without carry-over, purchases, subscriptions, admin grants) and are spent by jobs
that may fail minutes later. Balances must never go negative or drift, and every change must be
explainable to users and auditors.

**Decision.** Each grant is a bucket with its own expiry. Spending first **reserves** credits into
a hold, taking from the soonest-expiring buckets, then **captures** or **releases** them when the
job settles; released credits go back to the buckets they came from. Every change appends a
ledger entry with the balance after it. All mutations lock the wallet row; the invariant
sum(ledger) = sum(bucket remaining) is tested (including randomized sequences), enforced partly
by database constraints, and audited nightly.

**Consequences.** Users see exactly what expires when and why credits moved. Failed jobs cost
nothing without special cases. The design is more complex than a single balance column, so all
changes must go through `sml/credits/services.py`.
