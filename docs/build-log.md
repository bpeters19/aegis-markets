# Aegis Markets Dev Log

My notes on what I built at each step, why I built it that way, what broke, and what I learned. One entry per milestone.

---

## Entry 1: Getting the backend running
**Date:** Oct 1, 2026

**What I built:** A FastAPI app set up with an app factory (`create_app()`), a versioned API under `/api/v1`, and a `/health` endpoint that returns the service name, version, environment, and a UTC timestamp. Settings load from environment variables with pydantic-settings. Wrote the first pytest test against the health endpoint.

**Tech:** Python 3.13, FastAPI, Pydantic, pydantic-settings, pytest, Git, GitHub

**Why this matters in finance:** Trading systems are made of a lot of small services that each get monitored on their own, so a health check is one of the first things every service needs. I also learned that time-zone bugs are a common problem in trading software, which is why every timestamp here is explicitly UTC.

**Decisions I made:**
- Returned a typed Pydantic model instead of a plain dict, so the response shape is enforced. Later this same approach will apply to orders and signals, where a malformed message could actually cost money.
- Versioned the API from day one so I can make breaking changes in a v2 without breaking anything calling v1.
- Kept config in environment variables so passwords and API keys never end up in the code.

**Problems I ran into:**
- Python wasn't recognized after installing it. VS Code keeps the old PATH until every window is closed, and I still had another project open.
- My .gitignore ended up empty because the file never actually saved, so all the __pycache__ files got staged. I caught it by reading git status before committing and cleaned up the staged files.

**Commits:** `Initialize FastAPI backend with versioned health endpoint and test`

**Things I can talk about in interviews:** Why the app factory pattern makes testing easier, why API versioning matters to whoever consumes your API, and why timestamps in a trading system need to be time-zone aware.

---

## Entry 2: Connecting PostgreSQL and adding a readiness check
**Date:** Oct 1, 2026

**What I built:** Connected the app to PostgreSQL 18 with SQLAlchemy 2.0 and psycopg 3. The engine uses a connection pool with `pool_pre_ping`, and each request gets its own database session through FastAPI dependency injection. Added a `/ready` endpoint that runs `SELECT 1` against the database and returns a 503 if it can't connect. Wrote a unit test that fakes a database failure and an integration test that hits the real database.

**Tech:** PostgreSQL 18, SQLAlchemy 2.0, psycopg 3, FastAPI dependency injection, pytest markers

**Why this matters in finance:** A market-data or order service that's still running but can't reach its database should be taken out of rotation, not restarted. That's the whole point of having separate health and readiness checks. Health means the process is alive, ready means it can actually do its job.

**Decisions I made:**
- Returned 503 instead of 500. A 503 tells a load balancer the service is temporarily unavailable and to send traffic somewhere else. A 500 means there's a bug.
- Logged the real database error on the server and kept it out of the API response, so connection details never leak.
- Made the database URL a required setting with no default. If it's missing, the app fails right away at startup instead of quietly connecting somewhere it shouldn't.
- Split tests into unit and integration with a pytest marker, so I can run the fast ones without a database.

**Problems I ran into:**
- Password authentication kept failing because the password in my .env didn't match the database user. Fixed it with ALTER USER.
- Old editor tabs in VS Code kept overwriting files I had just written from the terminal. Now I close all tabs before writing files from the terminal.

**How I verified it:** Stopped the Postgres Windows service while the API was running and watched `/ready` switch to unreachable. When I started the service again it recovered on its own without restarting the API, which is `pool_pre_ping` doing its job.

**Commits:** `Add PostgreSQL connection pooling and database readiness probe`, `Document required DATABASE_URL in env example`

**Things I can talk about in interviews:** Liveness vs. readiness probes, what connection pooling is and why stale connections are a problem in long-running services, and how I used dependency injection to test a failure case without needing real infrastructure.

---

## Entry 3: Migrations and CI
**Date:** Oct 1, 2026

**What I built:** Set up Alembic for database migrations, reading the database URL from the same settings as the app. Created a shared SQLAlchemy base class with a naming convention for constraints. Set up a GitHub Actions workflow that starts a PostgreSQL 18 container, waits for it to pass a health check, runs migrations, and runs all the tests on every push. Added .gitattributes to force LF line endings and put the CI status badge on the README.

**Tech:** Alembic, GitHub Actions, Docker service containers, PostgreSQL 18

**Why this matters in finance:** Changes to tables like orders, trades, and positions get reviewed and audited just like code changes. Migrations keep a history of every schema change, and CI proves the project works on a clean machine and not just on my laptop.

