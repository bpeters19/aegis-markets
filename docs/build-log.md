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

---

## Entry 5: Event-driven engine and first strategy
**Date:** Oct 5, 2026

**What I built:** The core event loop. Immutable `BarEvent` and `SignalEvent` types, a FIFO event bus where components subscribe to event types instead of calling each other directly, a historical bar feed that merges multiple symbols into one chronological stream, and a rolling `BarHistory` window that is the only data a strategy ever receives. Added a `Strategy` interface and a moving-average crossover strategy (buy when the 10-day SMA crosses above the 30-day, sell when it crosses below) with stop-loss and profit targets rounded to the penny. Built a CLI that runs strategies over the bars stored in Postgres.

**Tech:** Python dataclasses (frozen, slots), collections.deque, heapq k-way merge, abstract base classes, Decimal arithmetic, pytest

**Why this matters in finance:** Look-ahead bias, accidentally using future data to make a past decision, is the most common reason backtests look great and then fail with real money. Vectorized pandas backtests make it easy to do by accident. An event-driven engine processes one bar at a time, the same way a live system receives data, so the same code can eventually run backtests and live trading.

**Decisions I made:**
- Made look-ahead impossible by structure instead of relying on being careful. The engine pulls one bar from the feed, fully processes every event it causes, and only then reads the next bar. Strategies only get an immutable tuple of past bars ending at the current bar.
- Strategies emit signals, not orders. They say what they'd like to do and where the stop and target are, but they never size positions or touch money. That's the risk engine's job.
- Kept strategies stateless, so the same history always produces the same signals. That makes them deterministic and easy to test.
- Rounded stops and targets to $0.01 because US stocks above $1 trade in penny increments.
- Used Pydantic for validation at the edges of the system and lightweight frozen dataclasses inside the engine, since the event loop is the hot path.
- Merged per-symbol series with heapq.merge (O(n log k)) since each series is already sorted, instead of re-sorting everything.

**How I verified it:** Wrote tests proving a strategy never sees a bar newer than the current one, that the engine never pulls the next bar from the feed before finishing the current one (checked by wrapping the feed in a generator that records what it has released), that each strategy only sees its own symbol, and that replaying the same data always produces identical signals.

**Results:** Ran the 10/30 SMA crossover over 2,500 real daily bars (10 symbols, all of 2025): 67 signals in 53 ms, about 47,000 bars per second in pure Python with exact decimal math. The first signal came Feb 18, after the 31-bar warm-up period. The output showed whipsaw during the April 2025 tariff selloff (TSLA flipped BUY/SELL/BUY/SELL in one week) and nine correlated BUY signals between May 1 and May 6, which is a concrete reason the risk engine needs exposure and position-count limits. These are signals only; no returns are measured until the backtester exists.

**Commits:** `Add event-driven signal engine with look-ahead-safe bar history and SMA crossover strategy`

**Things I can talk about in interviews:** What look-ahead bias is and how I made it structurally impossible and then proved it with tests, event-driven vs. vectorized backtesting, why strategies should be separated from risk and execution, k-way merging of sorted streams, and why I measured a performance baseline before optimizing.

---

## Entry 6: Risk engine
**Date:** Oct 5, 2026

**What I built:** A pre-trade risk engine that every signal has to pass through. For BUY signals, it sizes the position from the stop distance (1% of equity at risk per trade by default), then caps that size by max position size, remaining exposure, and buying power, and records which limit was the binding one. It then runs every check: kill switch, stop-loss required and below entry, no duplicate positions, max open positions, daily loss limit, max position size, max risk per trade, max total exposure, and buying power. It returns APPROVED or REJECTED with every failed reason, not just the first. SELL signals are approved only if there is an actual position to exit. Limits are a validated config model, and the kill switch is runtime state with halt() and resume().

**Tech:** Python, Decimal arithmetic, Pydantic (validated config), frozen dataclasses, pytest

**Why this matters in finance:** Pre-trade risk checks are the last line of defense before an order reaches the market, and they run on every single order. Getting position sizing right is what keeps one bad trade from doing outsized damage to an account.

**Decisions I made:**
- Risk-reducing orders are never blocked. When the kill switch is on or the daily loss limit is hit, new entries are rejected but exits still go through ("reduce-only" mode). A risk system that traps you in a losing position is worse than no risk system.
- Made evaluate() a pure function of the signal and a portfolio snapshot, with no database calls and no side effects, so it's deterministic, fast, and easy to test.
- Supported two modes with the same checks: size the position automatically within limits, or validate an explicitly requested size and reject it if it breaks a limit.
- Percent limits are validated to be between 0 and 1 and exposure can't exceed 100%, so a config typo can't accidentally allow leverage.
- Collected every failed check instead of stopping at the first one, so a rejection explains everything that was wrong.

