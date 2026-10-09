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

---

## Entry 8: Execution simulator
**Date:** Oct 6, 2026

**What I built:** A stateless execution simulator that turns working orders into fills one bar at a time. Market orders fill at the open plus slippage and are capped at 10% of bar volume, so a large order fills partially across several bars. Sell stops fill at the open when the price gaps through them, or at the stop price when it only touches them during the bar. Take-profit limit orders fill at the limit or better with no slippage. Stops and targets can be linked as an OCO (one-cancels-other) bracket. Commission is per share with a per-order minimum, and slipped prices round against the trader.

**Tech:** Python, Decimal arithmetic with explicit rounding modes, Pydantic (validated cost model), frozen dataclasses, pytest

**Why this matters in finance:** A backtest is only as honest as its fill assumptions. The usual shortcuts (filling at the signal bar's close, ignoring costs, assuming stops always fill at the stop price) all make results look better than reality. Gap risk in particular means a stop-loss doesn't guarantee your maximum loss.

**Decisions I made:**
- An order can only execute on bars that start at or after it was submitted. Orders from a signal are submitted at the end of the signal bar, so the earliest fill is the next bar's open. Passing an order to an earlier bar raises an error, which is look-ahead protection at the execution layer.
- Bracket stops and targets attach when the entry fills at the open, so they can trigger later in that same bar.
- When a stop and a target could both have triggered inside one daily bar, I assume the stop happened first, unless the open gapped through one of them. Daily bars don't show the order of prices within the day, so I picked the pessimistic assumption on purpose.
- Slipped buy prices round up and sell prices round down, so rounding never flatters results.
- Execution IDs are deterministic (order ID plus bar time), so replays produce identical IDs and the OMS duplicate-fill protection works for simulated fills.
- Kept the simulator pure with no database or hidden state, so it's deterministic and fully unit tested.

**How I verified it:** 14 new tests covering market fills with slippage and commission, rounding direction, the look-ahead guard, intrabar stops, gap-through stops, limit fills with and without gaps, OCO priority on ambiguous bars and on gap-ups, sibling cancellation, partial fills on thin volume, and brackets triggering on the entry bar. 84 tests passing.

**Results:** Replayed the real Mar 25, 2025 AMD signal (84 shares, stop $109.07, target $126.29). The entry filled at the next open, $114.17 including slippage, instead of the $114.81 signal close. AMD dropped to $108.68 the same day, so the bracket stop filled at $109.01. Net loss was $435.44 including $2 in commissions, 0.90x the $482.16 planned risk. In my Week 4 replay, with no stop enforcement, the same trade lost about $2,618, roughly 5.4x the plan. AMD closed at $110.19 that day, above the stop, so a close-based exit rule would have stayed in while AMD fell to $83.64 over the next two weeks.

**Commits:** `Add execution simulator with next-bar fills, slippage, commissions, gap-aware stops, and OCO brackets`

**Things I can talk about in interviews:** Why filling at the signal bar's close is look-ahead bias, gap risk and how to model stop fills honestly, intrabar ambiguity with daily bars and why I chose the pessimistic assumption, OCO bracket orders, how slippage and commission are modeled, and the concrete AMD example showing a planned 1x risk turning into 5.4x without enforced stops.

---

## Entry 9: Portfolio engine and the full trading pipeline
**Date:** Oct 6, 2026

**What I built:** A portfolio engine with average-cost accounting that tracks cash, positions, realized and unrealized P&L, commissions, a daily equity curve, and every closed trade with its exit reason. Then I connected every component into one event-driven pipeline: strategy signal, risk check, OMS order, simulated fill, OMS fill record, portfolio update. When an entry fills, its stop-loss and take-profit are created as an OCO bracket through the OMS. When the strategy emits SELL, the bracket is cancelled before the exit order goes in. Backtest runs happen inside a rolled-back transaction by default, with a --persist flag to save them.

**Tech:** Python, SQLAlchemy 2.0, PostgreSQL 18, event-driven architecture, pytest

**Why this matters in finance:** This is the first time the system behaves like a real trading stack: every order goes through the same state machine, idempotency checks, and audit log a live system would use, and every number can be traced back to a fill.

**Decisions I made:**
- Ordered the event handlers to match a real trading day: working orders execute at the open, the strategy sees the completed bar, positions are marked to the close, and only then do new signals go through risk and become orders for the next bar.
- Risk counts working orders, not just filled positions. Without that, nine BUYs approved on the same evening would all pass, because none of them have filled yet.
- Cash and positions only change through apply_fill() and prices only through mark(). After every run, the portfolio checks the accounting identity (equity = starting cash + realized + unrealized - commissions) and fails if it doesn't hold.
- After every run, portfolio positions are reconciled against the net of all OMS fills for that run, and any mismatch (a "break") fails the run. Firms reconcile against their brokers daily.
- Fixed a flaw in my own bracket logic: stops and targets came from the signal's close, but entries fill at the next open. When the open had already gapped past the stop or the target, the system bought and sold at the same open. Now the entry is cancelled with an audit reason instead. I chose cancelling over re-anchoring the bracket to the fill price, because re-anchoring would change the risk the risk engine approved.

**How I verified it:** 10 new tests. Portfolio tests cover average cost across multiple buys, partial sells, rejecting oversells without changing state, mark-to-market, reserving cash for pending orders, and the daily equity curve. Pipeline tests run against Postgres with exact dollar amounts: a same-day stop-out (-$522.93), a take-profit exit (+$984.31), working orders counting toward the position limit, and an entry cancelled because the open gapped below its stop. 94 tests passing.

**Results:** Ran the full pipeline over 2025 for 10 symbols with $100,000: 2,500 bars, 87 orders, and 49 fills in 0.81 seconds, with the books balanced and positions reconciled. 22 closed trades: 9 wins and 13 losses, average win $1,113 and average loss $384. Final equity $104,590.59 (+4.59%) vs. +17.05% for buying and holding SPY.

**What the results taught me:**
- The strategy badly underperformed buy-and-hold. With at most 5 positions at about 10% each, it was never more than about half invested in a strong bull year, and the 10/30 crossover got whipsawed from February to May (11 of 22 trades were stopped out).
- One trade (AMD, Oct 3 to Oct 6, an overnight gap through the target) made $3,282, about 65% of realized profit. A result that depends on one outlier is fragile.
- Removing three tiny round-trip losses raised the win rate from 36% to 41% while profit changed by only $30, and the average loss went up. Win rate alone is misleading.
- This is one strategy, one parameter set, and one year, tested in-sample. It's the first honest result, not evidence that the strategy works. No return numbers go on my resume from this.

**Commits:** `Add portfolio engine and end-to-end trading pipeline with brackets, pending-order-aware risk, and OMS reconciliation`

**Things I can talk about in interviews:** Average-cost accounting and the accounting identity, why pre-trade risk has to count working orders, position reconciliation and what a break is, what happens to bracket orders when the open gaps through them, path dependence in backtests, outlier concentration, and why win rate is a misleading metric.

---

## Entry 10: Performance metrics and benchmark comparison
**Date:** Oct 6, 2026

**What I built:** A metrics module and backtest report. From the equity curve it computes total return, CAGR, annualized volatility, Sharpe and Sortino ratios (with a configurable risk-free rate), max drawdown with peak, trough, recovery date and length, and the Calmar ratio. Against a buy-and-hold benchmark it computes beta, correlation, and annualized alpha. From the trade list it computes win rate, payoff ratio, profit factor, expectancy, average holding period, and the share of profit from the single best trade. The portfolio now records daily exposure so the report can show how much of the time the strategy was actually invested.

**Tech:** Python statistics module, Decimal for money and float for statistics, pytest

**Why this matters in finance:** Return alone says nothing about the risk taken to get it. Every quant interview expects you to know Sharpe, Sortino, drawdown, and beta, and also where each one misleads.

**Decisions I made:**
- Kept money in Decimal but computed statistics in float. Accounting has to be exact to the cent, while square roots and correlations are estimates anyway, and Decimal can't do most of that math.
- Wrote every formula in plain Python instead of using pandas, so each metric is a few lines I can explain, and tested them against hand-computed values (for example, returns of [0.02, 0.00] give a Sharpe of 11.225).
- Undefined metrics, like a Sharpe ratio with zero volatility or a profit factor with no losing trades, return n/a instead of a misleading number.
- Added a best-trade-share metric after seeing one trade carry my Week 5 results. It can exceed 100%, which would mean the strategy lost money on everything except its best trade.

**Results (2025, 10 symbols, SMA 10/30, $100,000):**
- With a 0% risk-free rate: Sharpe 0.93 vs. 0.91 for SPY buy-and-hold, Sortino 2.10 vs. 1.38, max drawdown -2.70% vs. -18.76%, Calmar 1.72 vs. 0.92. Beta 0.06, correlation 0.23.
- Average exposure was only 13.36%. The strategy sat in cash about 87% of the time, which explains the low volatility, the small drawdown, and the near-zero beta.
- With a 4% risk-free rate, Sharpe drops to 0.13 (SPY: 0.71). But that comparison is unfair to the strategy: it charges a 4% hurdle while my simulation credits zero interest on idle cash, which a real account would have earned. An honest comparison needs cash interest modeled too.
- The best single trade (AMD) was 65.34% of net profit from closed trades.

**What I learned:** The same strategy looks competitive or nearly worthless depending on one assumption about the risk-free rate, and the honest answer depends on modeling cash consistently. Low exposure makes risk ratios look good without the strategy being skilled. One year in-sample with an outlier trade isn't evidence of an edge. No return or Sharpe numbers go on my resume from this run.

**Commits:** `Add performance metrics and backtest report with risk-adjusted benchmark comparison`

**Things I can talk about in interviews:** How Sharpe, Sortino, Calmar, and drawdown are calculated and where each one misleads, why the risk-free rate and cash interest have to be modeled consistently, beta and alpha and why one year of alpha is noise, exposure and why a mostly-cash strategy can look good on risk metrics, and concentration risk from a single outlier trade.

---

## Entry 11: Out-of-sample testing
**Date:** Oct 6, 2026

**What I built:** Research tools for testing whether a strategy holds up on data it was never tuned on. A parameter sweep over 12 fast/slow window pairs ranked by Sharpe; a holdout test that picks the best pair on one period and evaluates it on a later one; and a walk-forward test that, for each year, picks parameters using only the previous three years and then trades that year. Idle cash now earns a daily interest rate, and the same rate is used as the Sharpe risk-free rate, so cash is treated consistently. Backtests warm up indicators on history before the test period but ignore signals until it starts. Ingested 2017-2024 daily data for the same 10 symbols.

**Tech:** Python, argparse subcommands, PostgreSQL, the full trading pipeline running inside rolled-back transactions

**Why this matters in finance:** In-sample results always look better than reality because the choices were made knowing the answer. Separating the data used to choose parameters from the data used to judge them is the core discipline of quantitative research.

**Decisions I made:**
- Selected parameters by Sharpe ratio on training data only, and never looked at test-period results when choosing.
- Compared every result against a fixed baseline (10/30, never re-tuned) and against buy-and-hold SPY, so I could tell whether re-tuning added anything.
- Treated cash consistently: idle cash earns the same rate that's subtracted in the Sharpe ratio, so cash contributes zero excess return either way.
- Gave each test period a warm-up window so slow indicators like a 200-day average are ready on day one, without letting any pre-period signals create positions.

**Problems I ran into:**
- My CLI had `--symbols` accept any number of values before the subcommand, so it swallowed the command name as a symbol. Moved `--symbols` onto each subcommand so the list ends at the next option.

**Results:**
- Holdout (train 2018-2022, test 2023-2025): the in-sample winner, 20/30, had a Sharpe of 1.12 in-sample and 0.65 out-of-sample. Out-of-sample, SPY buy-and-hold returned +84.57% vs. +17.31% for the chosen parameters.
- Walk-forward (2021-2025): the chosen parameters changed almost every year (10/200, 20/30, 20/30, 10/30, 5/100). Average Sharpe of the chosen parameters fell from 1.29 in-sample to 0.14 out-of-sample. Compounded returns were +21.38% walk-forward, +43.99% for fixed 10/30, and +93.36% for SPY buy-and-hold.
- In 2022 the strategy returned about +0.8% while SPY lost 18.40%. Average exposure was about 18-21%.

**What I learned:**
- Optimizing this strategy's parameters is overfitting. The in-sample advantage almost entirely disappeared out of sample, and re-tuning every year did worse than never tuning.
- The fixed 10/30 looked best out of sample, but I've been studying 2025 with it since Week 3, so choosing it now because it did well would repeat the same selection mistake. The walk-forward result is the honest one.
- The strategy behaves like a defensive, low-exposure trend filter: much smaller drawdowns, but far lower returns than buy-and-hold in bull markets.
- Every result is inflated by survivorship bias, since these 10 stocks were picked because they're winners today. A real test needs a point-in-time universe. The flat 2% rate also understates the roughly 5% T-bill rates of 2023-2024.
- Conclusion: no evidence of a tradable edge in returns, some evidence of drawdown reduction, and strong evidence that parameter optimization overfits.

**Commits:** `Add cash interest, warm-up aware backtests, parameter sweeps, holdout and walk-forward testing`

**Things I can talk about in interviews:** In-sample vs. out-of-sample testing, walk-forward analysis, multiple-testing bias and Sharpe decay, survivorship and selection bias, parameter instability as a sign of no persistent edge, why a fixed baseline matters, and why "this strategy doesn't have an edge" is a legitimate research result.

---

## Entry 12: Backtest API
**Date:** Oct 6, 2026

**What I built:** A backtest service plus two API endpoints for the upcoming dashboard. GET /api/v1/symbols lists every stored symbol with its bar count and date range. POST /api/v1/backtests runs the full pipeline for any set of symbols, dates, moving-average windows, starting capital, and cash rate, and returns the strategy and benchmark metrics, beta, correlation and alpha, trade statistics, the daily equity curve with benchmark and exposure, every closed trade, and the pipeline's counters. Added CORS so the dashboard on localhost:3000 can call the API.

**Tech:** FastAPI, Pydantic request and response models, SQLAlchemy, CORS middleware, pytest

**Why this matters in finance:** Research and trading tools are usually split into a backend that does the computation and a frontend that displays it. A clean, validated API between them means the dashboard, scripts, or other services can all reuse the same backtest logic.

**Decisions I made:**
- Moved the backtest logic into a service layer that returns a plain result object, so the API, a CLI, or a background worker can all use it without depending on HTTP.
- Validated every request before doing any work: the fast window must be shorter than the slow one, start must be before end, at most 10 symbols, and at most 10 years. The caps also keep one request from tying up the server.
- Sent money as strings in JSON and ratios as numbers, since JSON numbers are floats.
- Undefined metrics come back as null instead of a fake number, for example a Sharpe ratio with zero volatility.
- Kept the endpoint synchronous for now since a year of data runs in about a second. Long research jobs would need a job queue and a background worker later.
- Read allowed CORS origins from settings instead of hardcoding them.

**Problems I ran into:**
- My first test request returned a 422 because the interactive docs pre-fill example values. Learned to read the response body, which says exactly which field failed and why.

**How I verified it:** 5 new tests: request validation for bad windows, reversed dates, and too many symbols, plus integration tests that store fake bars, list them through /symbols, and run a full backtest through the API. A rising fake price series with no crossovers gives flat equity, a null Sharpe ratio, and a positive buy-and-hold benchmark. 110 tests passing.

**Results:** A 2025 backtest of 10 symbols through the API returned 29 trades, +4.82% vs. +17.05% for SPY, Sharpe 0.54 vs. 0.81 (risk-free rate 2%), beta 0.07. This differs from my Week 6 run (22 trades) because the database now has data back to 2017, so the strategy warms up on 2024 bars and can trade from January 2 instead of losing six weeks to warm-up. The best single trade was 91% of net closed-trade profit.

**Commits:** `Add backtest service and API endpoints for the dashboard`

**Things I can talk about in interviews:** Service layers vs. HTTP handlers, request validation and why limits protect a server, CORS and why browsers enforce it, synchronous endpoints vs. job queues for long-running work, and why the same backtest can give different results depending on available warm-up history.

---

## Entry 13: Next.js dashboard
**Date:** Oct 6, 2026

**What I built:** A Next.js and TypeScript dashboard in a frontend folder. It loads the symbols stored in the database as clickable chips, runs a backtest from a form (symbols, dates, fast and slow windows) through the backtest API, and shows summary cards, a full metrics table against SPY, and trade statistics. Added a frontend job to CI that installs dependencies, lints, and runs a production build on every push.

**Tech:** Next.js (App Router), React, TypeScript, Tailwind CSS, openapi-typescript, GitHub Actions

**Why this matters in finance:** Trading desks run on internal web dashboards, usually React and TypeScript on top of Python or Java services. Keeping the frontend and backend in sync is a real problem on those teams.

**Decisions I made:**
- Generated the frontend's TypeScript types from the backend's OpenAPI schema instead of writing them by hand (contract-first). If a backend field changes and I regenerate, every frontend line using the old name fails to compile.
- Committed the generated types so CI can build the frontend without a running backend.
- Routed every request through one small API client that handles the base URL, JSON, and errors, including turning FastAPI's validation errors into readable messages. Components never call fetch directly.
- Kept money as strings from the API until the moment it's formatted for display, so all math stays in the backend in exact decimals.
- Read the API URL from NEXT_PUBLIC_API_URL so the same code works locally and when deployed. Nothing secret ever goes in a NEXT_PUBLIC variable, since those are visible in the browser.
- Used Node 24 LTS in CI even though I have Node 25 locally, since LTS versions are what production uses.

**Problems I ran into:**
- Ran npm from the repo root instead of the frontend folder. Each tool runs from the folder with its own config: pytest and alembic from backend, npm from frontend, git from the root.
- My .env.local file didn't get created at first. The app still worked because the API client falls back to localhost, but I added it so the setup is explicit.
- create-next-app generated a generic README, so I replaced it with one specific to this dashboard.

**How I verified it:** Ran a 2025 backtest from the dashboard, tested a bad request (fast window longer than slow) to confirm the backend's validation message shows in the UI, and ran lint and the production build, which also type-checks everything. CI now runs a backend job and a frontend job.

**Commits:** `Add Next.js dashboard with generated API types, backtest form and metrics view`

**Things I can talk about in interviews:** Contract-first development with OpenAPI-generated types, why a single API client beats scattered fetch calls, CORS, why public environment variables must never hold secrets, and why CI uses LTS versions and lockfile installs (npm ci).

---

## Entry 14: Dashboard charts and trade table
**Date:** Oct 6, 2026

**What I built:** Added a return chart (strategy vs. SPY from the same starting value), a drawdown chart (distance below the previous peak), an exposure chart (share of equity invested each day), and a sortable trade table with color-coded P&L to the dashboard. The chart math lives in pure functions with unit tests run by Vitest, and CI now runs those tests on every push.

**Tech:** Recharts, Vitest, React, TypeScript

**Why this matters in finance:** An equity curve, an underwater (drawdown) chart, an exposure chart, and a trade blotter are the standard views for reviewing a strategy. The drawdown chart is usually the first thing a risk manager looks at, because it shows the pain, not just the final number.

**Decisions I made:**
- Kept the chart math (returns, drawdowns, exposure) in pure functions separate from the chart components so it could be tested. The drawdown test uses the same 100, 120, 90, 110, 130 example as my backend test, so both sides use the same definition.
- Turned off chart animations, since animating up to 2,500 points per line made the page slow.
- Had the dashboard send capital, cash rate, and benchmark explicitly instead of relying on server defaults, so every request states its assumptions.

**Problems I ran into:**
- The Part B dashboard code had never actually been written to disk. The earlier CI run passed because it built Next.js's default page. I found it when the Part C files failed to write to missing folders, then wrote the missing files and verified the folder contents before moving on. Lesson: check that the files exist, not just that CI is green.
- Running `npm audit fix --force` downgraded the ESLint config two major versions behind Next.js to silence a warning. I restored package.json and package-lock.json from Git and evaluated the remaining advisory instead: it's in development tooling that never ships to the browser. Turned on Dependabot to handle real fixes.
- The production build failed because the generated request type made fields with server-side defaults required. Fixed it by sending those values explicitly.
- The chart's month-only date labels put events in the wrong month (SPY's April 8 low appeared under March), so I switched to full dates.
- Deleted 31 fake bars from an early test that were showing up as a "DEMO" symbol. Every bar stores its source, so the cleanup only touched fake data.