**Decisions I made:**
- Added the constraint naming convention so future migrations can find and change constraints by name. Without it, Postgres generates names that are hard to predict.
- Kept the CI database password separate from anything real. It's a throwaway database that only exists for a few minutes during each run. Real keys, like broker API keys later, will go in GitHub's encrypted Secrets.
- Normalized line endings in the repo itself, since I develop on Windows and CI runs on Linux.

**Problems I ran into:**
- Docker Desktop wouldn't start because hardware virtualization is disabled on this machine. I installed PostgreSQL natively for local development, and CI still runs Postgres in Docker, so the setup works the same either way.

**Result:** CI passed on the first run. Every push now runs 3 tests against a real PostgreSQL 18 database.

**Commits:** `Normalize line endings with .gitattributes`, `Add Alembic migrations and GitHub Actions CI with PostgreSQL 18`

**Things I can talk about in interviews:** How to handle schema changes safely, what CI service containers and health checks are for, and how I separated secrets between local development, CI, and eventually production.

---

## Entry 4: Market data pipeline
**Date:** Oct 5, 2026

**What I built:** A `bars` table for OHLCV data with a composite primary key on symbol, timeframe, and timestamp, plus CHECK constraints that reject impossible bars at the database level. A validated `Bar` model that normalizes symbols, requires time-zone-aware timestamps and converts them to UTC, and rejects bars where the prices don't make sense (high below low, close outside the range, negative volume). A `MarketDataProvider` interface with three implementations: a fake provider for tests, a Tiingo provider for real end-of-day data, and an Alpaca provider. Idempotent ingestion using Postgres upserts in batches of 1,000, a CLI to ingest multiple symbols at once, and a `GET /api/v1/bars` endpoint.

**Tech:** PostgreSQL 18 (upserts, CHECK constraints), SQLAlchemy 2.0, Alembic, Pydantic validators, httpx with mocked transports for testing, Tiingo REST API

**Why this matters in finance:** Every strategy, backtest, and risk calculation downstream depends on this data being right. One bad bar can trigger a fake signal, and floating-point rounding errors add up across P&L calculations. Vendors also publish corrections, so the pipeline has to handle data changing after it's already been stored.

**Decisions I made:**
- Stored prices as `Numeric` instead of floats, and parsed the vendor's JSON straight into `Decimal` so precision is never lost between the API and the database. The API returns prices as strings for the same reason.
- Validated data in two places: the `Bar` model rejects bad data in Python, and CHECK constraints in Postgres act as a second line of defense.
- Made ingestion an upsert so re-running it never creates duplicates, and so vendor corrections overwrite the old values.
- Tagged every row with its source (like `tiingo-adjusted`) and an `ingested_at` time, so I can always trace where a number came from and whether it's split/dividend adjusted.
- Used half-open time ranges `[start, end)` everywhere so back-to-back queries never double-count a bar.
- Bad bars from a vendor get logged and skipped instead of failing the whole batch. Bad API keys fail immediately, while rate limits and server errors retry with exponential backoff.
- Injected the HTTP client and the sleep function into the providers, so tests run against fake responses and can check retry timing without actually waiting.

**Problems I ran into:**
- Alpaca's signup CAPTCHA kept failing, so I couldn't get API keys. Because everything goes through the provider interface, I switched to Tiingo by adding one new provider file, and nothing else in the system changed. The Alpaca provider is still in the repo and tested against a mocked API, and I'll connect it once the account works.
- Different vendors timestamp daily bars differently (Tiingo uses midnight UTC, Alpaca uses midnight New York time). That's part of why every row records its source.

**Results:** Ingested 2,500 real daily bars for 10 symbols (NVDA, AAPL, MSFT, AMD, TSLA, SPY, QQQ, META, AMZN, GOOGL) in under 2 seconds. Each symbol returned 250 bars, which matches the number of NYSE trading days in 2025. 29 tests passing in CI, including idempotency and vendor-correction tests against a real Postgres database.

**Commits:** `Add bars table, validated market data model, and idempotent ingestion`, `Add Tiingo and Alpaca market data providers with retries, pagination, and exact decimal parsing`

**Things I can talk about in interviews:** Why money should never be stored as floats, what idempotency means and why data pipelines need it, how upserts handle vendor corrections, data lineage, why I designed around a provider interface (and how it paid off when Alpaca didn't work out), and how I tested retry logic without real network calls.
