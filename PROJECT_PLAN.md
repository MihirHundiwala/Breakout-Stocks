# Breakout Stocks — Project Plan

## 1. Purpose

Build an interview-demonstrable research website for NSE-listed stocks that are
forming or breaking out of consolidations. The application will combine:

- explainable technical screening;
- a broad, explainable set of fundamental data points and comparisons;
- clear company and setup detail views.

This is an end-of-day research tool for swing and position ideas. It is not a
real-time trading system, order-execution platform, or investment-advice engine.

The code should resemble a well-structured project built by a developer with
roughly three years of experience: clean, tested, conventional, and easy to
explain without unnecessary production infrastructure.

Repository workspace:

```text
D:\Mihir\Projects\Breakout-Stocks
```

## 2. Product boundaries

### In scope for V1

- NSE equities with market capitalization above ₹1,000 crore.
- Exclude SME-listed stocks from breakout results.
- Per-user watchlists backed by shared market research. The `admin` account has
  no application-level stock limit; normal users have a configurable active-
  watchlist limit, initially `20` through `NORMAL_USER_WATCHLIST_LIMIT`.
- End-of-day price and volume analysis.
- An explainable technical setup state plus a 0-100 setup-quality score whose
  normalized components are exposed; the score ranks rule quality and is not a
  return prediction or trade recommendation.
- Fundamental data and valuation comparisons available as drill-down research
  rather than compressed into potentially misleading scores.
- One administrator role with unrestricted watchlist size and manual research
  refresh authority, plus normal authenticated users who manage only their own
  limited watchlists.
- Local Docker-based development and integration testing.
- A reliable fixture/snapshot mode for interviews and offline demonstrations.
- Automated tests, architecture notes, and interview-oriented documentation.
- Per-user Telegram notifications when an end-of-day technical setup changes,
  with immutable daily/weekly chart evidence attached. Telegram linking uses a
  one-time bot deep link and verified private chat identity.
- A connected user who newly adds or reactivates a stock receives its first
  fresh non-`NO_SETUP` result as a distinct watchlist-added alert; a fresh
  `NO_SETUP` result consumes that pending decision silently.
- Automatic analysis notifies the stock's connected active followers for every
  setup-status transition, including a prior setup becoming `NO_SETUP`.
  Administrator algorithm-only reruns always remain silent.
- At 8:30 AM IST on an NSE trading day, each connected user receives a text-only
  list of the current non-`NO_SETUP` setups in their watchlist, including close,
  one-session change, resistance, timeframe, setup quality, and analysis date.
  This morning digest is sent directly without an outbox, retry, or catch-up.

### Explicitly out of scope for V1

- Intraday or streaming scans.
- Trade recommendations, order placement, portfolio management, or real-time
  price-triggered alerts.
- Frontend price charts.
- OAuth, email verification, password reset, social login, or team/organization
  management. V1 public signup creates only normal accounts; administrator
  identity remains environment-controlled.
- Automatic scraping of Screener.in, Yahoo Finance, NSE, or BSE webpages.
- Autonomous web-research agents.
- Document uploads, document extraction/OCR, embeddings, semantic retrieval,
  company-specific document Q&A, and AI-generated document research.
- A vector database, LangChain/LlamaIndex, microservices, Kubernetes, Kafka, or
  other infrastructure not justified by a demonstrated requirement.
- Production-grade high availability or a full historical point-in-time NSE
  universe.

## 3. Users and access

### Administrator

The single administrator can:

- sign in;
- add, update, and remove watchlist stocks;
- correct missing fundamentals using source-referenced overrides; and
- trigger onboarding, analysis, and manual scans.

The administrator has an unlimited personal watchlist. “Unlimited” means no
application quota; provider/database performance claims remain limited to the
tested personal workload.

### Normal user

A normal authenticated user can view research for and add/remove companies from
their own watchlist. The active membership count cannot exceed
`NORMAL_USER_WATCHLIST_LIMIT`, initially 20. They cannot manage other users,
change global research data, or trigger a manual market-wide refresh.

### Signed-out visitor

A signed-out visitor can access the login and signup pages plus service health
boundaries but is redirected away from personalized watchlist and
company-research routes.

## 4. Application modes

| Mode | Purpose | Data behavior |
|---|---|---|
| `snapshot` | Dependable interview fallback | Read-only seeded/precomputed results; no external API required |
| `watchlist` | Default personal research mode | Per-user memberships over shared live Upstox research; admin unlimited, normal-user limit configured by environment |
| `universe` | Future scaling path | Scan the broader eligible NSE universe; not a V1 free-hosting target |

Watchlist mode compares momentum with the Nifty 500 benchmark. It must not call
that result a market-wide percentile because user-curated subsets are not valid
cross-sectional market universes regardless of their size.

## 5. Technical screening

The exact thresholds are isolated in the immutable domain configuration and
must be validated by tests and a historical backtest. `technical-v19` is the
only active technical algorithm. `technical-v1` through `technical-v18` rows remain
readable historical results and are never reinterpreted.

Every technical-rule change requires an explicit applicability review for both
daily and weekly analysis. When the underlying concept applies to both
timeframes, both implementations and their regression tests must change
together. Timeframe-specific windows and thresholds may differ because weekly
aggregation changes volatility and structure, but the shared market reasoning
must remain consistent. A one-timeframe change is acceptable only when the
other timeframe is demonstrably inapplicable and that reason is documented.

- Require 252 completed stock sessions and confirmed Stage 2 structure:
  `close > SMA50 > SMA150 > SMA200`, `SMA200 > SMA200.shift(20)`, close at
  least 75% of the 252-session high, close at least 125% of the
  252-session low. A normalized Stage 2 quality component measures the four
  moving-average relationships and proximity to the high. In addition, the
  close distance from the robust 98th-percentile 130-session actual high must
  not exceed 10%.
- Evaluate every base length from 20 through 120 completed sessions using only
  candles before the signal candle. V13 calculates separate body and actual
  high/low ranges after symmetrically
  trimming the outer 5% on each side (one observation per side in a 20-session
  base). For 20-39 sessions their respective body/wick maximums are 12%/16%;
  for 40-79 sessions, 15%/20%; and for 80-120 sessions, 18%/24%.
  Candidate selection uses price structure: base depth, contraction, resistance
  quality, and price position. Candidate windows describing the same resistance
  shelf prefer the longest valid duration; different shelves still compete on
  structural quality so a long prior trend cannot displace the active shelf.
  A candidate is not one coherent base when the median closes of its first and
  final thirds drift by more than 8% of the base high; this prevents a preceding
  markup or markdown leg from being absorbed merely to gain duration.
  Volume does not select the base or decide whether price broke out.
- Derive completed ISO-week OHLCV bars on demand from the same stored daily
  candles: first open, maximum high, minimum low, last close, and summed volume.
  The unfinished signal week is excluded from base detection but may be included
  in immutable chart evidence. No weekly provider request or second candle table
  is required. Evaluate 26-104-week bases with weekly-specific body/wick limits
  of 25%/30% through 39 weeks, 28%/34% through 59 weeks, and 32%/38% through
  104 weeks. Require a 13-week launch area within 25%/30%, regime drift no more
  than 12%, and resistance in the upper 75% of the base. Weekly resistance uses
  confirmed actual-high pivots with one completed week on each side. Require
  three separated touches below 40 weeks; at 40 weeks and longer, two reactions
  separated by at least three weeks are sufficient. These thresholds are
  independent of the daily branch because aggregation changes the observed
  price distribution and suppresses intra-week noise.
