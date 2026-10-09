#### H1: Development results
- **Code version:** commit `5c3b6e0b2972`
- **Data/config version:** data `ad3e31c528ae` | config `ef3096ca90c3` (pre-registered `ef3096ca90c3`)
- **Run IDs:** 12-month `0e2181d1`, 3-month `88a9c0e0`, 6-month `136dc6d7`
- **Period:** 2008-01-01 to 2023-01-01 | **Universe:** 16 ETFs | **Cash and risk-free rate:** 2.00% | **Costs:** CostModel defaults
- **Holdout unlocks used so far:** 0
- **Generated:** 2026-10-09 15:12 UTC

| Metric | Strategy | SPY buy and hold |
|---|---|---|
| Total return | +80.72% | +250.59% |
| CAGR | +4.03% | +8.73% |
| Volatility | 5.23% | 20.75% |
| Sharpe ratio | 0.40 | 0.41 |
| Max drawdown | -9.35% | -51.88% |
| Average exposure | 81.61% | 100.00% |
| Correlation to SPY | 0.38 | 1.00 |
| Closed trades | 133 | n/a |

| Robustness variant | Sharpe ratio |
|---|---|
| 3-month | 0.31 |
| 6-month | 0.41 |

| Sub-period | Strategy Sharpe | SPY Sharpe |
|---|---|---|
| 2008-2012 | 0.57 | 0.12 |
| 2013-2017 | 0.51 | 1.12 |
| 2018-2022 | 0.13 | 0.43 |

| Profit concentration | Share of net profit |
|---|---|
| Best trade | 14.25% |
| Top 5 trades (reported, not judged) | 43.14% |

| Group | Pre-registered criterion | Measured | Pass? |
|---|---|---|---|
| Return test (at least one) | Sharpe ratio higher than benchmark | 0.40 vs 0.41 | FAIL |
| Return test (at least one) | Sharpe within 0.10 of benchmark and max drawdown under 50% of benchmark's | Sharpe 0.40 vs 0.41, drawdown -9.35% vs -51.88% | PASS |
| Return test (at least one) | Correlation below 0.3 and Sharpe above 0.5 | correlation 0.38, Sharpe 0.40 | FAIL |
| Robustness (all) | Every robustness variant has a Sharpe of at least 0.0 | 3-month 0.31, 6-month 0.41 | PASS |
| Robustness (all) | Positive Sharpe in at least 2 of 3 sub-periods | 3 of 3 | PASS |
| Robustness (all) | Best trade under 25% of net profit | 14.25% | PASS |

- **Decision:** PASS
- **Reason:** written in hypotheses.md