**How I verified it:** 3 Vitest tests for the chart math, lint, a type-checked production build, and a manual check that the dashboard numbers match the API exactly for the 2025 backtest (+4.82% vs. +17.05% for SPY, Sharpe 0.54, max drawdown -3.74%, 29 trades).

**Commits:** `Add return, drawdown and exposure charts and sortable trade table to the dashboard`

**Things I can talk about in interviews:** Why drawdown charts matter more than return charts for risk, separating pure calculation from rendering for testability, how I handled dependency vulnerabilities without breaking the toolchain, and catching that CI was green while the code I thought existed didn't.

---

## Entry 15: Research foundations
**Date:** Oct 9, 2026

**What I built:** The infrastructure for looking for a real trading edge without fooling myself. A 16-ETF research universe covering US and international stocks, real estate, Treasuries of three maturities, corporate and inflation-protected bonds, gold, silver, commodities, and the US dollar, with history back to 2007. A data quality report that checks every symbol against SPY's trading calendar for missing or extra days and flags any single-day move above 20%. A locked holdout: research tools refuse to touch data from 2023-01-01 onward unless I unlock it with a written reason, and every unlock is logged to docs/research/holdout-log.md. A hypothesis log where every strategy idea, its variants, and its success criteria get written down before testing.

**Tech:** Python, PostgreSQL, Tiingo API, pytest (tmp_path and monkeypatch)