- Confirm body-high pivots with two completed sessions on each side. Cluster their
  prices within `max(0.75% of resistance, 0.36 * ATR14)`, deduplicate adjacent
  tests, and require at least two touches separated by three sessions with no
  more than 1% standard-deviation dispersion. Each cluster's resistance is the
  midpoint between its median body-high acceptance level and median actual-high
  wick ceiling. Once the required second touch establishes the shelf, later
  touches cannot erase an intervening breakout event. Two closes above the upper
  zone confirm acceptance and retire the shelf; one close above the zone followed
  by a decisive close below the support boundary is a failed breakout and also
  permanently retires that shelf. While price remains near an invalidated shelf,
  the result retains the explicit `BREAKOUT_SUPPORT_FAILED` reason.
- Measure ATR, log-return, and daily-range contraction against preceding
  windows, plus EMA10/EMA20/SMA50 compression. The default target for each
  contraction ratio is 0.90 and the moving-average spread target is 4%. At
  At least one of these four checks must pass, in addition to the body-depth
  gate. The number and strength of the remaining checks contribute graded
  volatility-contraction evidence instead of vetoing an otherwise coherent
  horizontal base.
  All contraction and breakout-buffer inputs end before the signal candle so a
  wide breakout/retest session cannot invalidate or redefine its prior base.
- Do not use pre-signal volume, distribution days, or volume dry-up to select,
  reject, or score a consolidation.
  Breakout volume uses the current candle / prior average volume 50 so the
  breakout candle cannot inflate its own baseline. Volume contributes to
  distinguishing a strong breakout from a weak breakout only.
- Classify a price breakout above resistance plus
  `max(0.3% of resistance, 0.20 * ATR14)`. A confirmed `BREAKOUT` requires at
  least 1.4x volume, a close-location value of at least 0.70, and extension no
  greater than 1.5 ATR. Otherwise it is `WEAK_BREAKOUT`. During the following
  five sessions, a candle whose low returns to the prior breakout zone and whose
  close holds resistance minus `max(0.5% of resistance, 0.25 * ATR14)` is a
  `RETEST`. Body-weighted touch detection allows a small
  `max(0.10% of resistance, 0.10 * ATR14)` approach tolerance. A close below
  the support boundary is `NO_SETUP`. `CONSOLIDATING` additionally requires the
  close to be in the upper 75% of the selected base, within 5% of resistance,
  and no lower than its five-session comparison close.
- Evaluate `EARLY_RECOVERY_BREAKOUT` only as an additive fallback for a valid
  price breakout rejected solely because confirmed Stage 2 is not complete.
  Require `close > SMA50 > SMA150`, close above SMA200, a rising 20-session
  SMA50, SMA150 no more than 8% below SMA200, and a 20-session SMA200 decline
  no worse than 2%. Recovery confirmation is deliberately stronger: at least
  2.0x volume, close-location value at least 0.75, and extension no greater
  than 2.5 ATR. Existing high, relative-strength, base, resistance, and failure
  gates still apply. Confirmed Stage 2 classifications always take precedence.
- Preserve an accepted breakout as `BREAKOUT_HOLDING` while the close remains
  above the original upper resistance zone, for at most five trading sessions
  on daily analysis or five completed weeks on weekly analysis. During that
  timeframe-specific window, the same resistance shelf cannot emit another
  `BREAKOUT` or `WEAK_BREAKOUT`; only a materially distinct new shelf can start
  a new breakout lifecycle. A support loss has first precedence, an actual
  return into the zone becomes `RETEST`, and holding is the remaining
  post-breakout lifecycle state. Holding is not counted as a new backtest signal.
- Persist average 20-session traded value as descriptive context only. It does
  not select, reject, or score ordinary v13 setups because volume is reserved for
  strong-versus-weak breakout confirmation. Market-cap eligibility belongs to
  upstream universe selection.
- Require date-aligned Nifty 500 relative strength. The stock/index line must be
  above its 50-session average and within 5% of its 60-session high. Missing
  benchmark coverage is explicit `RELATIVE_STRENGTH_UNAVAILABLE`, not a zero.
- Calculate a 0-100 setup-quality score from normalized Stage 2 (20), relative
  strength (20), base (15), volatility contraction (15), resistance (15),
  proximity (10), and closing-quality (5) components. Volume has zero weight.
  Hard rejection is limited to incomplete history, insufficient liquidity,
  absent Stage 2, excessive base depth, or missing/invalid resistance.
- All calculations use sorted Decimal OHLCV values for one instrument at a
  time. Point-in-time calls ignore later candles, do not forward-fill gaps, and
  never let the current breakout candle redefine its base or resistance.

### Primary technical statuses

Each stock receives one deliberately simple, user-facing technical status:

| Status | Meaning |
|---|---|
| `BREAKOUT` | Buffered price breakout with strong volume, strong close, and controlled ATR extension |
| `EARLY_RECOVERY_BREAKOUT` | Strongly confirmed price breakout during a constrained long-moving-average recovery transition |
| `WEAK_BREAKOUT` | Price cleared buffered resistance but one or more confirmation checks are weak |
| `BREAKOUT_HOLDING` | A breakout remains above its original upper resistance zone without retesting it, within five trading sessions on daily or five completed weeks on weekly |
| `CONSOLIDATING` | All gates pass, a tight 20-120-session daily or 26-104-week base/resistance exists, and price is within 5% below the line without clearing its upper zone |
| `RETEST` | Price returned to an eligible prior daily/weekly resistance zone and closed without losing the configured support boundary |
| `NO_SETUP` | A hard eligibility/resistance requirement failed, or a recent breakout lost its support boundary; reasons explain why |

`FORMING`, `READY`, `FAILED_BREAKOUT`, and `SETUP_FOUND` remain read-only legacy
values so older snapshots are reproducible. `technical-v19` never emits them.

For every non-`NO_SETUP` v15 snapshot, the same transaction stores one or two
immutable chart-evidence rows: the actionable daily and/or weekly base through
the analysis candle, resistance line and thin zone, rejection dates, candle
revision, timeframe, period count, and schema version. The list
response exposes only availability; an authorized lazy endpoint returns the
bounded chart payload when the user opens the setup chart. When both timeframes
exist, the frontend presents them in one accessible slideshow.

The status and score describe research structure, not a trade entry, prediction,
or guaranteed breakout. The pure domain result and immutable snapshot persist
the component scores, selected base, resistance evidence, contraction/volume
metrics, breakout quality, and rejection reasons. Legacy pivot and confirmation
columns remain nullable only for forward-safe migration history.

`PREPARING` and `ANALYSIS_FAILED` are operational analysis states, not technical
market statuses. Separate badges communicate those states, eligibility, data
freshness, and fundamental coverage. These concerns must not be folded into the
primary technical status.

## 6. Fundamental research

Upstox is the initial source for structured company profiles, statements,
ratios, and shareholding. Provider access belongs behind an
adapter so it can be replaced after coverage validation.

The fundamental model will expose a broad, extensible set of versioned data
points, trends, and peer comparisons rather than forcing them into a single
score. Areas include:

