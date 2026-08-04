# Architecture

## Runtime shape

The application is a modular monolith: React calls one FastAPI application,
which owns application services, provider adapters, and PostgreSQL persistence.
A separate process imports the same backend modules to process durable research
updates. This keeps deployment and debugging simple for personal scale while
preserving boundaries that could later be split.

```text
Browser -> React/Vite -> FastAPI routes -> application services
                                      -> domain calculations
                                      -> repositories -> PostgreSQL
                                      -> provider contracts -> Upstox

Weekday schedule -> nightly selector -> durable update rows -> research runner
```

## Backend boundaries

- `app/api`: HTTP validation, authentication dependencies, and status mapping.
- `app/services`: use cases and transaction coordination.
- `app/domain`: pure technical calculations and historical evaluation.
- `app/repositories`: SQLAlchemy queries and persistence operations.
- `app/providers`: typed contracts and Upstox response validation.
- `app/models`: relational structure and database invariants.
- `app/scripts`: executable API, scan, processing, demo, and report commands.

Routes do not calculate indicators or parse provider payloads. Provider code
does not decide database transactions. This separation keeps tests focused and
prevents an external response shape from becoming the domain model.

## Core relationships

```text
Company 1 --- * Instrument 1 --- * DailyCandle
                         | 1 --- * ProviderInstrumentIdentity
                         | 1 --- * AnalysisSnapshot
                         | 1 --- * FundamentalSnapshot
                         | 1 --- * FundamentalPeriod
                         | 1 --- 1 TrackedInstrument 1 --- * AnalysisJob

AppUser 1 --- * UserSession
AppUser 1 --- * UserWatchlistItem * --- 1 Instrument
```

`Company` is the business; `Instrument` is an exchange-listed security. Names
and symbols can change, so provider/ISIN identity is effective-dated instead of
being treated as the primary key. Watchlist membership is separate from stored
research, allowing reversible removal for normal users. `TrackedInstrument` is
shared while at least one normal-user membership remains. Administrator removal
is intentionally different: deleting the instrument cascades through every
membership and instrument-owned research row, then removes an orphan company.

## Market-data lifecycle

1. The backend resolves the latest completed NSE session, then probes Nifty 500
   once to determine whether Upstox Historical V3 has finalized it. After close,
   Intraday V3's daily candle is the temporary fallback if history is delayed.
2. Adding a company creates/reactivates the user's membership. Shared tracking
   is created or reactivated only when the instrument is not already active.
3. The runner claims one eligible row with `FOR UPDATE SKIP LOCKED`.
4. It loads the current provider identity and fetches only missing
   expected-session ranges.
5. Complete session history is validated before technical calculation. A
   temporary `UPSTOX_INTRADAY` daily row is replaced by `UPSTOX` history when
   the finalized candle becomes available.
6. A new immutable analysis row becomes the latest valid result.

Corporate actions are handled manually: an administrator permanently deletes
the affected instrument and adds it again, producing a new identity and complete
history fetch. The app does not fetch or persist corporate-action events.

An analysis job persists whether it is a technical refresh, fundamental refresh,
or stored-data algorithm run. Admin **Fetch technical data** jobs follow the
market lifecycle above and never request fundamentals. Admin **Fetch fundamental
data** jobs request and persist only company fundamentals; their failure does not
replace a valid technical operational state. Admin **Re-run algorithm** jobs skip
all provider calls and calculate only from complete stored stock and benchmark
candles. The scheduled 4:00 PM scan uses only the technical path. Job intent is
durable across worker restarts. A technical rule change must also change
`algorithm_version` so a new immutable result is distinguishable
from the prior calculation over the same candle revision.

`analysis_jobs` contains only active queue work. A row survives while pending,
running, or waiting for a bounded retry, then is deleted after success, terminal
failure, retry exhaustion, or cancellation. Successful-session idempotency comes
from immutable analysis snapshots. The tracking row keeps only the latest
terminal technical data-quality session and code, which prevents duplicate work
without retaining job history.

The stock-list read model starts from active tracked instruments rather than
analysis snapshots. This keeps a terminally failed or still-preparing company
visible without fabricating a technical result. Analysis-dependent fields are
nullable for those rows, and operational failures sort after all analyzed
technical statuses when the user selects status sorting.

Network calls occur outside long database transactions. Short claim/finalize
transactions reduce lock contention and allow safe cancellation.

