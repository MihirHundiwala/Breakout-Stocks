# Deployment guide

This repository contains deployment configuration but does not deploy itself.
The planned personal V1 uses Neon PostgreSQL, Render for FastAPI, Vercel for the
React SPA, and GitHub Actions for verification and the weekday post-market run.

## 1. Hosted PostgreSQL

Create a dedicated database and least-privilege application user. Record the
host, port, database, username, and password in platform secret stores. Hosted
connections set `POSTGRES_SSLMODE=require`; use `verify-full` when the provider
and certificate setup are confirmed.

Do not put a database URL or password in a Vite variable. PostgreSQL must never
be reachable directly from browser code.

## 2. Render API

Create the service from the root `render.yaml`. Enter every `sync: false` value
in Render rather than committing it:

- `POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_DB`, `POSTGRES_USER`,
  `POSTGRES_PASSWORD`
- `ADMIN_USERNAME`, `ADMIN_PASSWORD_HASH_B64`
- `UPSTOX_ACCESS_TOKEN`
- `ALLOWED_HOSTS` as a comma-separated allowlist containing only the exact
  Render API hostname and final Vercel frontend hostname (the proxy may preserve
  the public Host header)
- `METRICS_BEARER_TOKEN`, generated as a long random secret and supplied only
  to the Prometheus scraper

The blueprint enables secure cookies, watchlist mode, request limits, and no API
documentation. It runs `alembic upgrade head` before release and checks `/ready`.
The container launcher reads Render's `PORT` value.

The blueprint enables `/metrics` with bearer-token protection. Keep that route
private at the network layer when the platform supports it. The admin UI uses
`/admin/analytics`; it is session-protected and is not a replacement for the
time-series metrics endpoint.

Use a read-only Upstox Analytics Token. It is valid for one year according to
Upstox and must be rotated before expiry. A normal OAuth token expires at 3:30
AM the next day and is not appropriate for unattended annual operation.

Official references: [Render Blueprint specification](https://render.com/docs/blueprint-spec),
[Upstox Analytics Token](https://upstox.com/developer/api-documentation/analytics-token/).

## 3. Vercel SPA and same-origin API

After Render assigns the final HTTPS hostname:

1. Copy `frontend/vercel.json.example` to `frontend/vercel.json`.
2. Replace `REPLACE-WITH-YOUR-RENDER-HOST` with that hostname.
3. Configure the Vercel project root as `frontend`.
4. Verify `/stocks/{id}` deep links and `/api/ready` before enabling admin use.

The first rewrite proxies `/api/*` to Render and the second serves `index.html`
for React Router routes. This preserves first-party cookies and avoids placing
credentials or a privileged API key in the frontend. Do not enable CDN caching
for administrator or mutable API responses.

Official references: [Vercel external rewrites](https://vercel.com/docs/routing/rewrites),
[Vite SPA routing on Vercel](https://vercel.com/docs/frameworks/frontend/vite).

## 4. GitHub Actions secrets

Add repository Actions secrets with these exact names:

- `POSTGRES_HOST`
- `POSTGRES_PORT`
- `POSTGRES_DB`
- `POSTGRES_USER`
- `POSTGRES_PASSWORD`
- `UPSTOX_ACCESS_TOKEN`

`ci.yml` uses only placeholder local settings. `nightly.yml` runs at 4:00 PM
Asia/Kolkata Monday-Friday, applies migrations, schedules active companies, and
waits through bounded retries. The application still checks the exchange
calendar and latest completed session, so a weekday schedule does not assume a
weekday is always a trading day.

Official reference: [GitHub Actions schedule syntax](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax#onschedule).

Use GitHub environment protection if the repository later has multiple
operators. Rotate a leaked or expired credential in every runtime secret store;
never commit a replacement.

## 5. Acceptance checks

- `/health` returns liveness and `/ready` confirms database access.
- `/docs` and `/openapi.json` are unavailable in production.
- Direct requests with an unexpected Host are rejected.
- Visitors cannot call administrator routes.
- Login cookies include `Secure`, `HttpOnly` for the session, and `SameSite=Lax`.
- Vercel `/api` requests work without cross-site cookie warnings.
- Adding one company produces market research for the latest completed session.
- No secret appears in browser assets, logs, workflow output, or error messages.

## 6. Horizontal deployment

Use one Uvicorn process per container and scale containers/pods. Before changing
replica counts, ensure this worst-case connection budget remains below the
database provider limit:

```text
api replicas * (api pool size + api overflow)
+ worker replicas * (worker pool size + worker overflow)
+ migrations, monitoring, and operator reserve
```

Run Alembic once as a release job, not from every replica. All pods must share
the same PostgreSQL database and provider credentials. Prometheus should scrape
every API pod and aggregate the series; do not enable the Python client's local
multiprocess mode when each pod has one process. See `SCALING.md` for readiness,
rolling-update, worker, and metrics guidance.