- revenue and profit growth;
- margins and return ratios;
- operating cash flow and cash conversion;
- leverage and interest coverage;
- working-capital quality;
- share dilution;
- promoter ownership and pledging;
- earnings consistency;
- P/E and P/B compared with the company's historical medians;
- P/E and P/B compared with appropriate sector or industry medians; and
- sector-specific applicability.

The exact definitions, comparison periods, peer-group rules, and treatment of
financial companies must be agreed and tested before implementation. Each
displayed value must retain its reporting period, source/fetch time, and
calculation version. Negative earnings, invalid book value, insufficient peer
coverage, and inapplicable sector metrics must be shown honestly rather than
converted into favorable valuations.

Rules:

- Missing fields are `unknown`, not automatic failures.
- Show which expected data points are available, missing, stale, or not
  applicable; do not hide incomplete coverage.
- Admin overrides require a source, reporting period, citation, and audit trail.
- Ineligible stocks may be observed with a warning but are excluded from the
  breakout list.
- The breakout list is grouped by the explicit binary technical status and
  symbol, not by a composite score.

## 7. Market-data lifecycle

- Treat the latest completed NSE trading session as the analysis date, not the
  current calendar date. Before market close, on weekends, and on exchange
  holidays, use the previous completed session and show that `as of` date.
- Resolve provider availability once per queued batch with the Nifty 500. Use
  Upstox Historical V3 for finalized daily history. If the exchange session is
  complete but that date has not appeared in Historical V3, use the daily
  candle from Intraday V3 as an end-of-day fallback only while that session is
  still the current India calendar date. Intraday V3 never supplies a prior
  date; after midnight, request the completed session only from Historical V3.
  Never analyze an open or partial session.
- Mark fallback candles as `UPSTOX_INTRADAY`. On a later run, request that date
  from Historical V3 again and replace the provisional row with the finalized
  `UPSTOX` candle. Upserts and unique date constraints keep this idempotent.
- Cache the exchange calendar and Upstox holiday/special-session information;
  do not make the same exchange-level holiday request for every instrument.
- Pace Upstox calls by API family, reflecting the provider's per-API, per-user
  limits. Keep configurable headroom below the strictest sustained window;
  unrelated fundamental endpoints may run concurrently, while repeated calls
  to the same candle endpoint remain serialized.
- Verify expected sessions against returned candles. A missing candle for one
  instrument is not automatically a holiday and must be treated as incomplete,
  stale, suspended, inactive, or provider-delayed data until resolved.
- When a temporary provider failure or delayed latest candle affects only the
  newest stock session and validated earlier candle history is available,
  preserve the latest successful analysis and its actual `as of` date instead
  of showing `ANALYSIS_FAILED`. Internal completed-session gaps remain explicit
  data failures, and short continuous histories remain
  `INSUFFICIENT_LISTING_HISTORY`.
- Persist provider-validated ordinary candle fetches before technical analysis
  so retries request only unresolved gaps. A continuous post-listing series with
  fewer candles than the algorithm requires fails once as
  `INSUFFICIENT_LISTING_HISTORY`; absence of the whole requested history remains
  retryable as a likely provider failure.
- After a successful gap fetch, classify internal exchange sessions that the
  provider still omits as `PERSISTENT_CANDLE_GAPS`. Preserve the returned
  candles, do not analyze the incomplete series, and do not retry that job.
  Absence of the entire requested history remains transient and retryable.
- Fetch a complete rolling daily-candle window when an instrument is first
  tracked and has no retained candle history. The configured retention must be
  derived from the longest indicator lookback plus warm-up and correction
  buffers; approximately 400 trading sessions is the initial candidate, not a
  permanent magic number.
- Use a unique `(instrument, trading_date)` constraint.
- Store Nifty 500 as a `MarketBenchmark`, not as a company or equity
  instrument. Its OHLCV rows use a unique `(benchmark, trading_date)`
  constraint and are upserted idempotently alongside live stock analysis so
  relative-strength inputs remain available for reproduction and backtesting.
- Fetch only missing expected-session ranges. Treat a provisional intraday row
  as missing from finalized history so it is corrected when Historical V3
  catches up.
- Upsert idempotently so retries cannot create duplicates.
- Fill gaps before scanning after restarts or downtime.
- Removing an instrument as a normal user deactivates only that user's
  membership. Shared research remains while another user follows the instrument.
  An administrator removal is intentionally global: delete every user's
  membership and all instrument-owned identities, candles, fundamentals,
  analyses, tracking, and jobs in one transaction, then remove an orphaned
  company and its company-level periods.
- Re-adding an administrator-purged company creates a new internal instrument,
  provider identity, tracking row, and onboarding job. Because no candle history
  remains, the worker fetches and validates the complete configured window.
- Refuse to calculate signals from incomplete or stale history.
- Preserve historical fundamental periods independently; candle retention must
  not remove the data required for growth trends or valuation medians.
- Keep historical analysis events and forward outcomes because they are small
  and useful for evaluating the rules. Large backtest candle history remains in
  the separate Git-ignored backtest cache.

### Manual corporate-action policy

- V1 does not fetch, store, classify, or automatically repair corporate actions.
- The administrator is responsible for identifying an affected company,
  deleting it globally, and adding it again. The deletion intentionally removes
  prior research continuity for that instrument; the new onboarding job fetches
  a clean provider window and recalculates all derived values.
- A normal user cannot trigger this destructive reset. The administrator UI
  requires explicit confirmation and the backend/database enforce global purge
  semantics transactionally.
- Upstox may revise or adjust historical candles. This manual policy does not
  prove adjustment correctness, so the limitation must remain visible in project
  documentation and demonstrations.
- Calculate technical indicators locally from validated candles. Do not depend
  on opaque provider-generated technical scores or statuses.
- Delete candles outside the configured rolling window only after the refreshed
  range is complete and the current analysis has succeeded.

Initial provider acceptance testing should sample 30–50 varied NSE companies,
including large/mid-cap, recently listed, non-March year-end, loss-making,
banking, NBFC, and insurance cases. Provider freshness and history depth must be
measured rather than assumed.

## 8. Deferred document intelligence

Document intelligence is explicitly deferred until after V1. V1 will not
upload or store company documents, generate embeddings, perform semantic
retrieval, or provide AI question answering.

A later milestone may add:

1. Upload and private storage of public company documents.
2. Page-aware text/table extraction with selective OCR.
3. Chunking and embeddings associated with the owning `company_id`, document,
   page, reporting period, and source metadata.
4. Retrieval restricted to the selected company so questions cannot mix
   evidence from unrelated companies.
5. Company-specific question answering with page citations and evidence
   excerpts.
6. Validation and human review of AI-generated claims before persistence or
   display.
7. Explicit retention, deletion, deduplication, and audit rules.

The storage and retrieval technology will be chosen when this milestone begins.
A separate vector database must not be added by default; PostgreSQL-based vector
search and simpler non-vector retrieval should be evaluated against the actual
document volume and query requirements.

Removing a stock as a normal user is a reversible soft removal of that
membership. Administrator removal is a permanent global purge of the instrument
and all dependent research for every user; re-adding starts with a new identity
and full market-data fetch.

Local backtest data will be cached under `.local-data/backtest-cache`. This path
is private, persistent across container restarts, and Git-ignored.

## 9. Architecture and technology choices

### Local stack

