# Horizontal scaling guide

## What is safe to replicate

FastAPI pods are stateless: sessions, watchlists, jobs, analyses, limiter state,
and user activity live in PostgreSQL. A load balancer can therefore distribute
requests across any healthy API pod without sticky sessions.

Worker pods claim different ready jobs with `FOR UPDATE SKIP LOCKED`. Unique
active-job and immutable-analysis constraints make retries idempotent. The same
pattern protects Telegram outbox delivery. Provider request slots are reserved
transactionally in `distributed_rate_limit_buckets`, so replicas sharing a
credential observe one combined Upstox/Telegram rate. Telegram update polling
uses a session-level advisory lease and automatically fails over when the owning
connection closes.

## Kubernetes runtime rules

- Run one Uvicorn process per API pod. Scale pods rather than Python processes;
  this keeps Prometheus collection simple and gives Kubernetes direct control
  over capacity and restarts.
- Use `/health` for liveness and `/ready` for readiness. Stop routing new calls
  before terminating a pod and allow in-flight requests to drain.
- Run `alembic upgrade head` as one release Job. Do not let every pod race to
  migrate at startup.
- API and worker deployments use the same image and schema version but different
  commands. Workers need no public Service or Ingress.
- Use rolling updates with old and new code compatible with the additive schema.
  Apply migrations before scaling the new version.
- Keep `WORKER_SCHEDULE_ON_STARTUP=false` on replicated workers unless automatic
  catch-up is explicitly wanted. Queue processing itself remains enabled.

## Database connection budget

Each pod owns its SQLAlchemy pool. The hard upper bound is:

```text
API pods * (DATABASE_POOL_SIZE + DATABASE_MAX_OVERFLOW)
+ worker pods * (DATABASE_POOL_SIZE + DATABASE_MAX_OVERFLOW)
+ release jobs, Prometheus checks, and operator reserve
```

Keep that result below PostgreSQL's connection limit with safety margin. Begin
with the local defaults of 5+5 for an API and 3+2 for a worker, then reduce or
increase from observed concurrency. `DATABASE_POOL_TIMEOUT_SECONDS` bounds how
long overload waits for a connection instead of hanging indefinitely. A managed
pooler can be added later if measurements show connection churn or limits are
the bottleneck.

## Metrics and alerts

Enable `METRICS_ENABLED` and store `METRICS_BEARER_TOKEN` as a Kubernetes Secret.
Scrape every API pod directly; Prometheus performs cross-pod aggregation. Do not
put the token in frontend configuration. Recommended initial alerts are sustained
5xx rate, p95 duration, readiness failure, a growing ready-job count, old pending
work, and database connection saturation.

The `/admin/analytics` dashboard is a current database snapshot for product and
queue questions. `/metrics` is the time-series source for latency, throughput,
errors, and alerting. They intentionally serve different purposes.

## Remaining scale limits

PostgreSQL is both the durable queue and coordination service. This is the right
tradeoff for the current modular monolith, but very high job throughput could
eventually make queue polling or limiter-row contention measurable. Upstox's
provider allowance is also a hard throughput ceiling no number of workers can
raise. Add an external queue, partitioned limiter, or precomputed analytics only
after metrics identify one of those as the actual bottleneck.