The Upstox adapter uses a keyed request-start limiter. Calls to the same API
family honor the configured requests-per-second value, but different API
families do not block one another. Each permit is reserved in PostgreSQL under
a row lock, so all API and worker replicas sharing an Upstox credential obey
one combined rate. With the default of one request per second, one API family
can start at most 1,800 requests in 30 minutes, below Upstox's documented 2,000
limit. Telegram sends use the same shared mechanism. Telegram update polling is
a singleton operation protected by a PostgreSQL advisory lease; another worker
can take over as soon as the owning database session ends.

Worker startup scheduling is an explicit runtime policy. With
`WORKER_SCHEDULE_ON_STARTUP=false`, startup recovers stale jobs and processes
the durable queue but does not probe market availability or enqueue catch-up
work. Enabling it restores automatic latest-session catch-up without changing
manual admin refresh behavior.

Telegram setup alerts use a transactional outbox. When a newly inserted
analysis snapshot differs meaningfully from its predecessor, the same database
transaction inserts one recipient row for each connected user actively
following that instrument. New or reactivated memberships keep a pending first
fresh-analysis decision: an available non-`NO_SETUP` snapshot queues a distinct
watchlist-added event, while `NO_SETUP` consumes it silently. The worker renders PNGs from immutable chart
evidence after commit and uploads them through Telegram's Bot API. Delivery is
paced, deduplicated by `(user_id, analysis_snapshot_id)`, retried independently,
and never changes technical-analysis success. A short-lived hashed deep-link
token binds a Telegram `/start` update to an application user; the browser
never supplies the numeric chat ID. A durable update offset prevents replay.
Delivery rechecks that the recipient still has an active membership for the
snapshot's instrument; removal during queue delay discards the alert.

First-time Upstox identity creation takes a transaction-scoped advisory lock
derived from provider and ISIN. Instrument-row locks then serialize shared
tracking activation, so concurrent users create separate memberships but only
one tracking row and one active job per job type.

Technical scheduling treats the latest `INSUFFICIENT_LISTING_HISTORY` or
`PERSISTENT_CANDLE_GAPS` result as terminal for the same instrument and target
session. A repeated manual or scheduled scan does not create duplicate work for
that date, but the next completed session remains eligible. A successful Upstox
gap request that still omits internal NSE sessions is persistent: returned
candles are preserved, analysis is refused, and the job is not retried.

## Frontend structure

React Router owns the list/detail routes. TanStack Query owns server state,
caching, refetching, and mutations. Axios provides one `/api` client and adds
the readable CSRF cookie only to mutating requests. Component-local state is
used for forms and announcements; Redux would add complexity without a current
cross-application state problem.

Backend enum names stay stable at the API boundary. Components map them to
market language such as “Checking latest session” and “Research ready.”

## Security model

- List/detail reads require a signed-in user and active membership. Personal
  mutations require that user's session and matching CSRF cookie/header; global
  refresh and destructive instrument deletion remain administrator-only.
- The opaque session cookie is HttpOnly; PostgreSQL stores only its SHA-256
  digest. The CSRF cookie is intentionally readable by the same-origin client.
- Password verification uses Argon2. The administrator hash is configured by
  environment; normal-user hashes are stored in PostgreSQL.
- Trusted hosts, exact-origin CORS, request-size limits, defensive headers, and
  disabled production API docs reduce exposed attack surface.
- Upstox, Telegram, database, and administrator credentials exist only in
  backend/runtime secret stores.
- Provider error bodies and arbitrary exceptions are not persisted or returned.

## Scaling path

API and worker replicas can be added without assigning instruments to a
specific process. Durable jobs and notification rows use `FOR UPDATE SKIP
LOCKED`, active-job and immutable-result uniqueness enforce idempotency, shared
provider limit rows serialize outbound request starts, and advisory leases
protect singleton polling. Every authenticated request updates user activity at
most once per 15 minutes to avoid turning analytics into a write hot spot.

The admin analytics read model reports registration/activity windows, Telegram
connections, tracked-stock memberships, current setup distribution, and queue
state. Optional Prometheus HTTP counters, duration histograms, and in-progress
gauges use route templates rather than IDs, preventing unbounded label growth.
See `SCALING.md` for replica and database-connection budgets.

At much larger scale, measurements may justify partitioning instruments,
external queue infrastructure, or precomputed analytics. Those are not needed
for the current modular monolith and are not introduced speculatively.