| Layer | Choice | Reason |
|---|---|---|
| Orchestration | Docker Compose | Reproducible setup without local language/database runtimes |
| Frontend | React + TypeScript + Vite | Modern, typed SPA with a fast and simple build tool |
| Styling | Tailwind CSS v4 | Learnable utilities and a clean responsive UI without a large component framework |
| Routing | React Router | Explicit client-side navigation |
| Server state | TanStack Query | Loading, caching, invalidation, and job polling |
| HTTP | Axios | One configured client with timeouts, auth, and consistent errors |
| Client state | React Context | Small shared admin/session state; Redux is not justified yet |
| Backend | Python + FastAPI | Strong data ecosystem, typed APIs, async I/O, and generated API docs |
| Persistence | PostgreSQL | Relational integrity, transactions, and mature querying |
| ORM | SQLAlchemy 2 | Explicit typed models, queries, transactions, and pooling |
| Migrations | Alembic | Reproducible schema evolution across environments |
| Market/fundamentals | Upstox adapter | Free-first structured Indian market data for account holders |
| Tests | Pytest and frontend unit/integration tests | Fast feedback around business rules and UI behavior |

Do not combine Tailwind and Bootstrap. Do not add Redux, Next.js, Create React
App, jQuery, or another state/UI framework unless a real requirement appears and
the architectural decision is documented.

### Initial runtime shape

```text
Browser
  -> React/Vite frontend container
  -> FastAPI backend container
  -> PostgreSQL container

FastAPI -> Upstox (market data and fundamentals)
```

This stays a modular monolith: routes, services, domain logic, repositories, and
provider adapters are separated inside one backend deployment. Microservices are
not justified at this scale.

## 10. Background work and automation

### Current timeout budget

- PostgreSQL connection establishment is limited to 5 seconds.
- The readiness database operation is limited to 5 seconds end to end so a
  stalled pooled connection cannot hang `/ready`.
- SQL statements executed through the application engine are limited to 8
  seconds.
- Frontend API requests use a 10-second timeout so the backend can return a
  meaningful dependency or query failure before the browser gives up.
- Reassess these limits when implementing provider calls, nightly scans,
  backtests, deferred document intelligence, and other legitimately long-running
  work.
  Long-running jobs should use explicit operation-specific budgets rather than
  silently increasing the interactive API limits.

- FastAPI handles membership-triggered onboarding and admin manual scans using
  durable records and visible market-language progress.
- GitHub Actions runs CI and the scheduled 4:00 PM IST end-of-day scan. Provider
  acceptance testing must verify that the completed NSE daily session is
  consistently available by then. If data is delayed, the scan records a
  retryable incomplete-data result and retries with bounded backoff rather than
  analyzing stale or partial candles.
- The GitHub-hosted runner executes the scanner command directly; it does not
  depend on waking a sleeping web service.
- A separate GitHub Actions schedule invokes the ephemeral morning digest at
  8:30 AM IST on weekdays. The command confirms that the date is an open NSE
  session before sending, so exchange holidays remain silent. It reads the
  latest stored research and sends directly to Telegram without creating a
  notification row. A missed or failed run expires instead of delivering stale
  morning information later.
- The 4:00 PM IST nightly command fills candle gaps, evaluates technical setups,
  and updates forward outcomes. It does not
  fetch company fundamentals; administrators schedule those independently.
- Job operations must be idempotent and recoverable after retries.
- On startup, the durable runner resumes or recovers queued work and reconciles
  every active tracked instrument against the latest completed NSE session. It
  enqueues that latest session only when no successful analysis exists. If an
  older job is still pending, it is retargeted in place to the latest session;
  retry state resets and no duplicate job is created. A job already running is
  allowed to finish safely, after which the runner completes reconciliation.
  This catches up the latest state after downtime; it does not replay every
  missed historical session.
- After an algorithm-version change, the administrator's manual refresh is the
  only path allowed to force another analysis of an already-successful market
  session. Startup reconciliation and the normal nightly selector never force
  the same session again. The new `algorithm_version` produces a distinct
  immutable result even when the target session and candles are unchanged.
- A future paid deployment may move scheduled work to a managed cron/worker.

### Newly followed instrument workflow

- `UserWatchlistItem` owns `(user, instrument)` membership while
  `TrackedInstrument` owns shared research activation for an instrument.
  Company fundamentals remain reachable through `instrument.company_id`.
- When any authenticated user adds an instrument, determine and persist the target
  completed trading-session date at request time. During market hours, on
  weekends, and on exchange holidays, target the most recent completed session
  rather than the current calendar date.
- Lock the user row, count active memberships, and atomically add the selected
  modal batch. Admin bypasses quota enforcement; a normal-user request that
  would exceed `NORMAL_USER_WATCHLIST_LIMIT` fails as a whole without partial
  membership changes. Duplicate active selections do not consume extra quota.
- In the same membership use case, create/reactivate shared tracking plus one
  durable technical-onboarding job and one independent fundamental-refresh job
  only when needed. Multiple users following the same active, current
  instrument must not create duplicate candles, fundamentals, or provider work.
- Return the tracking resource immediately with operational state `PREPARING`,
  the target session, and job identifier. The frontend polls the resource with
  TanStack Query until the state changes; WebSockets are not justified yet.
- Removing a membership as a normal user marks it inactive for that user. Shared
  tracking and pending work stop only after the last active membership
  disappears. Administrator removal deletes the instrument and all dependent
  rows for every user. A worker that observes the concurrent purge treats the
  missing durable job as cancellation rather than a runtime failure.
- Do not use an unpersisted FastAPI `BackgroundTasks` operation for provider
  work because it would be lost on process restart.
- Run a lightweight worker from the same backend code and Docker image. This is
  still one modular monolith and does not require Celery, Redis, Kafka, or a new
  microservice.
- Keep automatic latest-session scheduling on worker startup configurable. The
  default is disabled: startup recovers and processes durable queued work but
  does not contact the provider merely to create or retarget catch-up jobs.
- The worker claims a pending database job with `FOR UPDATE SKIP LOCKED`, marks
  it running in a short transaction, and commits before making provider calls.
  Database locks must not be held during network I/O.
- Multiple API and worker replicas share PostgreSQL request-permit rows for
  Upstox and Telegram pacing. Telegram update polling uses a session-level
  PostgreSQL advisory lease so only one replica polls while failover remains
  automatic.
- Record an authenticated user's `last_active_at` no more than once per 15
  minutes. The administrator analytics endpoint reports registration and
  activity windows, Telegram adoption, tracked stocks, watchlist memberships,
  setup distribution, and current durable-queue state.
- Optional bearer-protected Prometheus metrics expose normalized-route request
  counts, duration histograms, and in-progress gauges. Keep one API process per
  Kubernetes pod and size bounded SQLAlchemy pools against the database's total
  connection limit.
- `analysis_jobs` is an active durable queue, not an audit log. Pending and
  retrying work remains restart-safe; succeeded, terminally failed, exhausted,
  and cancelled rows are deleted after their durable outcome is recorded.
  Immutable analysis snapshots prove successful sessions, while
  `TrackedInstrument` retains only the current terminal data-quality session
  and code needed for same-session idempotency.
- The worker loads the active provider identity, fills missing candle ranges,
  verifies completeness, calculates indicators locally, and
  persists the status for `(instrument, target_session, algorithm_version,
  candle_revision)` before marking the job successful.
