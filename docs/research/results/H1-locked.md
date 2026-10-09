#### H1: Locked results
- **Code version:** commit `73a76d624228`
- **Data/config version:** data `295de06c74c1` | config `ef3096ca90c3` (pre-registered `ef3096ca90c3`)
- **Run IDs:** 12-month `937349a9`
- **Period:** 2023-01-01 to 2026-10-09 | **Universe:** 16 ETFs | **Cash and risk-free rate:** 2.00% | **Costs:** CostModel defaults
- **Holdout unlocks used so far:** 1
- **Generated:** 2026-10-09 16:53 UTC

| Metric | Strategy | SPY buy and hold |
|---|---|---|
| Total return | +47.94% | +111.12% |
| CAGR | +11.01% | +22.05% |
| Volatility | 8.63% | 14.90% |
| Sharpe ratio | 1.02 | 1.28 |
| Max drawdown | -9.73% | -18.76% |
| Average exposure | 88.52% | 100.00% |
| Correlation to SPY | 0.67 | 1.00 |
| Closed trades | 25 | n/a |

Robustness variants: not run in this phase.

Sub-periods: not run in this phase.

| Profit concentration | Share of net profit |
|---|---|
| Best trade | 109.61% |
| Top 5 trades (reported, not judged) | 244.49% |

| Group | Pre-registered criterion | Measured | Pass? |
|---|---|---|---|
| Return test (at least one) | Sharpe ratio higher than benchmark | 1.02 vs 1.28 | FAIL |
| Return test (at least one) | Sharpe within 0.10 of benchmark and max drawdown under 50% of benchmark's | Sharpe 1.02 vs 1.28, drawdown -9.73% vs -18.76% | FAIL |
| Return test (at least one) | Correlation below 0.3 and Sharpe above 0.5 | correlation 0.67, Sharpe 1.02 | FAIL |
| Robustness (all) | Best trade under 25% of net profit | 109.61% | FAIL |

- **Decision:** FAIL
- **Reason:** written in hypotheses.md
