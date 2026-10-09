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