**How I verified it:** 12 tests, including the exact example from my original spec (a $20,000 NVDA order on a $100,000 account is rejected because it's 20% of equity against a 10% limit), sizing by risk vs. by position cap, exposure limits, the daily loss limit, duplicate positions, and the kill switch blocking entries while still allowing exits. 53 tests passing total.

**Results:** Replayed the 10/30 SMA crossover over all of 2025 for 10 symbols with a $100,000 account, by subscribing the risk engine to the event bus without changing the signal engine's code: 37 signals approved, 30 rejected (14 for max open positions, 16 SELLs with no position). The May cluster I spotted in Week 3 got handled exactly as expected: after 5 positions filled, the next 5 BUYs were rejected.

**What the replay taught me:**
- With a 5% stop, the 10% position cap always binds before the 1% risk limit, so real risk per trade was about 0.5%. Limits interact, and you have to check which one is actually doing the work.
- The demo book didn't enforce stops. AMD was bought at $114.81 with a stop at $109.07 (planned risk $482), but it was held down to $83.64, a loss of about $2,620, more than 5x the plan. Risk sizing only works if stops are actually executed, and even real stop orders fill below the stop when a stock gaps down overnight (gap risk). The Week 5 execution simulator needs to model this honestly.
- Limits cost upside too. NVDA was rejected on May 5 at $113.53 for max positions and was at $170 by September. Whether the limits help overall is something the backtester has to measure.
- The replay used a demo-only book that fills instantly at the signal price, so these numbers are not performance results.

**Commits:** `Add pre-trade risk engine with position sizing, configurable limits, and reduce-only kill switch`

**Things I can talk about in interviews:** How to size a position from a stop distance, why exits should never be blocked by risk limits, gap risk and why a stop-loss doesn't guarantee your max loss, how different limits interact, and why risk limits are a trade-off rather than free protection.

---

## Entry 7: Order management system
**Date:** Oct 5, 2026

**What I built:** An order management system between approved risk decisions and execution. Orders move through an explicit state machine (PENDING, SUBMITTED, PARTIALLY_FILLED, FILLED, CANCELLED, REJECTED) defined as a table of legal transitions, and anything else raises an error. Orders, fills, and an audit log are stored in Postgres through new Alembic migrations. Every state change writes an audit row in the same transaction as the change itself.

**Tech:** PostgreSQL 18 (unique constraints, CHECK constraints, PL/pgSQL triggers, JSONB), SQLAlchemy 2.0 (savepoints, optimistic locking), Alembic, pytest

**Why this matters in finance:** The OMS is the source of truth for what the system has actually done. Duplicate orders and double-counted fills are classic real-world trading bugs, and firms have to be able to reconstruct exactly what happened to every order for regulators.

**Decisions I made:**
- Idempotent orders: every order has a client_order_id. A retried submit returns the existing order instead of creating a new one, and reusing an ID with different details raises a conflict. A unique constraint backs this up, and a savepoint handles the case where two processes race to insert the same ID.
- Client order IDs for strategy orders are built from the signal itself (strategy, symbol, action, timestamp), so replaying the same signal can never create a second order.
- Idempotent fills: every fill carries the broker's execution_id with a unique constraint, so duplicate execution reports are ignored instead of double-counting shares.
- The audit log is append-only at the database level. A Postgres trigger rejects UPDATE, DELETE, and TRUNCATE on order_events, so even raw SQL can't edit history.
- Stored both occurred_at (event time, which is simulated time in a backtest) and recorded_at (when the database wrote it).
- The average fill price is derived from the fills table instead of being updated incrementally, so rounding errors can't build up.
- Added a version column for optimistic locking, so two processes updating the same order can't silently overwrite each other.
- Added `alembic check` to CI so the build fails if models and migrations ever drift apart.

**Problems I ran into:**
- My script for writing the trigger migration replaced a placeholder with PowerShell's -replace, which is case-insensitive, so it also mangled the `down_revision` line. Switched to -creplace (case-sensitive).
- Ran pytest from the repo root instead of backend, so .env and pytest.ini weren't found. Changed the config to locate .env relative to the config file itself.
- The demo printed 08:30 for an order placed at 14:30 UTC. Postgres on Windows was returning timestamps in local time. The data was right, but I forced every database connection to UTC so the system never depends on server settings.
- The audit log recorded the average price with 28 decimal places while the orders table stores 6. Fixed it by rounding to the column's precision before saving, so the audit log matches exactly what was stored.

**How I verified it:** 17 new tests: the full lifecycle with partial fills, idempotent creates, conflicting client IDs, duplicate execution reports, overfill rejection, cancelling a partially filled order, illegal transitions, and a test that tries to UPDATE and DELETE audit rows with raw SQL and confirms Postgres refuses both. Database tests run inside a transaction that's rolled back afterward, which is necessary since the audit log can't be deleted from. 70 tests passing.

**Results:** A dry run of the real Feb 19, 2025 NVDA signal: 72 shares filled in two partial fills (30 at $138.90 and 42 at $138.95) for an average of $138.929167. The retry returned the same order, the duplicate fill report was ignored, cancelling the filled order was refused, and the audit trail had exactly four events: CREATED, SUBMITTED, FILL, FILL.

**Commits:** `Add order management system with state machine, idempotent orders and fills, and append-only audit log`

**Things I can talk about in interviews:** Order state machines, idempotency for both orders and fills, why audit logs need to be append-only and how to enforce it at the database level, event time vs. processing time, optimistic locking, and why a trading system should never depend on the server's time zone.