- Persist whether an analysis job is a full market-data refresh or an
  algorithm-only rerun. The latter must use complete stored stock and benchmark
  candles without calling Upstox. Every technical-rule change must advance the
  algorithm version before such a rerun.
- Unique constraints and upserts prevent duplicate user memberships, global
  tracking entries, active work, candles, and analysis results on retries.
- Retry transient failures with bounded backoff and actionable error codes.
  After the retry limit, expose operational state `ANALYSIS_FAILED` separately
  from the last valid technical status.
- The authorized stock list retains every active tracked identity even when no
  valid analysis snapshot exists. Such rows expose nullable market-analysis
  fields plus the terminal session/code; the UI renders plain-language
  operational badges and status sorting places them after analyzed results.
  Never create a synthetic `NO_SETUP` snapshot to hide an analysis failure.
- Treat `INSUFFICIENT_LISTING_HISTORY` and provider-confirmed internal
  `PERSISTENT_CANDLE_GAPS` as terminal data-quality outcomes for that target
  session. Repeated scheduling for the same session skips the latest terminal
  result, while a later completed session is eligible for a fresh check.
- Fundamental refresh uses its own durable job type and may run alongside or
  after technical analysis. It never fetches candles or changes the technical
  operational state, and missing fundamentals do not block technical status.

## 11. Backtesting and outcome measurement

The backtest is a local CLI, not a nightly or hosted job.

- Reuse the same `technical-v19` Stage 2, recovery-transition, daily and derived-weekly
  base selection, confirmed resistance clustering, contraction, volume quality, breakout/retest,
  optional Nifty 500 relative-strength, state, and scoring rules used by the
  scanner. Do not introduce historical-only filters.
- Use an earlier calibration period and a later untouched validation period.
- Measure 5-, 20-, and 60-session returns, benchmark-relative returns, maximum
  adverse excursion, and false-breakout rate.
- Prevent look-ahead bias and overlapping signals.
- Cache large candle data in Git-ignored Parquet files.
- Publish only small aggregate reports.
- Prominently disclose survivorship bias when using current Nifty 500 members.
- Re-run when indicator definitions or breakout logic change.

The nightly forward-outcome log independently measures signals produced by the
live application.

## 12. UI principles

- Lucid, clean, responsive, and easy to scan.
- `/login` and `/signup` are separate responsive pages. Successful login or
  signup redirects to the watchlist; signed-out access to protected routes
  redirects to login, and logout explicitly returns there.
- No general charting terminal in V1. A bounded, read-only candlestick popup is
  allowed solely to inspect the exact evidence persisted with a setup analysis.
- A user's watchlist plus stock-detail/research views.
- The watchlist header places one **Add companies** action at the right. The
  stock table uses authenticated server-side search by company name or trading
  symbol before selectable 10/25/50/100/all-row pagination. Search, sorting,
  and pagination stay inside the
  caller's authorized scope and never call the market-data provider or replace
  the Add Companies discovery flow.
- The add action opens an accessible modal with debounced Upstox company search,
  multi-selection, selected-count/normal-user capacity feedback, Cancel, and an
  atomic Save action. On small screens it becomes a near-full-screen sheet.
- Every watchlist stock has an accessible three-dot menu with a remove action,
  keyboard support, outside/Escape dismissal, and clear confirmation/progress.
  Administrators see an explicit global-data-delete action and warning.
- Each stock shows its latest completed-session close, one-day percentage
  movement, and
  percentage movement from the close captured when that user most recently
  added it. Removal and re-addition reset this persisted membership baseline;
  the value remains unavailable until that session's close is retained.
- A later UI slice may display the persisted resistance evidence and component
  metrics with their as-of date and `technical-v19` version. It must label this as research
  context rather than a target, recommendation, or guaranteed breakout. Each
  stock also provides a safe external TradingView chart link. Viewport-level
  tooltips and action menus must not create table or final-row overflow
  scrollbars.
- Reusable, small components such as buttons, badges, cards, tables, alerts,
  forms, modals, spinners, progress indicators, toasts, and tabs.
- Consistent colors for technical statuses.
- Explicit loading, empty, error, stale, incomplete-data, and permission states.
- Accessible labels, keyboard interaction, and sufficient color contrast.
- Keep Tailwind class lists readable by extracting repeated UI patterns.

## 13. Security and privacy

- Never commit API keys, tokens, passwords, future uploaded documents, or local
  database data.
- Keep secrets in a Git-ignored environment file and placeholders in
  `.env.example`.
- `keys.txt` is treated as sensitive legacy material: never read, print, or
  commit it. Move its values to the future ignored environment file, then remove
  it only with explicit user approval.
- Provider credentials stay in the backend.
- Hash all passwords with Argon2 and use secure session/cookie settings
  appropriate to the environment. Session authorization derives the user and
  role server-side; the frontend never selects or asserts a role.
- Public signup accepts only a normalized, bounded username and password, always
  assigns the normal-user role server-side, reserves the configured administrator
  name, and relies on the database uniqueness constraint for concurrent requests.
  Add edge rate limiting or an equivalent deployment control before exposing
  registration broadly on the public internet.
- Enforce per-user ownership in every watchlist query/mutation and never trust a
  browser-supplied user id. Normal-user quota enforcement occurs transactionally
  on the backend; frontend capacity display is convenience, not security.
- Log operational metadata without logging secrets or sensitive business data.

## 14. Testing strategy

Testing grows with each vertical slice:

- Unit tests for indicators, fundamental calculations, valuation comparisons,
  and status transitions.
- Repository tests against PostgreSQL.
- API integration tests for signed-out, admin, ownership-isolated normal-user,
  quota, and concurrent/batch workflows.
- Provider contract tests using recorded/synthetic fixtures, plus explicitly
  invoked live integration tests.
- Frontend component and user-flow tests.
- Docker Compose smoke tests.
- End-to-end browser tests for login, admin/unlimited, normal-user quota,
  responsive modal, multi-select save, three-dot removal, and sign-out journeys.
- A fixture/snapshot demonstration that requires no provider credentials.

Real credentials are enabled one integration at a time, beginning with Upstox
for one stock. Hosted services are tested only after local behavior is stable.

## 15. Delivery milestones

Each milestone is a small, tested vertical slice. Do not generate all milestones
at once.

1. **Foundation:** verify prerequisites, create planning files, initialize Git,
   and add secret-safe ignore rules.
2. **Container skeleton:** create backend, frontend, and PostgreSQL containers;
   explain every Docker file and verify service startup.
3. **Health slice:** implement FastAPI `/health`, call it from React, and test the
   first browser-to-backend flow.
4. **Database foundation:** add SQLAlchemy, Alembic, connection health, and the
   first migration.
5. **Fixture mode:** seed safe sample companies/results and build the stock-list
   UI with status and coverage states.
6. **Admin access and watchlist:** add the simple single-admin session, tracked
   instrument CRUD, durable onboarding-job record, and worker skeleton.
7. **Upstox integration:** integrate one real stock through a provider adapter;
   add trading-session resolution, rolling candle persistence, gap recovery,
   and fundamentals.
8. **Technical engine:** implement indicators, patterns, statuses, and unit tests.
9. **Fundamental research:** define and implement versioned data points, trends,
   historical/sector valuation comparisons, coverage, overrides, and calculation
   tests.
