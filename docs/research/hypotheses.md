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
- **Development result:** (to be filled in)
- **Locked-period result:** (to be filled in)
- **Decision:** (to be filled in)
