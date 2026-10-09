"""Renders an EvaluationResult as the standard Markdown results template and as JSON."""
import json
from dataclasses import asdict
from datetime import date
from decimal import Decimal
from typing import Any

from app.backtest.run import num, pct
from app.research.evaluation import EvaluationResult

GROUP_LABEL = {"return": "Return test (at least one)", "robustness": "Robustness (all)"}


def _json_default(value: Any) -> Any:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, date):
        return value.isoformat()
    raise TypeError(f"cannot serialize {type(value).__name__}")


def to_json(result: EvaluationResult) -> str:
    return json.dumps(asdict(result), default=_json_default, indent=2)


def _robustness_table(r: EvaluationResult) -> list[str]:
    if not r.robustness:
        return ["Robustness variants: not run in this phase."]
    return [
        "| Robustness variant | Sharpe ratio |",
        "|---|---|",
        *[f"| {name} | {num(sharpe)} |" for name, sharpe in r.robustness.items()],
    ]


def _subperiod_table(r: EvaluationResult) -> list[str]:
    if not r.subperiods:
        return ["Sub-periods: not run in this phase."]
    return [
        f"| Sub-period | Strategy Sharpe | {r.benchmark_name} Sharpe |",
        "|---|---|---|",
        *[f"| {p.name} | {num(p.strategy_sharpe)} | {num(p.benchmark_sharpe)} |" for p in r.subperiods],
    ]


def to_markdown(r: EvaluationResult) -> str:
    s, b = r.strategy, r.benchmark
    bn = r.benchmark_name

    def bench(fn):
        return fn(b) if b else "n/a"

    lines = [
        f"#### {r.hypothesis_id}: {r.phase.capitalize()} results",
        f"- **Code version:** commit `{r.commit}`",
        f"- **Data/config version:** data `{r.data_hash}` | config `{r.config_hash}` "
        f"(pre-registered `{r.registered_config_hash}`)",
        "- **Run IDs:** " + ", ".join(f"{name} `{run_id}`" for name, run_id in r.run_ids.items()),
        f"- **Period:** {r.period_start} to {r.period_end} | **Universe:** {len(r.universe)} ETFs | "
        f"**Cash and risk-free rate:** {r.cash_rate:.2%} | **Costs:** CostModel defaults",
        f"- **Holdout unlocks used so far:** {r.holdout_unlocks}",
        f"- **Generated:** {r.generated_at}",
        "",
        f"| Metric | Strategy | {bn} buy and hold |",
        "|---|---|---|",
        f"| Total return | {pct(s.total_return)} | {bench(lambda x: pct(x.total_return))} |",
        f"| CAGR | {pct(s.cagr)} | {bench(lambda x: pct(x.cagr))} |",
        f"| Volatility | {pct(s.volatility, False)} | {bench(lambda x: pct(x.volatility, False))} |",
        f"| Sharpe ratio | {num(s.sharpe)} | {bench(lambda x: num(x.sharpe))} |",
        f"| Max drawdown | {pct(s.drawdown.max_drawdown)} | {bench(lambda x: pct(x.drawdown.max_drawdown))} |",
        f"| Average exposure | {pct(r.average_exposure, False)} | 100.00% |",
        f"| Correlation to {bn} | {num(r.correlation)} | 1.00 |",
        f"| Closed trades | {r.closed_trades} | n/a |",
        "",
        *_robustness_table(r),
        "",
        *_subperiod_table(r),
        "",
        "| Profit concentration | Share of net profit |",
        "|---|---|",
        f"| Best trade | {pct(r.best_trade_share, False)} |",
        f"| Top 5 trades (reported, not judged) | {pct(r.top5_trade_share, False)} |",
        "",
        "| Group | Pre-registered criterion | Measured | Pass? |",
        "|---|---|---|---|",
        *[
            f"| {GROUP_LABEL[c.group]} | {c.name} | {c.measured} | {'PASS' if c.passed else 'FAIL'} |"
            for c in r.criteria
        ],
        "",
        f"- **Decision:** {'PASS' if r.passed else 'FAIL'}",
        "- **Reason:** written in hypotheses.md",
    ]
    return "\n".join(lines) + "\n"
