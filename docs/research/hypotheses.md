# Research Hypotheses

Every strategy idea is written here **before** it is tested. This limits how many variants get tried and keeps results honest.

## Rules

1. Write the hypothesis, the reasoning, the variants, and the success criteria before running any backtest.
2. Keep variants to a small fixed set (at most about 6). More variants means more chances to find something by luck.
3. Develop and walk-forward test only on data before the research lock date (2023-01-01).
4. A hypothesis that passes development gets **one** run on the locked period. That result is recorded here, good or bad.
5. Failed hypotheses stay in this file. Deleting failures hides how many ideas were tried.

## Success criteria (default)

Out-of-sample, after costs, a strategy must beat at least one of these to be worth paper trading:
- higher Sharpe ratio than buy-and-hold SPY, or
- a similar Sharpe ratio with a max drawdown less than half of SPY's, or
- returns with low correlation to SPY (below 0.3) and a Sharpe ratio above 0.5.

---

## Template

### H#: Name
- **Date written:**
- **Hypothesis:**
- **Why it might work:**
- **Universe and period:**
- **Variants (fixed list):**
- **Success criteria:**
- **Development result:**
- **Locked-period result:**
- **Decision:**

---

### H1: Time-series momentum across asset classes
- **Date written:** 2026-10-09 (before any H1 code or results exist)
- **Hypothesis:** An asset whose own trailing return is positive tends to keep rising over the next month, across stocks, bonds, real estate, commodities and currencies. Holding an asset only while its trailing return is positive, sized by volatility, earns better risk-adjusted returns than buy-and-hold SPY.
- **Why it might work:** Time-series momentum is one of the most widely documented effects in finance, found across asset classes over many decades. Common explanations are investors under-reacting to new information and then over-reacting, plus hedging and flow pressure. Its known weakness is sharp trend reversals.
- **Rule:**
  - Evaluate on the first trading day of each month, using that day's close. Orders fill at the next day's open.
  - For each asset, compute the trailing return over the lookback window. Positive: target is long. Zero or negative: target is flat.
  - Every month, emit the target for every asset (BUY if long, SELL if flat). The risk engine ignores buys of assets already held and sells of assets not held.
  - No fixed stop-loss or take-profit. Exits come only from the monthly signal.
- **Sizing and limits:** volatility-targeted sizing, 1% annualized volatility target per position, 20-day volatility estimate, max 15% of equity per position, max 100% total exposure (no leverage), up to 16 open positions, no stop required. All other limits at their defaults.
- **Universe and period:** etf_core (16 ETFs). Development period 2008-01-01 to 2023-01-01, with indicator warm-up on 2007 data. Idle cash earns 2% and the Sharpe ratio uses a 2% risk-free rate.
- **Variants (fixed list):**
  - **Primary:** 12-month lookback (252 trading days), chosen in advance because it is the standard in the published research.
  - **Robustness only:** 3-month (63 days) and 6-month (126 days). These cannot replace the primary even if they score higher.
- **Success criteria (primary variant, 2008-2022, after costs):** at least one of
  - Sharpe ratio higher than SPY buy-and-hold over the same period
  - Sharpe ratio within 0.10 of SPY with a max drawdown less than half of SPY's
  - correlation to SPY below 0.3 and Sharpe ratio above 0.5

  and all of these robustness checks:
  - neither robustness variant has a negative Sharpe ratio
  - the primary variant has a positive Sharpe ratio in at least 2 of the 3 sub-periods 2008-2012, 2013-2017, 2018-2022
  - the single best trade is under 25% of net profit
- **If it passes:** one run of the primary variant on the locked period (2023-01-01 to the latest data), judged by the same criteria against SPY, logged as a holdout unlock. That result is recorded here whatever it shows.
- **If it fails:** recorded here, and the next hypothesis starts from scratch. The parameters do not get adjusted to make H1 pass.
- **Known limitations, stated in advance:** positions are sized at entry and not rebalanced until exit; when the exposure cap binds, symbols processed first in a day get the capital; flat 2% rate instead of historical T-bill rates; the ETF list was chosen in 2026, so a milder form of selection bias remains; HYG and UUP lack a full 12 months of history at the start of 2008, so they join later.
- **Config hash at pre-registration:** `ef3096ca90c3` (backend/app/research/hypotheses/h1.py)
- **Development result:** PASS. [Full report](results/H1-development.md) | commit `5c3b6e0b2972` | data `ad3e31c528ae` | config `ef3096ca90c3`
- **Development reason:** Passed on the drawdown test: Sharpe 0.40 vs 0.41 for SPY with a max drawdown of -9.35% vs -51.88%. Both robustness lookbacks and all three sub-periods were positive, and the best trade was 14% of profit. It did not beat SPY's Sharpe and its CAGR was about half of SPY's, so the edge is lower risk, not higher returns. The 2018-2022 Sharpe (0.13) was much weaker than the earlier periods, and the top 5 trades were 43% of profit. Neither was a pre-registered criterion, but I'm watching both.
- **Locked-period judging (clarified 2026-10-09, after the development result and before any locked data was run):** the original text says the locked run is judged "by the same criteria against SPY." Since only the primary variant runs on the locked period, it is judged by the three return tests (at least one must pass) and the best-trade concentration check. The robustness lookbacks and sub-periods are development checks and are not re-run.
- **Locked-period result:** FAIL. [Full report](results/H1-locked.md) | commit `73a76d624228` | data `295de06c74c1` | config `ef3096ca90c3` | holdout unlocks: 1
- **Locked-period reason:** Failed all three return tests. It made 11.0% a year with a Sharpe of 1.02, but SPY made 22.1% a year with a Sharpe of 1.28, and its drawdown (-9.73%) was just over half of SPY's (-18.76%). Correlation to SPY jumped from 0.38 in development to 0.67, so in this bull market it mostly acted like a smaller version of the stock market instead of a diversifier. It also failed the concentration check, but that number is distorted: only 25 trades closed and most of the profit was in positions still open at the end. The return tests failed on their own, so the decision does not depend on it.
- **Decision:** FAIL. H1 is not promoted to paper trading and its parameters will not be adjusted.
- **Lessons for future hypotheses (recorded before H2 is written):** measure profit concentration on total P&L including open positions, not only closed trades; choose and pre-register a benchmark that matches the kind of strategy being tested.

