#### H3: Development results
- **Code version:** commit `81236484b021`
- **Data/config version:** data `b757d04836e7` | config `88055e63c63c` (pre-registered `88055e63c63c`)
- **Run IDs:** RSI below 10 `ce67b7c1`, RSI below 5 `39dc6d50`, RSI below 15 `c1ca1b31`
- **Period:** 2008-01-01 to 2023-01-01 | **Universe:** 5 ETFs | **Cash and risk-free rate:** 2.00% | **Costs:** CostModel defaults
- **Holdout unlocks used so far:** 1
- **Generated:** 2026-10-12 15:03 UTC

| Metric | Strategy | SPY buy and hold |
|---|---|---|
| Total return | +50.92% | +250.59% |
| CAGR | +2.78% | +8.73% |
| Volatility | 3.38% | 20.75% |
| Sharpe ratio | 0.24 | 0.41 |
| Max drawdown | -7.01% | -51.88% |
| Average exposure | 7.16% | 100.00% |
| Correlation to SPY | 0.35 | 1.00 |
| Closed trades | 513 | n/a |

| Robustness variant | Sharpe ratio |
|---|---|
| RSI below 5 | 0.25 |
| RSI below 15 | 0.28 |

| Sub-period | Strategy Sharpe | SPY Sharpe |
|---|---|---|
| 2008-2012 | 0.39 | 0.12 |
| 2013-2017 | 0.54 | 1.12 |
| 2018-2022 | -0.11 | 0.43 |

| Profit concentration | Share of net profit |
|---|---|
| Best contribution, including open positions | 6.22% |
| Top 5 contributions, including open positions (reported, not judged) | 23.14% |

| Group | Pre-registered criterion | Measured | Pass? |
|---|---|---|---|
| Required (all) | Sharpe ratio above 0.5 | 0.24 | FAIL |
| Required (all) | Correlation to benchmark below 0.5 | 0.35 | PASS |
| Required (all) | Profit factor above 1.3 | 1.30 | PASS |
| Required (all) | At least 200 closed trades | 513 | PASS |
| Required (all) | Best contribution under 10% of total profit including open positions | 6.22% | PASS |
| Required (all) | Every robustness variant has a Sharpe ratio above 0.0 | RSI below 5 0.25, RSI below 15 0.28 | PASS |
| Required (all) | Positive Sharpe in at least 2 of 3 sub-periods | 2 of 3 | PASS |

- **Decision:** FAIL
- **Reason:** written in hypotheses.md