10. **Nightly scan and job hardening:** extend the onboarding job pattern with
    bounded retries, observability, outcome updates, and the scheduled command.
11. **Backtest:** run the local historical report and document limitations.
12. **Quality pass:** complete automated tests, security checks, UI polish, and
    interview/architecture documentation.
13. **Deployment:** after local acceptance, deploy frontend to Vercel, backend to
    Render, PostgreSQL to Neon, and nightly scanning to GitHub Actions.
14. **Per-user watchlists:** migrate the environment administrator into the user
    identity model, add normal users and isolated configurable quotas, then
    replace inline admin controls with separate login/signup pages, a batch-add
    modal, and a per-row action menu.

After V1 is accepted, document upload, extraction, embeddings, company-specific
question answering, citations, and retention will be planned as a separate
vertical milestone.

## 16. Later hosting plan

| Responsibility | Provider |
|---|---|
| React frontend | Vercel |
| FastAPI backend | Render |
| PostgreSQL | Neon |
| CI and nightly scan | GitHub Actions |

Railway is not part of the selected plan. Current provider pricing, limits,
authentication, and API documentation must be rechecked from official sources
immediately before integration or deployment.

## 17. Documentation deliverables

- `README.md`: setup, daily commands, tests, and demo instructions.
- Architecture decision records explaining choices and alternatives.
- Production-scaling path: queues/workers, managed scheduling, observability,
  object storage, larger universe processing, and availability improvements.
- React/TypeScript learning notes tied to actual project examples.
- API/provider integration notes and data-quality findings.
- Backtest methodology and limitations.
- Interview guide: architecture walkthrough, tradeoffs, likely questions, and a
  reliable demonstration script.

## 18. Definition of done for V1

V1 is complete when:

- a clean machine with Docker can run the documented local setup;
- snapshot mode demonstrates the complete read-only experience without secrets;
- admin watchlists have no application quota; each normal user is isolated and
  transactionally limited by `NORMAL_USER_WATCHLIST_LIMIT`, initially 20;
- technical statuses are explainable and covered by deterministic tests;
- fundamental research displays its coverage and never invents missing data or
  misleading aggregate scores;
- normal-user removal affects only that user's membership; administrator removal
  permanently purges the instrument and its research for every user, while a
  later add creates a clean identity and full-history onboarding job;
- watchlist routes require login and enforce server-derived ownership; only the
  admin can manually refresh global research;
- separate login, protected routing, responsive multi-select add modal, normal-
  user capacity feedback, and accessible three-dot removal work on mobile,
  tablet, and desktop;
- public signup can create only a quota-limited normal account and successful
  logout always returns to the login page without an empty intermediate view;
- the critical local and automated tests pass;
- architecture, limitations, scaling options, and interview explanations are
  documented; and
- the project can be demonstrated without claiming production readiness or
  investment certainty.

## 19. Current implementation handoff

As of 2026-07-25, milestone 14 is implemented: the previously completed
single-admin V1 now supports authenticated per-user watchlists while reusing
shared market data, fundamentals, and analysis per instrument.

Agreed milestone-14 decisions:

- The environment-configured username `admin` remains the administrator and has
  no application watchlist quota. Public signup creates only normal users, which
  default to a configurable 20-stock limit; the backend-only provisioning command
  remains available for local administration.
- Market research is shared per instrument. A new per-user membership model
  must not duplicate candles, fundamentals, analysis results, or provider work.
- Existing active tracked instruments migrate into the admin user's personal
  watchlist without deleting history.
- Batch addition is atomic and backend-enforced under a user-row lock. The
  frontend never supplies an owner id or role.
- Signed-out users use separate `/login` and `/signup` routes. Successful signup
  starts a normal-user session, and logout explicitly returns to `/login`. The
  protected watchlist uses one right-aligned add button, a responsive searchable
  multi-select modal, and an accessible three-dot removal menu per stock.
- Manual global research refresh remains admin-only. Normal users may add and
  remove their own companies, subject to quota.
- Removing one normal-user membership never deactivates shared tracking while
  another active membership remains. Administrator removal is the explicit
  exception: it globally purges the instrument and all dependent data.

- Docker Compose runs PostgreSQL, FastAPI, React/Vite, and the durable research
  runner. No local Python or Node installation is required.
- The PostgreSQL model and Alembic history cover companies, effective-dated
  instrument identities, OHLCV, fundamental snapshots and
  periods, immutable analysis results, reversible tracking, retryable work, and
  secure user sessions. Each membership also persists the target session and
  closing-price baseline for its latest activation so re-addition correctly
  resets user-specific movement without depending on long-term candle retention.
- Authenticated list/detail APIs enforce active membership for normal users and
  hide temporary bulk-scan instruments even if a membership is guessed or
  created. Administrators may access the active shared research universe.
  List search and user-relative sorting are applied before selectable
  10/25/50/100/all-row pagination for both roles while
  details present shared current setup research, prices, company financial
  data, coverage, and dates.
- The responsive React experience provides separate login/signup pages,
  protected routing, a searchable multi-select company modal, normal-user
  capacity feedback, accessible unclipped three-dot removal, TradingView links,
  latest/daily/since-added price movement, binary setup status, and
  admin-only manual refresh.
  User-visible messages use business/market language rather than backend
  processing terminology.
- Live onboarding loads the active provider identity, fills ordinary candle
  gaps, validates a complete window, runs the local engine, and atomically
  preserves the last valid result on failure. Corporate-action handling is a
  deliberate manual administrator delete-and-re-add operation.
- Upstox adapters validate instrument search, sessions, historical candles,
  profiles, ratios, statements, and shareholding responses.
  Normal tests use synthetic responses; live smoke testing is opt-in and
  output-safe.
- The durable runner implements ordered claims, bounded exponential retry,
  cancellation preservation, stale-run recovery, and safe failure codes. The
  nightly selector schedules every active company without a fixed count cap.
- The historical report reuses the real technical engine on date prefixes and
  reports 5/20/60-session outcomes, adverse excursion, false-breakout rate, and
  required Nifty 500-relative returns without inventing missing values.
- The three sample companies were removed from the current database. Explicit,
  idempotent demo seed/purge commands remain for offline interview mode.
- CI, a timezone-aware weekday GitHub workflow, Render API blueprint, hosted
  PostgreSQL TLS configuration, and a Vercel same-origin proxy template are
  present. Nothing has been pushed, published, or deployed by Codex.
- `README.md` and `docs/` describe operation, architecture, deployment,
  limitations, scaling, and interview answers.
- Final verification on 2026-07-25 passed 136 backend tests, 27 frontend tests,
  Alembic drift checking, frontend type checking, and the production build.
  Real 375px and 768px login/signup checks had no console errors or horizontal
  overflow; authenticated stock-list responsiveness remains covered by the
  component suite and the earlier real-browser 375px/768px/1280px checks.

Remaining intentional limitations are documented in `docs/LIMITATIONS.md`.
The fundamental UI currently exposes broad versioned provider data and coverage
but not every proposed sector-specific derived comparison. Technical thresholds
remain configurable and testable rather than presented as investment certainty.

## Appendix A. Historical implementation handoff

Completed foundation work:

- Docker Compose runs React/Vite, FastAPI, and PostgreSQL with persistent database
  storage and internal service networking.
