#### H4: Development results
- **Code version:** commit `c4d204e4b296`
- **Data/config version:** data `ad3e31c528ae` | config `524acb2a255e` (pre-registered `524acb2a255e`)
- **Run IDs:** sleeve H1 `4840e69b`, sleeve H3 `ef1baa78`
- **Period:** 2008-01-01 to 2023-01-01 | **Universe:** 16 ETFs | **Cash and risk-free rate:** 2.00% | **Costs:** CostModel defaults
- **Holdout unlocks used so far:** 1
- **Generated:** 2026-10-12 15:44 UTC

| Metric | Strategy | SPY buy and hold |
|---|---|---|
| Total return | +169.45% | +250.59% |
| CAGR | +6.84% | +8.73% |
| Volatility | 12.90% | 20.75% |
| Sharpe ratio | 0.42 | 0.41 |
| Max drawdown | -34.88% | -51.88% |
| Average exposure | n/a | 100.00% |
| Correlation to SPY | 0.99 | 1.00 |
| Closed trades | 646 | n/a |

| Robustness variant | Sharpe ratio |
|---|---|
| 70% SPY, 30% satellite | 0.42 |
| 50% SPY, 50% satellite | 0.43 |

| Sub-period | Strategy Sharpe | SPY Sharpe |
|---|---|---|
| 2008-2012 | 0.14 | 0.12 |
| 2013-2017 | 1.08 | 1.12 |
| 2018-2022 | 0.40 | 0.43 |

| Profit concentration | Share of net profit |
|---|---|
| Best contribution, including open positions | n/a |
| Top 5 contributions, including open positions (reported, not judged) | n/a |

| Group | Pre-registered criterion | Measured | Pass? |
|---|---|---|---|
| Required (all) | Sharpe ratio higher than benchmark | 0.42 vs 0.41 | PASS |
| Required (all) | Max drawdown no more than 70% of benchmark's | -34.88% vs -51.88% (67% of benchmark) | PASS |
| Required (all) | Sharpe at least as high as benchmark in at least 2 of 3 sub-periods | 1 of 3 | FAIL |
| Required (all) | Every robustness variant has a Sharpe at least as high as benchmark | 70% SPY, 30% satellite 0.42, 50% SPY, 50% satellite 0.43 | PASS |

- **Decision:** FAIL
- **Reason:** written in hypotheses.md
