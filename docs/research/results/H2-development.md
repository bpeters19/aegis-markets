#### H2: Development results
- **Code version:** commit `6409593d3496`
- **Data/config version:** data `ad3e31c528ae` | config `6906a411ffa9` (pre-registered `6906a411ffa9`)
- **Run IDs:** sleeve H1 `e395c739`
- **Period:** 2008-01-01 to 2023-01-01 | **Universe:** 16 ETFs | **Cash and risk-free rate:** 2.00% | **Costs:** CostModel defaults
- **Holdout unlocks used so far:** 1
- **Generated:** 2026-10-12 15:41 UTC

| Metric | Strategy | SPY buy and hold |
|---|---|---|
| Total return | +196.74% | +250.59% |
| CAGR | +7.53% | +8.73% |
| Volatility | 14.99% | 20.75% |
| Sharpe ratio | 0.43 | 0.41 |
| Max drawdown | -40.10% | -51.88% |
| Average exposure | n/a | 100.00% |
| Correlation to SPY | 0.99 | 1.00 |
| Closed trades | 133 | n/a |

| Robustness variant | Sharpe ratio |
|---|---|
| 80% SPY, 20% trend | 0.42 |
| 60% SPY, 40% trend | 0.43 |

| Sub-period | Strategy Sharpe | SPY Sharpe |
|---|---|---|
| 2008-2012 | 0.14 | 0.12 |
| 2013-2017 | 1.06 | 1.12 |
| 2018-2022 | 0.42 | 0.43 |

| Profit concentration | Share of net profit |
|---|---|
| Best contribution, including open positions | n/a |
| Top 5 contributions, including open positions (reported, not judged) | n/a |

| Group | Pre-registered criterion | Measured | Pass? |
|---|---|---|---|
| Required (all) | Sharpe ratio at least as high as benchmark | 0.43 vs 0.41 | PASS |
| Required (all) | Max drawdown no more than 80% of benchmark's | -40.10% vs -51.88% (77% of benchmark) | PASS |
| Required (all) | Sharpe at least as high as benchmark in at least 2 of 3 sub-periods | 1 of 3 | FAIL |
| Required (all) | Every robustness variant has a Sharpe at least as high as benchmark | 80% SPY, 20% trend 0.42, 60% SPY, 40% trend 0.43 | PASS |

- **Decision:** FAIL
- **Reason:** written in hypotheses.md
