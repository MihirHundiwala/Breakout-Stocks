# AGENTS.md

## Purpose

This repository is both a working Breakout Stocks application and a guided
learning project. Anyone changing it—including Codex—must optimize for
understanding, interview readiness, correctness, and small verified steps.

`PROJECT_PLAN.md` is the source of truth for product scope and architecture.
Read this file and `PROJECT_PLAN.md` before every major implementation decision.

## Required collaboration workflow

Do not generate the entire project or a large unexplained scaffold at once.

Use the detailed learning workflow for non-trivial application work, including:

- frontend components, routing, state, API communication, and user flows;
- backend routes, services, validation, authentication, background jobs, and
  provider integrations;
- database models, relationships, constraints, transactions, migrations, and
  query design;
- technical indicators, status classification, fundamental calculations,
  screening, retention, and other domain logic;
- architectural choices, meaningful dependencies, failure handling, and tests.

For each such step:

1. State the small outcome being attempted.
2. Explain the concept in plain language.
3. Explain why it belongs in this architecture and what simpler alternatives
   exist.
4. Explain the interview relevance and likely questions.
5. Show and explain each command before running it.
6. Name every file to be created or changed and explain its responsibility.
7. Implement only the agreed small slice.
8. Explain important code paths and non-obvious choices.
9. Run focused tests or verification.
10. Explain the observed output and investigate failures before continuing.
11. Summarize what the learner should remember.
12. Stop before the next major milestone unless the user explicitly asks to
    continue.

Ask the user to type commands or code when that improves learning. Codex may
implement requested changes directly, but must not hide the reasoning behind a
large patch.

Routine setup does not require the full interview-style explanation. Codex may
directly create or update standard files and defaults such as `.gitignore`,
basic directories, conventional formatter/linter configuration, placeholder
environment files, and other obvious project housekeeping. Briefly summarize
what changed and verify it, but do not spend time explaining elementary commands
or boilerplate unless the user asks.

## Scope and architecture guardrails

- Build an end-of-day NSE research tool, not a trading/execution system.
- Keep the backend a modular FastAPI monolith.
- Use PostgreSQL, SQLAlchemy 2, and Alembic.
- Use React, TypeScript, Vite, Tailwind CSS v4, React Router, TanStack Query,
  Axios, and limited React Context.
- Run local services with Docker Compose; local Python and Node installations
  must not be required.
- Keep market-data, fundamentals, document-AI, and storage integrations behind
  explicit adapters/interfaces.
- Document upload, extraction, embeddings, semantic retrieval, and
  company-specific document Q&A are deferred until after V1. Do not create their
  schemas, dependencies, endpoints, jobs, storage, or UI during V1.
- Prefer direct, typed, conventional code over metaprogramming or framework
  magic.
- Prefer configuration for thresholds, modes, and retention policies; avoid
  unexplained magic numbers.
- Do not add Bootstrap alongside Tailwind.
- Do not add Redux, Next.js, Create React App, jQuery, a vector database,
  LangChain/LlamaIndex, microservices, queues, or new cloud services without a
  demonstrated requirement and an architecture decision record.
- Do not implement deferred milestones opportunistically.

## Data and domain correctness

- Use `Decimal`/database numeric types for monetary and price values where
  floating-point error matters.
- Store market dates and reporting periods explicitly; use timezone-aware UTC
  timestamps for events and record the source/fetch time.
- Enforce idempotency and database uniqueness for imports and retryable jobs.
- Never calculate a signal from incomplete or stale candle history.
- Never label watchlist-relative data as a market-wide percentile.
- Treat missing fundamentals as `unknown`, never as zero or a failed check.
- Always expose fundamental coverage with the displayed data.
- Do not introduce technical, fundamental, catalyst, or composite scores unless
  the product plan is explicitly revised again.
- Keep indicator, status-classification, and derived-calculation versions with
  generated results so outcomes can be reproduced.
- Prevent look-ahead bias in backtests and disclose survivorship bias.
- Every catalyst presented as verified research needs a source document, page,
  and evidence excerpt.
- AI output is untrusted input: validate its schema, citations, and ranges before
  persistence or display.

## Security and secrets