- FastAPI exposes liveness and database-backed readiness endpoints.
- SQLAlchemy 2 async infrastructure, Alembic, and the empty database-foundation
  migration are configured and tested.
- React uses Axios and TanStack Query to display readiness through the frontend
  proxy with explicit loading, dependency-failure, and refetch behavior.
- Current timeout budget is 5 seconds for database connection/readiness, 8
  seconds for application SQL statements, and 10 seconds for frontend requests.
- The first milestone-5 domain migration adds `Company`, `Instrument`, and an
  immutable `AnalysisSnapshot` with internal primary keys, explicit market dates,
  reproducibility metadata, technical status, fundamental-coverage status, and
  current/previous close. Legacy pivot/confirmation columns are retained as
  nullable migration history and remain unused by `technical-v19`.
- PostgreSQL constraints enforce normalized instrument identity, idempotent
  analysis identity, positive prices, bounded persisted scores, supported
  technical state values, and unused-null legacy pivot fields.
- Focused PostgreSQL integration tests run inside rolled-back transactions, and
  the migration has been verified upgrade, downgrade, and upgrade again without
  schema drift.
- A separate transactional fixture command seeds three clearly synthetic stocks
  covering every technical status and fundamental-coverage state. Rerunning the
  command is idempotent and creates no duplicate companies, instruments, or
  snapshots.
- Public `GET /stocks` returns one latest valid analysis per instrument, ordered
  by explicit technical-status group and symbol. It includes each result's
  analysis date, exact price strings, derived one-day percentage change,
  coverage, source freshness, algorithm version, technical-v19 state, setup
  score, component scores, selected base/resistance evidence, quality metrics,
  and rejection reasons.
- The latest-analysis query retains history internally while presenting only the
  newest successful result. An unsuccessful future run will therefore leave the
  previous dated result available rather than overwriting it.
- Backend verification currently has 66 passing tests, including pure Decimal
  calculations, empty-list behavior, latest-result selection, fixture
  idempotency, response serialization, PostgreSQL constraints, and transactional
  watchlist lifecycle behavior, plus administrator authentication and CSRF
  enforcement.
- React/TanStack Query now provides the fixture stock-list experience with
  explicit loading, empty, API-error, retry, and background-refresh states.
- The responsive presentation uses a semantic desktop table and mobile cards
  to show technical status, exact close, one-day percentage change, fundamental
  coverage, source, and analysis date.
- Frontend verification currently has 27 passing tests: four StockList tests,
  twelve administrator authentication tests, and eleven watchlist API/control
  tests covering visitor hiding, loading, add, remove, reactivation, polling
  inputs, retry, mapping, and safe errors. The production TypeScript/Vite build
  and the real Docker/browser path have also been verified.
- The root README documents Docker-only startup, migration, idempotent fixture
  seeding, demo URLs, verification commands, and current scope boundaries.

Agreed lifecycle constraints for watchlist/provider work:

- Adding or reactivating a stock creates a durable onboarding job immediately
  and fills missing candle ranges from its active provider identity.
- Company names and trading symbols are mutable display attributes. Internal
  instrument identity remains stable, while ISIN and provider-key mappings are
  effective-dated and versioned when authoritative exchange/provider data proves
  continuity.
- V1 does not automatically process corporate actions. The administrator
  globally deletes and re-adds an affected stock to force a clean identity and
  full retained-window fetch.
- The milestone-6 persistence foundation adds one soft-removable
  `TrackedInstrument` per instrument and durable `AnalysisJob` history with
  `PENDING`, `RUNNING`, `SUCCEEDED`, `FAILED`, and `CANCELLED` states.
  PostgreSQL enforces membership uniqueness, valid lifecycle timestamps,
  non-negative attempts, normalized failure metadata, and at most one active job
  per tracking record and job type. The migration has been verified downgrade,
  upgrade, and schema-drift free, with eight focused model tests.
- A transactional watchlist application service now locks the internal
  instrument identity, atomically creates or reactivates tracking with its
  pending onboarding job, handles repeated add/remove commands idempotently,
  and soft-removes tracking while cancelling pending or running work. Typed
  not-found errors and deterministic UTC timestamps form the future HTTP
  boundary. Ten focused PostgreSQL service tests include rollback after
  synthetic job-creation failure.
- The single-administrator backend boundary is complete. A configured Argon2
  password hash creates opaque, expiring sessions through `POST /auth/login`;
  `GET /auth/session` restores browser state; and `POST /auth/logout` requires a
  matching double-submit CSRF token before revoking the PostgreSQL session.
- Raw session and CSRF credentials exist only in browser cookies. PostgreSQL
  stores SHA-256 digests, the session cookie is HttpOnly, credential failures
  use one generic response, and absent or invalid server configuration fails
  closed. Changing the configured administrator username also invalidates old
  sessions.
- The `admin_sessions` migration is applied at revision `60c5d892abfe`, and
  Alembic reports no schema drift. Twelve focused model/API tests cover cookie
  flags, digest persistence, invalid credentials and configuration, missing and
  mismatched CSRF, logout revocation, expiry, and timezone validation.
- Protected `PUT` and `DELETE` commands now expose the internal watchlist
  lifecycle under `/admin/watchlist/instruments/{instrument_id}`. They reuse a
  separate business database session, require both administrator authentication
  and CSRF validation, map typed service failures to stable 404 error codes, and
  return whether membership was created, reactivated, already active, or
  already inactive together with relevant durable-job state.
- Seven focused API tests verify permission failures, CSRF enforcement, strict
  request validation, 201/200 semantics, idempotency, cancellation, history-
  preserving reactivation, and not-found mappings. Until the provider/calendar
  slice exists, `target_session` is an explicit deterministic command input; it
  must later be replaced by backend resolution of the latest completed NSE
  trading session.
- The onboarding-worker skeleton claims the oldest active pending job with
  PostgreSQL `FOR UPDATE SKIP LOCKED`, commits the `RUNNING` transition before
  invoking an injected handler, and finalizes in a separate short transaction.
  Success and failure finalization both preserve an administrator's concurrent
  cancellation, and unexpected exceptions persist only generic safe failure
  metadata.
- Nine focused worker tests cover empty queues, ordered claims, attempt counts,
  success, safe unexpected failure, cancellation during both successful and
  failing handlers, invalid state transitions, normalized failure metadata, and
  deterministic UTC time injection. No executable loop, scheduler, retry
  recovery, stale-running-job repair, or provider handler exists yet.
- React now restores the administrator session through TanStack Query, treats a
  session 401 as the normal visitor state, and presents accessible checking,
  unavailable/retry, signed-out form, signed-in, login-error, logout-progress,
  and logout-error states without blocking the public stock list.
- The shared Axios client sends credentials and echoes only the readable CSRF
  cookie on mutating methods; the HttpOnly session token never enters JavaScript
  state. Twelve focused auth/API/component tests pass, the strict production
  build succeeds, and real-browser checks verified desktop and 375px layouts,
  correct password/autocomplete attributes, no horizontal overflow, public
  fixture visibility, and no console warnings or errors.
- Protected `GET /admin/watchlist/instruments` returns active and retained
  inactive tracking records with company/instrument identity, lifecycle
  timestamps, operational state, and only the latest durable job. Three focused
  integration tests cover authentication, empty state, active counts, ordering,
  latest-job state, and cancelled history.