---

## Promotion rules (written 2026-10-09, before H2 and H3 are tested)

No strategy trades real money because of a backtest alone. To move from research to real money, a strategy must:
1. Pass its development test and its out-of-sample test (locked period or forward paper trading, as pre-registered).
2. Run in live paper trading for at least 6 months with no unexplained differences between live fills and simulated fills, and with no risk-limit or reconciliation failures.
3. Start with a small allocation I can afford to lose entirely, with the kill switch and daily loss limit active.

---

### H2: Stocks plus a trend-following sleeve
- **Date written:** 2026-10-09, before any H2 code or results exist. Written after H1's results were known, which is why H2's out-of-sample test is forward paper trading (see below).
- **Hypothesis:** A portfolio holding mostly SPY plus a trend-following sleeve has a better risk-adjusted return and a smaller drawdown than holding SPY alone.
- **Why it might work:** H1 had a similar Sharpe ratio to SPY in development with a much smaller drawdown, and it did best when stocks did worst (2008-2012). Combining two return streams that fail at different times usually improves the combination.
- **Rule:** each month, rebalance to fixed weights between SPY buy-and-hold and the H1 trend sleeve (H1's exact rules, sizing and limits). Weights drift between rebalances. Simulated by combining the two daily return series, with a cost of 5 basis points on the traded amount at each rebalance.
- **Universe and period:** SPY plus the etf_core trend sleeve; development 2008-01-01 to 2023-01-01; 2% cash and risk-free rate.
- **Variants (fixed list):**
  - **Primary:** 70% SPY, 30% trend sleeve.
  - **Robustness only:** 80/20 and 60/40.
- **Benchmark:** SPY buy-and-hold, because H2 is meant to replace holding SPY.
- **Success criteria (development, primary variant), all required:**
  - Sharpe ratio at least as high as SPY's
  - max drawdown no more than 80% of SPY's
  - Sharpe ratio at least as high as SPY's in at least 2 of the 3 sub-periods (2008-2012, 2013-2017, 2018-2022)
  - both robustness variants have a Sharpe ratio at least as high as SPY's
- **Out-of-sample test:** no locked-period run, because the trend sleeve's 2023-2026 results are already known from H1. If H2 passes development, its out-of-sample test is 6 months of forward paper trading, judged by the same criteria against SPY over the same months.
- **Known limitations, stated in advance:** return-level simulation instead of share-level rebalancing in the engine; the trend sleeve inherits H1's limitations; flat 2% rate.
- **Development result:** (to be filled in)
- **Out-of-sample result:** (to be filled in)
- **Decision:** (to be filled in)

---

### H3: Short-term mean reversion in equity index ETFs
- **Date written:** 2026-10-09, before any H3 code or results exist.
- **Hypothesis:** Broad equity index ETFs that have fallen sharply over a few days, while still in a long-term uptrend, tend to bounce over the following days.
- **Why it might work:** Short-term overreaction and liquidity demand push index prices below fair value briefly; the effect is documented in broad equity indices. Known weaknesses: it buys into crashes, its edge is sensitive to execution timing and costs, and it has likely faded as it became popular.
- **Rule:**
  - Universe limited to equity index ETFs: SPY, QQQ, IWM, EFA, EEM.
  - Entry signal at the close when the 2-day RSI is below the entry threshold and the close is above its 200-day moving average. Order fills at the next day's open.
  - Exit signal at the close when the close is above its 5-day moving average, or after 10 trading days in the position, whichever comes first. Order fills at the next day's open.
  - No fixed stop-loss. The 200-day filter and the 10-day time limit are the crash protection.
- **Sizing and limits:** volatility-targeted sizing, 2% volatility target per position, max 20% of equity per position, max 100% exposure, up to 5 positions, no stop required.
- **Universe and period:** development 2008-01-01 to 2023-01-01; 2% cash and risk-free rate.
- **Variants (fixed list):**
  - **Primary:** entry when 2-day RSI is below 10.
  - **Robustness only:** entry thresholds of 5 and 15.
- **Benchmark:** none for raw return. H3 is a low-exposure satellite, so it is judged on its own risk-adjusted return and on being different from SPY.
- **Success criteria (development, primary variant), all required:**
  - Sharpe ratio above 0.5
  - correlation to SPY below 0.5
  - profit factor above 1.3
  - at least 200 closed trades
  - the single best trade is under 10% of total profit, including open positions
  - both robustness variants have a positive Sharpe ratio
  - positive Sharpe ratio in at least 2 of the 3 sub-periods (2008-2012, 2013-2017, 2018-2022)
- **Out-of-sample test:** one locked-period run of the primary variant (2023-01-01 to the latest data), judged by the Sharpe, correlation, profit factor, and concentration criteria. The trade-count criterion is scaled to the locked period's length. That run is logged as a holdout unlock.
- **Known limitations, stated in advance:** fills at the next open instead of the signal close, which may reduce the edge compared with published results; all gains are short-term for tax purposes; flat 2% rate; the five ETFs were chosen in 2026.
- **Development result:** (to be filled in)
- **Locked-period result:** (to be filled in)
- **Decision:** (to be filled in)