- Never open, print, quote, commit, or transmit `keys.txt`.
- Never commit `.env*` files containing values, API keys, tokens, passwords,
  uploaded PDFs, database volumes, backtest caches, or generated private data.
- Commit only documented placeholder environment files such as `.env.example`.
- Keep Upstox, Gemini, database, storage, and admin credentials backend-only.
- Never expose secrets through frontend environment variables, logs, exceptions,
  fixtures, screenshots, command output, or test snapshots.
- Use only public company documents with free-tier external AI services.
- Validate uploads by type and size; generate safe storage names rather than
  trusting user filenames.
- Do not delete or move `keys.txt` without explicit user approval. When secret
  setup begins, guide the user to transfer values into the ignored environment
  file without displaying them.

## Code organization and quality

- Use clear names and small functions focused on one responsibility.
- Separate HTTP routes, application services, domain calculations, persistence,
  provider clients, and configuration.
- Keep domain calculations pure where practical so they are easy to unit test.
- Add types at public boundaries; avoid `Any` and unvalidated dictionaries when
  a Pydantic model, dataclass, or TypeScript interface is appropriate.
- Validate external responses before the domain layer sees them.
- Use structured errors and actionable UI states; do not swallow exceptions.
- Use structured logging without secrets or full document content.
- Add comments for business reasoning or surprising constraints, not to restate
  obvious code.
- Keep accessibility and responsive behavior in UI acceptance criteria.
- Update nearby documentation when behavior or architecture changes.

## Database and migration rules

- Schema changes require an Alembic migration; changing only an ORM model is
  incomplete.
- Review autogenerated migrations and give them meaningful names.
- Add database constraints for invariants and indexes for demonstrated query
  patterns.
- Keep migrations forward-safe and test them against the Dockerized PostgreSQL
  service.
- Use transactions for multi-record operations such as removing a stock, while
  making external file deletion retryable and observable.
- Never destroy or reset user data as a shortcut for fixing a migration.

## Testing rules

- Every business rule change must include or update focused tests.
- Use synthetic/fixture data for normal automated tests.
- Keep live Upstox and Gemini tests opt-in and clearly labeled; never run them
  accidentally in CI.
- Test success, empty, stale/incomplete, permission, provider-error, and retry
  paths where relevant.
- Keep tests deterministic: freeze dates/times and mock network boundaries.
- Run the smallest relevant check first, then the broader affected suite.
- For container or UI changes, verify the real Docker/browser path rather than
  relying only on isolated unit tests.
- Report exactly which commands ran, what passed, and what was not tested.

## Commands and dependencies

- Explain each new command and important flag before execution.
- Prefer commands that work from the repository root in PowerShell.
- Run application language tools inside Docker unless a documented bootstrap
  step explicitly says otherwise.
- Pin or constrain dependency versions intentionally and explain new packages.
- Before using a provider/library integration, consult its current official
  documentation because APIs and recommended setup can change.
- Do not install global Windows packages or change machine settings without
  explicit user approval.

## Git workflow

- Before editing, inspect `git status` and preserve unrelated user changes.
- Make small, coherent commits only when the user asks or approves committing.
- Explain the value of each commit and suggest an interview-readable message.
- Never commit secrets or generated local data.
- Do not use destructive Git commands to discard work.
- Do not push, publish, deploy, or open a pull request unless explicitly asked.

## Documentation and interview relevance

Each completed slice should leave enough documentation for the user to explain:

- the problem it solves;
- why the chosen design fits the current scale;
- its tradeoffs and reasonable alternatives;
- failure modes and data-quality risks;
- how it is tested; and
- how it would evolve for production scale.

Prefer honest statements such as “designed for a personal 20-stock EOD
watchlist” over unsupported claims of production readiness. The quality signal
is sound judgment, explicit tradeoffs, and verified code—not the number of tools
used.

## Completion checklist for every slice

Before calling a step complete, confirm:

- scope matches `PROJECT_PLAN.md`;
- files and commands were explained;
- secrets and user data are protected;
- focused tests pass;
- errors and incomplete states are handled;
- documentation reflects the behavior;
- interview takeaways were summarized; and
- the next major slice has not been started without user direction.