**Why this matters in finance:** My Week 6 results showed parameter tuning overfit badly. Before searching for a profitable strategy, I needed measurements I could trust: a universe without hindsight bias, clean data, and a final test period I can't accidentally tune on.

**Decisions I made:**
- Switched from 10 hand-picked mega-cap stocks to broad asset-class ETFs. That removes most single-company survivorship bias and gives strategies like trend following assets that actually behave differently from each other.
- Started the data in 2007 so every test includes the 2008 financial crisis, the 2020 crash, and the 2022 bear market.
- Locked 2023 onward as the final test period, enforced in code instead of relying on willpower. I'm being honest that I already saw how markets behaved in 2023-2025, so the lock can't erase that, but it stops me from tuning these strategies on it.
- Pre-registering hypotheses before testing them, with a fixed small number of variants and default success criteria, to keep the multiple-testing problem under control. Failed ideas stay in the file.
- The quality report flags big moves for review instead of treating them as errors, since real markets do make huge moves.

**Problems I ran into:**
- The first ingestion run got interrupted with Ctrl+C partway through because it looked stuck (no output while each symbol saved). Since each symbol commits separately, the finished ones were kept and the interrupted one rolled back cleanly, so I just re-ran the remaining 12.
- Opened a new terminal and pytest wasn't found because the virtual environment wasn't active.

**How I verified it:** 4 new tests for the holdout lock, including one that redirects the log to a temporary folder so tests never write to my real docs. Confirmed the research CLI refuses a run that reaches past the lock date. 114 backend tests passing.

**Results:** Ingested 78,500 bars across 16 ETFs (2007 to Oct 2026). Zero missing and zero off-calendar days for every symbol. Two moves were flagged and both checked out as real: SLV fell 28.5% on Jan 30, 2026 (a historic silver crash after a record high the day before), and EEM rose 22.8% on Oct 13, 2008, the same day SPY had its biggest rally of the financial crisis.

**Commits:** `Add ETF research universe, data quality report, locked holdout guard and hypothesis log`

**Things I can talk about in interviews:** How I avoid overfitting (a locked holdout enforced in code, an unlock log, and pre-registered hypotheses), survivorship bias and why I moved to asset-class ETFs, data quality checks against a trading calendar, and why an extreme price move needs to be investigated rather than automatically deleted.