- The signed-in React watchlist panel merges the protected tracking read model
  with public fixture candidates, supports add/reactivate/remove commands,
  announces outcomes, exposes operational/job state, handles permission and
  service failures, and polls while active jobs are pending or running. Visitors
  see no controls and retain the complete public stock list.
- Per the current product decision, neither the API nor database enforces a
  fixed watchlist-size limit. Existing uniqueness and job-state constraints
  remain enforced; scale beyond the tested personal/fixture workload is not yet
  claimed.

Milestone 5 fixture mode and milestone 6 admin/watchlist work are complete.
Milestone 7 is in progress: the backend now has a typed Upstox V3 adapter for
daily candles, NSE equity search, and date-specific exchange sessions; provider
failures are converted to safe retryable/non-retryable codes, and normal tests
use only synthetic HTTP responses. The Upstox Analytics Token is an optional
backend-only secret. A separately invoked, output-safe live smoke command has
successfully searched RELIANCE, resolved completed session `2026-07-24`, fetched
  11 short-window candles, and validated the provider session boundary.
No credential, header, or raw provider body was displayed or persisted.

The live-research migration at revision `9b7e1c4d2a10` introduced provider
identities, OHLCV, fundamentals, and the now-removed corporate-action table.
Revision `b4d6f8a0c213` removes that table and makes instrument-owned data cascade
on administrator deletion. The provider-independent completed-session resolver handles ordinary
cutoff time, weekends, explicit holidays, and special weekend session close
times; watchlist commands no longer trust a frontend-supplied target date.

`technical-v19` supersedes the earlier technical algorithms. It preserves v18's
point-in-time 20-120-session scan, duration-sensitive robust body/wick limits,
breakout-holding lifecycle, while volume remains a strength qualifier after
price confirmation rather than a resistance-discovery condition. V8
early-recovery breakout fallback with stricter volume, close,
extension, moving-average convergence, and moving-average slope requirements;
it never weakens or replaces a confirmed Stage 2 result. V9 added a five-session
breakout-holding lifecycle state without counting continuation days as new
signals. V10 evaluates shelf history from the touch that first establishes it:
a later touch cannot erase a failed breakout, and one accepted close followed
by decisive support loss permanently retires the old shelf. V11 reduces the
minimum contraction confirmations from two to one while retaining structural
body/wick depth as a hard gate and contraction strength in setup quality. This
keeps orderly bases whose volatility is stable rather than at least 10% lower
across several fixed windows. V12 narrowly raises resistance clustering from
0.35 to 0.36 ATR so a nearby confirmed rejection is not lost at the refined
median-tolerance boundary; body-high pivots, separation, and dispersion gates
remain unchanged. V13 adds a separate 26-104-week long-base branch derived
deterministically from stored daily candles, weekly wick-pivot resistance and
duration-specific depth/launch rules, weekly holding/retest context,
and up to two immutable chart slides per analysis. It also lets coherent daily
wick rejections augment a body-established shelf's evidence and upper breakout
ceiling without allowing one isolated wick to establish resistance. V14 leaves
all V13 thresholds and classifications unchanged, but extends inherited retest
and breakout-holding chart evidence through the current analysis candle,
including the current partial week for a weekly setup. V15 gives a held
resistance-zone touch precedence as `RETEST` after any already-qualified
breakout type; current-day Stage 2 or relative-strength softening cannot relabel
that price-defined lifecycle event as `BREAKOUT_HOLDING`. V16 keeps body pivots
as the requirement for establishing a daily shelf, but extends its upper
breakout ceiling to every confirmed rejection wick whose candle body tested the
same shelf. Touch deduplication still controls touch count; it no longer erases
a coherent higher wick from the zone. Lifecycle lookback also stops at an
intervening support failure so an invalidated breakout cannot later reappear as
a retest. V17 applies the same rejection-ceiling principle to weekly wick
shelves: touch deduplication controls independent weekly tests but cannot erase
a coherent higher wick from the upper zone. Weekly candidates now calculate
contraction from completed weekly bars instead of inheriting daily measurements:
five recent versus twenty reference weeks for ATR, return volatility, and range,
plus EMA5/EMA10/SMA20 compression with an 8% weekly spread ceiling. Selected
weekly results persist and score those weekly measurements. The chart popup also
derives the latest close and the matching one-day or current-week percentage
change from each stored daily/weekly evidence slide. V18 gives the breakout
lifecycle the same bounded meaning on both timeframes: five trading sessions on
daily and five completed weeks on weekly. During that window the same shelf is
classified as holding, retest, or support failure instead of emitting repeated
breakout signals; a materially distinct new shelf remains eligible. Broken-shelf
candidates retain their original acceptance date so the weekly window is applied
point in time. Weekly chart labels also include the year. V7's structure confirms pivots on
point in time. Weekly chart labels also include the year. V19 requires ordinary
breakout Stage 2 to exist before the signal candle, so one large candle cannot
manufacture its own prerequisite trend. A close must clear the already-buffered
upper resistance/wick zone by the larger of 0.10% of resistance or 0.10 ATR;
this prevents a marginal probe from becoming a breakout/retest lifecycle event.
A recent valid consolidating shelf is retained for at most five daily sessions
or five weekly periods when a marginal probe temporarily makes fresh base
detection unavailable, allowing a later decisive close to break the same shelf.
These rules share one implementation across daily and weekly candidates. V7's structure confirms pivots on
body highs, represents rejection as a body-to-wick zone, retires shelves after
two accepted closes, detects a subsequent recent support failure, and requires
upper-range five-session approach evidence for consolidation. Nested windows on
the same shelf prefer the longest valid duration; competing shelves remain
quality-ranked. It retains
hard 26-week-high/relative-strength/tightness checks, volume-only breakout
confirmation and immutable setup-chart evidence. Its horizontal resistance
remains independent of volume, and it emits breakout,
weak-breakout, consolidating, retest, or no-setup states.
It persists explainable
0-100 component scoring. The engine continues to refuse duplicate,
missing-target, missing-session, invalid, stale, or insufficient stock candle
histories; benchmark absence is explicitly rejected as unavailable rather than
misrepresented as weak or zero relative strength.
A dedicated market-benchmark identity and daily-candle table persist Nifty 500
inputs without pretending the index is a company. Live analysis upserts the
benchmark and stock series in the same transaction, and the local backtest loads
the stored benchmark by its stable `NIFTY_500` code.
A live onboarding handler requires an active provider identity before it upserts
a rolling window, calculates and stores an immutable analysis snapshot, and
changes tracking to `READY`. It has no corporate-action provider capability.

The HTTP boundary now applies exact host/origin configuration, a bounded request
body, security headers, Argon2 authentication, opaque HttpOnly sessions, and
CSRF validation. Hosted configuration must set secure cookies, production
hosts/origins, secret backend environment variables, and disable API docs.
Current verification is 268 backend tests, 46 frontend tests, a passing frontend
production build, and a migrated PostgreSQL schema at revision `b2d4f6a8c013`.

Remaining milestone-7+ work is live instrument import/reconciliation,
fundamental response adapters, executable retrying worker/nightly commands, fundamental research
and stock-detail API/UI, backtest/reporting, final browser/security quality
checks, and deployment configuration. These items must not be represented as
complete merely because their schema boundaries exist.
