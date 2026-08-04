# Interview guide

## Two-minute walkthrough

“This is an end-of-day NSE research tool built as a modular FastAPI monolith
with React and PostgreSQL. Each user selects authoritative Upstox listings,
the backend stores durable work, resolves provider identity, fills
daily candle gaps, refuses incomplete history, and saves an immutable result.
Users see the latest valid research for their own watchlists while instruments,
candles, fundamentals, and calculations are shared rather than duplicated.
Security uses Argon2, opaque HttpOnly sessions, CSRF, exact hosts/origins, and
backend-only provider credentials. Docker runs the same app locally and in CI.”

## Likely questions

**Why Company and Instrument separately?** A business can have multiple or
changing listings; the tradable security lifecycle should not overwrite company
identity.

**Why Decimal instead of float?** Binary floating point cannot exactly represent
many prices; Decimal/Numeric makes persisted monetary calculations predictable.

**How are duplicate candles prevented?** A unique instrument/date constraint
plus idempotent upsert makes imports safe to retry.

**Why retain analysis history if the UI shows one row?** History supports
reproducibility and evaluation while the read query cheaply selects the latest
valid result.

**What happens when an update fails?** The durable update records a safe failure
state, but the previous immutable analysis remains visible.

**How do multiple processors avoid claiming the same row?** PostgreSQL
`FOR UPDATE SKIP LOCKED` serializes each claim without blocking other eligible
rows.

**Why not hold the transaction during Upstox calls?** Network latency would keep
locks open, reduce concurrency, and make cancellation/recovery harder.

**How do you avoid look-ahead bias?** Each historical signal is calculated only
from the candle prefix available on that date.

**Why no Redux?** TanStack Query owns server state and local state handles forms;
there is no complex client-only global state requiring Redux.

**What is the CSRF defense?** The browser must send both the session cookie and a
matching readable CSRF cookie value in a custom header on mutations.

**Can React access the session token?** No. It is in an HttpOnly cookie; React
stores only the safe session response.

**Why proxy `/api` in deployment?** Same-origin requests keep secure cookies
reliable and avoid exposing credentials or relying on third-party cookie rules.

**How are stock splits handled?** V1 uses an explicit manual reset: the
administrator deletes the affected instrument globally and adds it again, which
fetches a new complete window. The tradeoff is lost research continuity.

**Why are normal-user and administrator deletes different?** A normal user owns
only their membership, so shared research remains. An administrator can perform
an explicit confirmed global purge when a clean provider refresh is required.

**What if two users add the same stock?** Two membership rows point to one
instrument and one shared tracking/analysis lifecycle, so provider work is not
duplicated.

**When does removing a stock stop analysis?** Normal-user removal stops shared
tracking only for the last follower. Administrator removal immediately deletes
the instrument, all memberships, research, and durable jobs; an in-flight worker
treats the missing job as cancellation.

**How is the 20-stock limit concurrency-safe?** The backend locks the user row,
counts active memberships, and commits the whole batch atomically.

**What would you scale first?** Measure provider/database bottlenecks, then add
batching, rate limits, multiple claimers, managed queues, and observability.

## Demonstration sequence

1. Show the separate login page and protected-route redirect.
2. Sign in and explain why the session token never enters React state.
3. Search Upstox in the modal, select multiple companies, and save one batch.
4. Show database constraints and a focused provider/domain test.
5. Run the historical report and explain look-ahead/survivorship limitations.
6. Contrast normal-user soft removal with administrator global delete/re-add.
